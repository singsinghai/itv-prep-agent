from pydantic import BaseModel, Field


class InterviewStagePlan(BaseModel):
    stage_name: str = Field(..., description="Interview stage name.")
    stage_objective: str = Field(
        ...,
        description="Why this stage exists and what interviewers evaluate.",
    )
    why_this_matters_for_this_role: list[str] = Field(
        default_factory=list,
        description="Role-specific rationale tied to JD and candidate profile.",
    )
    revision_roadmap: list[str] = Field(
        default_factory=list,
        description="Targeted revision items grounded in JD + CV experience.",
    )
    expected_questions: list[str] = Field(
        default_factory=list,
        description="Likely interviewer questions for this stage.",
    )
    questions_to_ask_interviewer: list[str] = Field(
        default_factory=list,
        description="Thoughtful candidate questions to ask at this stage.",
    )


class InterviewStrategyExtraction(BaseModel):
    interview_process_source: str = Field(
        ...,
        description=(
            "Use 'jd' when interview stages are clearly mentioned in JD; "
            "otherwise use 'default'."
        ),
    )
    process_reason: str = Field(
        ...,
        description="Short reason why source is jd/default.",
    )
    stage_plans: list[InterviewStagePlan] = Field(
        default_factory=list,
        description="Ordered stage-by-stage preparation plan.",
    )


class JobRequirementExtraction(BaseModel):
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
    interview_strategy: InterviewStrategyExtraction = Field(
        ...,
        description=(
            "Interview preparation roadmap with stage plans grounded in JD and CV."
        ),
    )
