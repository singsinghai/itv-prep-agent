import logging

from perplexity import Perplexity
from pydantic import BaseModel, Field

from app.config import Settings
from app.models.company_research import CompanyResearchResult
from app.utils.timing import timed


class CompanyResearchExtraction(BaseModel):
    core_products: list[str] = Field(default_factory=list)
    ceo: str | None = None
    culture: list[str] = Field(default_factory=list)


class CompanyResearchService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    @timed("company_research.research")
    def research(self, company_name: str) -> tuple[CompanyResearchResult, dict]:
        if not self._settings.perplexity_api_key:
            raise ValueError("Missing PERPLEXITY_API_KEY environment variable for company research")

        response = self._call_perplexity(company_name)

        output_text = getattr(response, "output_text", "") or ""
        raw = response.model_dump() if hasattr(response, "model_dump") else {"response": str(response)}

        if not self._settings.openai_api_key:
            fallback = CompanyResearchResult(
                core_products=[output_text[:2000]] if output_text else [],
                ceo=None,
                culture=[],
            )
            return fallback, raw

        extracted = self._structure_company_research(company_name, output_text)

        return (
            CompanyResearchResult(
                core_products=extracted.core_products,
                ceo=extracted.ceo,
                culture=extracted.culture,
            ),
            raw,
        )

    @timed("company_research.perplexity_call")
    def _call_perplexity(self, company_name: str):
        client = Perplexity(api_key=self._settings.perplexity_api_key)
        prompt = (
            f"Research company: {company_name}. "
            "Return concise facts on: (1) core products/services, (2) current CEO, (3) engineering/work culture."
        )
        try:
            return client.responses.create(
                model=f"openai/{self._settings.openai_large_model}",
                preset=self._settings.perplexity_model,
                input=prompt,
                tools=[{"type": "web_search"}],
            )
        except Exception as exc:
            raise ValueError(f"Failed to call Perplexity: {exc}") from exc

    @timed("company_research.structure_with_llm")
    def _structure_company_research(self, company_name: str, output_text: str) -> CompanyResearchExtraction:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract structured company research results. Keep outputs concise and factual.",
                ),
                ("human", "Company: {company_name}\n\nResearch notes:\n{notes}"),
            ]
        )
        llm = ChatOpenAI(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_large_model,
            temperature=0,
        )
        chain = prompt | llm.with_structured_output(CompanyResearchExtraction)
        return chain.invoke(
            {
                "company_name": company_name,
                "notes": output_text[: self._settings.max_research_chars],
            }
        )
