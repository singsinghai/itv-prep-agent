import re
import logging
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.models.planner_decision import JobRequirementExtraction
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

    def _build_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_large_model,
            temperature=0,
        )

    @timed("planner.resolve_company")
    def resolve_company(self, user_company: str | None, jd_text: str) -> tuple[str | None, Literal["request", "jd", "unknown"]]:
        if user_company and user_company.strip():
            return user_company.strip(), "request"

        from_jd = self._extract_company_from_jd_llm(jd_text)
        if from_jd:
            return from_jd, "jd"
        return None, "unknown"

    @timed("planner.extract_job_requirements")
    def extract_job_requirements(
        self,
        user_query: str,
        jd_text: str,
        resolved_company: str | None,
        company_source: str,
        cv_text: str | None,
    ) -> JobRequirementExtraction:
        if not self._settings.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable for planner agent")

        jd_context = self._select_jd_context(jd_text=jd_text, user_query=user_query)
        cv_context = self._format_cv_text_context(cv_text)

        llm = self._build_llm()
        chain = self._requirement_prompt | llm.with_structured_output(JobRequirementExtraction)
        return chain.invoke(
            {
                "user_query": user_query,
                "resolved_company": resolved_company or "Not identified",
                "company_source": company_source,
                "jd_context": jd_context,
                "cv_context": cv_context,
            }
        )

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

    def _format_cv_text_context(self, cv_text: str | None) -> str:
        if not cv_text or not cv_text.strip():
            return "No CV provided."
        return cv_text[: self._settings.max_cv_chars]
