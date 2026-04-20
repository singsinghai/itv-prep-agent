from pydantic import BaseModel, Field


class CEOProfile(BaseModel):
    name: str | None = None
    is_founder_or_cofounder: bool | None = None
    main_background: list[str] = Field(default_factory=list)
    publications_or_side_products: list[str] = Field(default_factory=list)
    work_and_contribution: list[str] = Field(default_factory=list)


class CompanyResearchResult(BaseModel):
    core_products: list[str] = Field(default_factory=list)
    top_products_brief: list[str] = Field(default_factory=list)
    ceo_profile: CEOProfile = Field(default_factory=CEOProfile)
    culture: list[str] = Field(default_factory=list)
    vision: list[str] = Field(default_factory=list)
    business_model: list[str] = Field(default_factory=list)
