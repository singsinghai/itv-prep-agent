import logging

from app.models.cv_models import JobExperience
from app.models.interview_prep_response import InterviewPrepResponse
from app.services.company_research_service import CompanyResearchService
from app.services.planner_agent_service import PlannerAgentService
from app.utils.timing import timed


class InterviewPrepService:
    def __init__(
        self,
        planner_service: PlannerAgentService,
        company_research_service: CompanyResearchService,
    ) -> None:
        self._planner_service = planner_service
        self._company_research_service = company_research_service
        self._logger = logging.getLogger(__name__)

    @timed("interview_prep.process")
    def process(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        job_experiences: list[JobExperience],
    ) -> InterviewPrepResponse:
        decision = self._planner_service.plan(
            user_query=user_query,
            jd_text=jd_text,
            company_name=company_name,
            job_experiences=job_experiences,
        )

        research_enabled = bool(decision.company_name)
        research_result = None
        research_raw = None
        if research_enabled:
            research_result, research_raw = self._company_research_service.research(decision.company_name or "")

        return InterviewPrepResponse(
            company_name=decision.company_name,
            company_source=decision.company_source,
            routing_reason=decision.reason,
            cv_provided=bool(job_experiences),
            job_experiences=job_experiences,
            scope_of_work=decision.scope_of_work,
            key_qualifications=decision.key_qualifications,
            tech_stacks=decision.tech_stacks,
            jd_gaps_or_ambiguities=decision.jd_gaps_or_ambiguities,
            core_products=research_result.core_products if research_result else [],
            ceo=research_result.ceo if research_result else None,
            culture=research_result.culture if research_result else [],
            company_research_enabled=research_enabled,
            answer=(
                "Planner extraction complete. Perplexity company research executed."
                if research_enabled
                else "Planner extraction complete. Company unresolved, skipped Perplexity company research."
            ),
            raw={
                "planner_decision": decision.model_dump(),
                "company_research": research_raw,
            },
        )
