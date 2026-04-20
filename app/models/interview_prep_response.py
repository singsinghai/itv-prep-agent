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


class InterviewPrepResponse(BaseModel):
    user_job_experiences: UserJobExperiencesSection
    company_information: CompanyInformationSection
    job_requirement: JobRequirementSection
    answer: str | None = None
    raw: dict[str, Any] | None = None
