import re
import logging
import json
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.models.cv_models import JobExperience
from app.models.planner_decision import InterviewStrategyExtraction, JobRequirementExtraction
from app.utils.timing import timed


class CompanyExtractionResult(BaseModel):
    company_name: str | None = Field(default=None)
    reason: str = Field(default="")


class PlannerAgentService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._requirement_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an interview-prep planner. "
                    "Extract factual role information from JD and build a practical interview roadmap "
                    "grounded in JD + candidate CV context. "
                    "When JD URL is provided, use it directly as the primary source for JD content interpretation. "
                    "Avoid generic advice. Tie revision items and questions to concrete JD requirements "
                    "and the candidate's past experience. "
                    "If JD explicitly mentions interview rounds/process, set interview_process_source='jd' "
                    "and follow that structure. "
                    "If JD does not mention interview process, set interview_process_source='default' "
                    "and use these stages in order:\n"
                    "1) Technical interview\n"
                    "2) Cultural / past experience interview\n"
                    "3) CEO interview\n"
                    "For each stage, include stage_objective, why_this_matters_for_this_role, "
                    "revision_roadmap, expected_questions, and questions_to_ask_interviewer. "
                    "Keep outputs concise and specific; do not hallucinate missing details.",
                ),
                (
                    "human",
                    "User query:\n{user_query}\n\n"
                    "Resolved company name: {resolved_company}\n"
                    "Company source: {company_source}\n\n"
                    "JD URL (optional): {jd_url}\n\n"
                    "Selected JD context:\n{jd_context}\n\n"
                    "Candidate CV experience summary:\n{cv_context}",
                ),
            ]
        )
        self._company_extraction_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract the real hiring company name from JD text. "
                    "If unresolved or unclear, return null for company_name. "
                    "When JD URL is provided, use that URL as source context. "
                    "Do not guess.",
                ),
                ("human", "JD URL (optional): {jd_url}\n\nJD content:\n{jd_context}"),
            ]
        )
        self._strategy_enrichment_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You design senior-level interview preparation strategy for backend/AI product roles.\n"
                    "Output must be specific, evidence-based, and interviewer-grade deep.\n\n"
                    "Quality bar:\n"
                    "- Do not produce generic advice.\n"
                    "- Materialize concrete projects/contexts from extracted candidate experiences.\n"
                    "- Prefer questions in this probing style:\n"
                    "  In project X, when problem Y happened, what action Z did you take and why?\n"
                    "- Include diagnostic follow-ups on metrics, logs/signals, trade-offs, alternatives, failure handling, and lessons learned.\n"
                    "- Include deep fundamentals checks for technologies in JD/candidate stack (e.g. async model, Future/Promise concepts, FastAPI/ASGI internals, distributed systems primitives).\n"
                    "- When candidate experience includes recommendation/ranking/retrieval systems, explicitly include deep probes such as long-tail handling, cold-start strategy, feedback loops, offline-vs-online metric mismatch, and serving latency vs quality trade-offs.\n"
                    "- When candidate experience includes LLM/RAG systems, probe chunking/retrieval quality, hallucination controls, eval design, and cost/latency controls under production constraints.\n"
                    "- The goal is to test whether candidate truly understands systems, not whether they can repeat buzzwords.\n\n"
                    "Stage requirements:\n"
                    "- Keep stage order and names exactly aligned with provided stage templates.\n"
                    "- For each stage, keep fields complete and concrete.\n"
                    "- revision_roadmap must be execution-oriented and tied to extracted projects/problems.\n"
                    "- expected_questions must include both scenario deep-dives and fundamentals stress-test questions.\n"
                    "- questions_to_ask_interviewer should probe architecture constraints, reliability expectations, incident posture, ownership boundaries, and strategy.\n"
                    "- Keep outputs concise but high-signal.",
                ),
                (
                    "human",
                    "User query:\n{user_query}\n\n"
                    "Resolved company: {resolved_company}\n"
                    "Company source: {company_source}\n\n"
                    "JD URL (optional): {jd_url}\n\n"
                    "JD context:\n{jd_context}\n\n"
                    "Extracted job requirements:\n{requirements_context}\n\n"
                    "Extracted candidate experiences (structured):\n{experiences_context}\n\n"
                    "Stage templates to preserve and enrich:\n{stage_templates_context}\n\n"
                    "Generate enriched interview strategy only.",
                ),
            ]
        )

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_large_model,
            temperature=0,
        )

    @timed("planner.resolve_company")
    def resolve_company(
        self,
        user_company: str | None,
        jd_text: str,
        jd_url: str | None,
    ) -> tuple[str | None, Literal["request", "jd", "unknown"]]:
        if user_company and user_company.strip():
            return user_company.strip(), "request"

        from_jd = self._extract_company_from_jd_llm(jd_text, jd_url)
        if from_jd:
            return from_jd, "jd"
        return None, "unknown"

    @timed("planner.extract_job_requirements")
    def extract_job_requirements(
        self,
        user_query: str,
        jd_text: str,
        jd_url: str | None,
        resolved_company: str | None,
        company_source: str,
        cv_text: str | None,
    ) -> JobRequirementExtraction:
        if not self._settings.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable for planner agent")

        jd_context = self._select_jd_context(jd_text=jd_text, jd_url=jd_url, user_query=user_query)
        cv_context = self._format_cv_text_context(cv_text)

        llm = self._build_llm()
        chain = self._requirement_prompt | llm.with_structured_output(JobRequirementExtraction)
        return chain.invoke(
            {
                "user_query": user_query,
                "resolved_company": resolved_company or "Not identified",
                "company_source": company_source,
                "jd_url": jd_url or "Not provided",
                "jd_context": jd_context,
                "cv_context": cv_context,
            }
        )

    @timed("planner.enrich_interview_strategy")
    def enrich_interview_strategy(
        self,
        user_query: str,
        jd_text: str,
        jd_url: str | None,
        resolved_company: str | None,
        company_source: str,
        requirements: JobRequirementExtraction,
        job_experiences: list[JobExperience],
    ) -> InterviewStrategyExtraction:
        jd_context = self._select_jd_context(jd_text=jd_text, jd_url=jd_url, user_query=user_query)
        llm = self._build_llm()
        chain = self._strategy_enrichment_prompt | llm.with_structured_output(InterviewStrategyExtraction)
        return chain.invoke(
            {
                "user_query": user_query,
                "resolved_company": resolved_company or "Not identified",
                "company_source": company_source,
                "jd_url": jd_url or "Not provided",
                "jd_context": jd_context,
                "requirements_context": self._format_requirements_context(requirements),
                "experiences_context": self._format_job_experience_context(job_experiences),
                "stage_templates_context": self._format_stage_templates_context(requirements.interview_strategy),
            }
        )

    @timed("planner.extract_company_from_jd_llm")
    def _extract_company_from_jd_llm(self, jd_text: str, jd_url: str | None) -> str | None:
        llm = self._build_llm()
        chain = self._company_extraction_prompt | llm.with_structured_output(CompanyExtractionResult)
        context = self._select_jd_context(jd_text=jd_text, jd_url=jd_url, user_query="")
        result = chain.invoke({"jd_url": jd_url or "Not provided", "jd_context": context})
        if not result.company_name:
            return None
        candidate = re.sub(r"\s+", " ", result.company_name).strip(" .,:;|-")
        if len(candidate) < 2:
            return None
        return candidate

    def _select_jd_context(self, jd_text: str, jd_url: str | None, user_query: str) -> str:
        if jd_url:
            return f"JD URL: {jd_url}"

        max_chars = self._settings.max_jd_chars
        if len(jd_text) <= max_chars:
            return jd_text

        blocks = [block.strip() for block in re.split(r"\n\s*\n", jd_text) if block.strip()]
        if not blocks:
            return jd_text[:max_chars]

        query_terms = set(re.findall(r"[a-zA-Z]{3,}", user_query.lower()))
        keywords = {
            "responsibility",
            "responsibilities",
            "scope",
            "requirement",
            "requirements",
            "qualification",
            "qualifications",
            "must",
            "preferred",
            "experience",
            "skills",
            "tech",
            "stack",
            "python",
            "ai",
            "ml",
            "llm",
        }

        scored: list[tuple[int, int, str]] = []
        for idx, block in enumerate(blocks):
            lower = block.lower()
            score = sum(2 for keyword in keywords if keyword in lower)
            score += sum(1 for term in query_terms if term in lower)
            score += 1 if len(block) < 500 else 0
            scored.append((score, idx, block))

        scored.sort(key=lambda item: (-item[0], item[1]))
        picked: list[tuple[int, str]] = []
        total = 0
        for score, idx, block in scored:
            _ = score
            if total >= max_chars:
                break
            remaining = max_chars - total
            if remaining <= 0:
                break
            snippet = block[:remaining]
            picked.append((idx, snippet))
            total += len(snippet) + 2

        picked.sort(key=lambda item: item[0])
        return "\n\n".join(part for _, part in picked).strip()

    def _format_cv_text_context(self, cv_text: str | None) -> str:
        if not cv_text or not cv_text.strip():
            return "No CV provided."
        return cv_text[: self._settings.max_cv_chars]

    def _format_requirements_context(self, requirements: JobRequirementExtraction) -> str:
        payload = {
            "reason": requirements.reason,
            "scope_of_work": requirements.scope_of_work,
            "key_qualifications": requirements.key_qualifications,
            "tech_stacks": requirements.tech_stacks,
            "jd_gaps_or_ambiguities": requirements.jd_gaps_or_ambiguities,
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)[: self._settings.max_research_chars]

    def _format_job_experience_context(self, job_experiences: list[JobExperience]) -> str:
        if not job_experiences:
            return "No extracted job experiences available."
        payload = [experience.model_dump() for experience in job_experiences]
        max_chars = max(self._settings.max_cv_chars, 6000)
        return json.dumps(payload, ensure_ascii=True, indent=2)[:max_chars]

    def _format_stage_templates_context(self, strategy: InterviewStrategyExtraction) -> str:
        payload = {
            "interview_process_source": strategy.interview_process_source,
            "process_reason": strategy.process_reason,
            "stage_names": [stage.stage_name for stage in strategy.stage_plans],
        }
        return json.dumps(payload, ensure_ascii=True, indent=2)
