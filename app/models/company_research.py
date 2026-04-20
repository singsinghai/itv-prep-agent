from pydantic import BaseModel, Field


class CompanyResearchResult(BaseModel):
    core_products: list[str] = Field(default_factory=list)
    ceo: str | None = None
    culture: list[str] = Field(default_factory=list)
