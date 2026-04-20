from typing import Any

from pydantic import BaseModel

from app.models.cv_models import JobExperience


class InterviewPrepResponse(BaseModel):
    company_name: str | None
    company_source: str
    routing_reason: str
    cv_provided: bool
    job_experiences: list[JobExperience]
    scope_of_work: list[str]
    key_qualifications: list[str]
    tech_stacks: list[str]
    jd_gaps_or_ambiguities: list[str]
    next_step_plan: list[str]
    answer: str | None = None
    raw: dict[str, Any] | None = None
