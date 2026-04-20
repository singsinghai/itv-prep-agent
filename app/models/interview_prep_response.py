from typing import Any

from pydantic import BaseModel

from app.models.company_research import CEOProfile
from app.models.cv_models import JobExperience


class UserJobExperiencesSection(BaseModel):
    cv_provided: bool
    job_experiences: list[JobExperience]


class CompanyInformationSection(BaseModel):
    company_name: str | None
    company_source: str
    routing_reason: str
    company_research_enabled: bool
    core_products: list[str]
    top_products_brief: list[str]
    ceo: CEOProfile
    culture: list[str]
    vision: list[str]
    business_model: list[str]


class JobRequirementSection(BaseModel):
    scope_of_work: list[str]
    key_qualifications: list[str]
    tech_stacks: list[str]
    jd_gaps_or_ambiguities: list[str]


class InterviewStageStrategySection(BaseModel):
    stage_name: str
    stage_objective: str
    why_this_matters_for_this_role: list[str]
    revision_roadmap: list[str]
    expected_questions: list[str]
    questions_to_ask_interviewer: list[str]


class InterviewStrategySection(BaseModel):
    interview_process_source: str
    process_reason: str
    stage_plans: list[InterviewStageStrategySection]


class InterviewPrepResponse(BaseModel):
    user_job_experiences: UserJobExperiencesSection
    company_information: CompanyInformationSection
    job_requirement: JobRequirementSection
    interview_strategy: InterviewStrategySection
    answer: str | None = None
    raw: dict[str, Any] | None = None
