import logging
import re

from perplexity import Perplexity
from pydantic import BaseModel, Field

from app.config import Settings
from app.models.company_research import CEOProfile, CompanyResearchResult
from app.utils.timing import timed


class CompanyResearchExtraction(BaseModel):
    referenced_company_name: str | None = None
    exact_company_match: bool | None = None
    core_products: list[str] = Field(default_factory=list)
    top_products_brief: list[str] = Field(default_factory=list)
    ceo_name: str | None = None
    ceo_is_founder_or_cofounder: bool | None = None
    ceo_main_background: list[str] = Field(default_factory=list)
    ceo_publications_or_side_products: list[str] = Field(default_factory=list)
    ceo_work_and_contribution: list[str] = Field(default_factory=list)
    culture: list[str] = Field(default_factory=list)
    vision: list[str] = Field(default_factory=list)
    business_model: list[str] = Field(default_factory=list)


class CompanyResearchService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    @timed("company_research.research")
    def research(self, company_name: str, enforce_exact_name: bool = False) -> tuple[CompanyResearchResult, dict]:
        if not self._settings.perplexity_api_key:
            raise ValueError("Missing PERPLEXITY_API_KEY environment variable for company research")

        response = self._call_perplexity(company_name, enforce_exact_name=enforce_exact_name)

        output_text = getattr(response, "output_text", "") or ""
        raw = response.model_dump() if hasattr(response, "model_dump") else {"response": str(response)}
        top_results = self._extract_top_search_results(raw=raw, company_name=company_name, top_k=5)
        self._shrink_raw_search_results(raw=raw, filtered_results=top_results)
        research_notes = self._build_research_notes(output_text=output_text, top_results=top_results)

        if not self._settings.openai_api_key:
            fallback = CompanyResearchResult(
                core_products=[research_notes[:2000]] if research_notes else [],
                top_products_brief=[],
                ceo_profile=CEOProfile(),
                culture=[],
                vision=[],
                business_model=[],
            )
            return fallback, raw

        extracted = self._structure_company_research(company_name, research_notes)
        exact_match = self._is_exact_company_match(company_name, extracted.referenced_company_name, extracted.exact_company_match)

        if enforce_exact_name and not exact_match:
            self._logger.warning(
                "Company research mismatch for exact name '%s' (referenced: '%s'). Returning empty research.",
                company_name,
                extracted.referenced_company_name,
            )
            return (
                CompanyResearchResult(
                    core_products=[],
                    top_products_brief=[],
                    ceo_profile=CEOProfile(),
                    culture=[],
                    vision=[],
                    business_model=[],
                ),
                {
                    **raw,
                    "exact_company_match": False,
                    "referenced_company_name": extracted.referenced_company_name,
                },
            )

        return (
            CompanyResearchResult(
                core_products=extracted.core_products,
                top_products_brief=extracted.top_products_brief,
                ceo_profile=CEOProfile(
                    name=extracted.ceo_name,
                    is_founder_or_cofounder=extracted.ceo_is_founder_or_cofounder,
                    main_background=extracted.ceo_main_background,
                    publications_or_side_products=extracted.ceo_publications_or_side_products,
                    work_and_contribution=extracted.ceo_work_and_contribution,
                ),
                culture=extracted.culture,
                vision=extracted.vision,
                business_model=extracted.business_model,
            ),
            raw,
        )

    @timed("company_research.perplexity_call")
    def _call_perplexity(self, company_name: str, enforce_exact_name: bool = False):
        client = Perplexity(api_key=self._settings.perplexity_api_key)
        exact_clause = (
            f"Treat '{company_name}' as immutable exact company name (lower/upper case allowed); do not autocorrect or substitute similar names. "
            "If exact match evidence is weak, say so explicitly."
            if enforce_exact_name
            else ""
        )
        prompt = (
            f"Research company: {company_name}. "
            f"{exact_clause} "
            "Return concise facts on: "
            "(1) core products/services, "
            "(1b) brief summary for top products, "
            "(2) current CEO including if founder/cofounder, main background, publications or side products, "
            "(2b) CEO's main work and contribution to the company, "
            "(3) engineering/work culture, "
            "(4) company vision, "
            "(5) business model."
        ).strip()
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
                    "Extract structured company research results. Keep outputs concise and factual.\n"
                    "For CEO fields, use null/empty when not available. Do not guess.\n"
                    "For top_products_brief and ceo_work_and_contribution, keep each bullet very short and practical.",
                ),
                (
                    "human",
                    "Company (source of truth): {company_name}\n\n"
                    "Research notes:\n{notes}\n\n"
                    "Set exact_company_match=true only if notes clearly refer to the same exact company name.",
                ),
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

    def _is_exact_company_match(
        self,
        source_company_name: str,
        referenced_company_name: str | None,
        model_flag: bool | None,
    ) -> bool:
        if model_flag is False:
            return False
        if not referenced_company_name:
            return model_flag is not False
        return self._normalize(source_company_name) == self._normalize(referenced_company_name)

    def _extract_top_search_results(self, raw: dict, company_name: str, top_k: int) -> list[dict]:
        output_blocks = raw.get("output", [])
        if not isinstance(output_blocks, list):
            return []

        all_results: list[dict] = []
        for block in output_blocks:
            if not isinstance(block, dict):
                continue
            results = block.get("results")
            if isinstance(results, list):
                all_results.extend([r for r in results if isinstance(r, dict)])

        if not all_results:
            return []

        scored = [(self._score_result(r, company_name), r) for r in all_results]
        scored.sort(key=lambda item: item[0], reverse=True)

        deduped: list[dict] = []
        seen_urls: set[str] = set()
        for score, result in scored:
            if score <= 0:
                continue
            url = str(result.get("url", ""))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(result)
            if len(deduped) >= top_k:
                break

        if deduped:
            return deduped
        return [r for _, r in scored[:top_k]]

    def _score_result(self, result: dict, company_name: str) -> int:
        company_norm = self._normalize(company_name)
        text_blob = " ".join(
            [
                str(result.get("title", "")),
                str(result.get("snippet", "")),
                str(result.get("url", "")),
            ]
        )
        text_norm = self._normalize(text_blob)
        score = 0
        if company_norm and company_norm in text_norm:
            score += 100

        first_token = re.split(r"[^a-zA-Z0-9]+", company_name.strip().lower())[0] if company_name.strip() else ""
        if first_token and first_token in text_blob.lower():
            score += 20

        if "linkedin.com/company" in str(result.get("url", "")).lower():
            score += 5
        if "crunchbase.com/organization" in str(result.get("url", "")).lower():
            score += 5
        if "wikipedia.org" in str(result.get("url", "")).lower():
            score += 2
        return score

    def _shrink_raw_search_results(self, raw: dict, filtered_results: list[dict]) -> None:
        output_blocks = raw.get("output")
        if not isinstance(output_blocks, list):
            return

        first_results_set = False
        for block in output_blocks:
            if not isinstance(block, dict) or "results" not in block:
                continue
            if not first_results_set:
                block["results"] = filtered_results
                first_results_set = True
            else:
                block["results"] = []
        raw["company_search_top_results"] = filtered_results

    def _build_research_notes(self, output_text: str, top_results: list[dict]) -> str:
        if not top_results:
            return output_text

        lines = [output_text.strip()] if output_text.strip() else []
        lines.append("Top matched sources:")
        for idx, result in enumerate(top_results, start=1):
            title = str(result.get("title", "")).strip()
            snippet = str(result.get("snippet", "")).strip()
            url = str(result.get("url", "")).strip()
            lines.append(f"{idx}. {title}")
            if snippet:
                lines.append(f"   {snippet[:500]}")
            if url:
                lines.append(f"   {url}")
        return "\n".join(lines).strip()

    @staticmethod
    def _normalize(text: str) -> str:
        import re

        return re.sub(r"[^a-z0-9]+", "", text.lower())
