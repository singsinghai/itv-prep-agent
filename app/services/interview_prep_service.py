import logging
import asyncio

from app.models.company_research import CEOProfile
from app.models.cv_models import JobExperience
from app.models.interview_prep_response import (
    CompanyInformationSection,
    InterviewPrepResponse,
    JobRequirementSection,
    UserJobExperiencesSection,
)
from app.services.cv_extraction_service import CVExtractionService
from app.services.company_research_service import CompanyResearchService
from app.services.planner_agent_service import PlannerAgentService
from app.utils.timing import timed


class InterviewPrepService:
    def __init__(
        self,
        planner_service: PlannerAgentService,
        company_research_service: CompanyResearchService,
        cv_extraction_service: CVExtractionService,
    ) -> None:
        self._planner_service = planner_service
        self._company_research_service = company_research_service
        self._cv_extraction_service = cv_extraction_service
        self._logger = logging.getLogger(__name__)

    @timed("interview_prep.process")
    async def process(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        cv_text: str | None,
    ) -> InterviewPrepResponse:
        cv_task = self._run_user_profile_flow(cv_text)
        job_company_task = self._run_job_company_flow(
            user_query=user_query,
            jd_text=jd_text,
            company_name=company_name,
            cv_text=cv_text,
        )

        job_experiences, job_company_result = await asyncio.gather(cv_task, job_company_task)
        (
            requirements,
            resolved_company,
            company_source,
            research_enabled,
            research_result,
            research_raw,
        ) = job_company_result

        return InterviewPrepResponse(
            user_job_experiences=UserJobExperiencesSection(
                cv_provided=bool(job_experiences),
                job_experiences=job_experiences,
            ),
            company_information=CompanyInformationSection(
                company_name=resolved_company,
                company_source=company_source,
                routing_reason=requirements.reason,
                company_research_enabled=research_enabled,
                core_products=research_result.core_products if research_result else [],
                top_products_brief=research_result.top_products_brief if research_result else [],
                ceo=research_result.ceo_profile if research_result else CEOProfile(),
                culture=research_result.culture if research_result else [],
                vision=research_result.vision if research_result else [],
                business_model=research_result.business_model if research_result else [],
            ),
            job_requirement=JobRequirementSection(
                scope_of_work=requirements.scope_of_work,
                key_qualifications=requirements.key_qualifications,
                tech_stacks=requirements.tech_stacks,
                jd_gaps_or_ambiguities=requirements.jd_gaps_or_ambiguities,
            ),
            answer=(
                "Planner extraction complete. Perplexity company research executed."
                if research_enabled
                else "Planner extraction complete. Company unresolved, skipped Perplexity company research."
            ),
            raw={
                "planner_decision": {
                    "company_name": resolved_company,
                    "company_source": company_source,
                    "requirements": requirements.model_dump(),
                },
                "company_research": research_raw,
            },
        )

    @timed("interview_prep.user_profile_flow")
    async def _run_user_profile_flow(self, cv_text: str | None) -> list[JobExperience]:
        if cv_text:
            return await self._cv_extraction_service.extract_job_experiences_from_text(cv_text)
        return await _empty_job_experiences()

    @timed("interview_prep.job_company_flow")
    async def _run_job_company_flow(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        cv_text: str | None,
    ) -> tuple:
        if company_name and company_name.strip():
            resolved_company = company_name.strip()
            company_source = "request"
        else:
            resolved_company, company_source = await asyncio.to_thread(
                self._planner_service.resolve_company,
                company_name,
                jd_text,
            )

        research_enabled = bool(resolved_company)
        requirements_task = asyncio.to_thread(
            self._planner_service.extract_job_requirements,
            user_query,
            jd_text,
            resolved_company,
            company_source,
            cv_text,
        )

        if research_enabled:
            research_task = asyncio.to_thread(
                self._company_research_service.research,
                resolved_company or "",
                company_source == "request",
            )
        else:
            research_task = _empty_company_research()

        requirements, research_output = await asyncio.gather(
            requirements_task,
            research_task,
        )

        research_result = None
        research_raw = None
        if research_enabled:
            research_result, research_raw = research_output

        return (
            requirements,
            resolved_company,
            company_source,
            research_enabled,
            research_result,
            research_raw,
        )


async def _empty_company_research() -> tuple[None, None]:
    return (None, None)


async def _empty_job_experiences() -> list[JobExperience]:
    return []
