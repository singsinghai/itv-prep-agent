from typing import Literal

from pydantic import BaseModel, Field


class PlannerDecision(BaseModel):
    company_name: str | None = Field(
        default=None,
        description="Resolved target company name when available.",
    )
    company_source: Literal["request", "jd", "unknown"] = Field(
        ...,
        description="Where the company name came from.",
    )
    reason: str = Field(..., description="Short explanation of planning assumptions.")
    scope_of_work: list[str] = Field(
        default_factory=list,
        description="Extracted responsibilities/scope from JD.",
    )
    key_qualifications: list[str] = Field(
        default_factory=list,
        description="Extracted qualifications from JD.",
    )
    tech_stacks: list[str] = Field(
        default_factory=list,
        description="Extracted tools, frameworks, and technologies in JD.",
    )
    jd_gaps_or_ambiguities: list[str] = Field(
        default_factory=list,
        description="Unclear/missing JD details that later stages may need to enrich.",
    )
