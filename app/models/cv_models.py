from pydantic import BaseModel, Field


class Project(BaseModel):
    name: str = Field(..., description="Project name or short identifier.")
    main_work: list[str] = Field(
        default_factory=list,
        description="Core implementation work delivered by the candidate.",
    )
    key_improvements: list[str] = Field(
        default_factory=list,
        description="Notable performance, quality, or product improvements achieved.",
    )
    key_designs: list[str] = Field(
        default_factory=list,
        description="Important architecture or design decisions made by the candidate.",
    )
    notable_results: list[str] = Field(
        default_factory=list,
        description="Outcome metrics or other impactful results.",
    )


class JobExperience(BaseModel):
    role: str = Field(..., description="Role title for this experience item.")
    company: str | None = Field(default=None, description="Company name, if available.")
    period: str | None = Field(default=None, description="Date period text from CV.")
    tech_stack: list[str] = Field(
        default_factory=list,
        description="Technologies used in this role.",
    )
    projects: list[Project] = Field(
        default_factory=list,
        description="Projects delivered under this role.",
    )
