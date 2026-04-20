import re
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.models.cv_models import JobExperience
from app.models.planner_decision import PlannerDecision
from app.utils.timing import timed


class CompanyExtractionResult(BaseModel):
    company_name: str | None = Field(default=None)
    reason: str = Field(default="")


class PlannerAgentService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are an interview-prep planner focused ONLY on information extraction. "
                    "Do not provide coaching guidance, strategies, or mock interview plans. "
                    "Extract factual role information from provided JD context.",
                ),
                (
                    "human",
                    "User query:\n{user_query}\n\n"
                    "Resolved company name: {resolved_company}\n"
                    "Company source: {company_source}\n\n"
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
                    "Do not guess.",
                ),
                ("human", "JD content:\n{jd_context}"),
            ]
        )

    @timed("planner.plan")
    def plan(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        job_experiences: list[JobExperience],
    ) -> PlannerDecision:
        if not self._settings.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable for planner agent")

        resolved_company, company_source = self._resolve_company(
            user_company=company_name,
            jd_text=jd_text,
        )
        jd_context = self._select_jd_context(jd_text=jd_text, user_query=user_query)
        cv_context = self._format_cv_context(job_experiences)

        llm = self._build_llm()
        chain = self._prompt | llm.with_structured_output(PlannerDecision)
        decision = chain.invoke(
            {
                "user_query": user_query,
                "resolved_company": resolved_company or "Not identified",
                "company_source": company_source,
                "jd_context": jd_context,
                "cv_context": cv_context,
            }
        )
        decision.company_name = resolved_company
        decision.company_source = company_source
        return decision

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_large_model,
            temperature=0,
        )

    def _resolve_company(self, user_company: str | None, jd_text: str) -> tuple[str | None, str]:
        if user_company and user_company.strip():
            return user_company.strip(), "request"

        from_jd = self._extract_company_from_jd_llm(jd_text)
        if from_jd:
            return from_jd, "jd"
        return None, "unknown"

    @timed("planner.extract_company_from_jd_llm")
    def _extract_company_from_jd_llm(self, jd_text: str) -> str | None:
        llm = self._build_llm()
        chain = self._company_extraction_prompt | llm.with_structured_output(CompanyExtractionResult)
        context = jd_text[: self._settings.max_jd_chars]
        result = chain.invoke({"jd_context": context})
        if not result.company_name:
            return None
        candidate = re.sub(r"\s+", " ", result.company_name).strip(" .,:;|-")
        if len(candidate) < 2:
            return None
        return candidate

    def _select_jd_context(self, jd_text: str, user_query: str) -> str:
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

    def _format_cv_context(self, job_experiences: list[JobExperience]) -> str:
        if not job_experiences:
            return "No CV provided."

        lines: list[str] = []
        for idx, exp in enumerate(job_experiences[:8], start=1):
            header = f"{idx}. Role: {exp.role}"
            if exp.company:
                header += f" | Company: {exp.company}"
            if exp.period:
                header += f" | Period: {exp.period}"
            lines.append(header)
            if exp.tech_stack:
                lines.append(f"   Tech stack: {', '.join(exp.tech_stack[:12])}")
            for p_idx, project in enumerate(exp.projects[:4], start=1):
                lines.append(f"   Project {p_idx}: {project.name}")
                if project.main_work:
                    lines.append(f"     Main work: {'; '.join(project.main_work[:3])}")
                if project.key_improvements:
                    lines.append(f"     Key improvements: {'; '.join(project.key_improvements[:3])}")
                if project.key_designs:
                    lines.append(f"     Key designs: {'; '.join(project.key_designs[:3])}")
                if project.notable_results:
                    lines.append(f"     Results: {'; '.join(project.notable_results[:3])}")
        return "\n".join(lines)
