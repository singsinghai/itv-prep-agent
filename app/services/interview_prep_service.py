from app.models.cv_models import JobExperience
from app.models.interview_prep_response import InterviewPrepResponse
from app.services.company_research_draft_service import CompanyResearchDraftService
from app.services.planner_agent_service import PlannerAgentService


class InterviewPrepService:
    def __init__(
        self,
        planner_service: PlannerAgentService,
        company_research_draft_service: CompanyResearchDraftService,
    ) -> None:
        self._planner_service = planner_service
        self._company_research_draft_service = company_research_draft_service

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
        next_steps = self._company_research_draft_service.draft_next_steps(decision.company_name)

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
            next_step_plan=next_steps,
            answer="Planner extraction complete. Post-planner company research is drafted but not executed.",
            raw={"planner_decision": decision.model_dump()},
        )
