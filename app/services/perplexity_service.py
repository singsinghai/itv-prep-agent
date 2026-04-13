from typing import Any

from perplexity import Perplexity

from app.config import Settings


class PerplexitySearchService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def query(self, query: str, system_prompt: str | None) -> dict[str, Any]:
        if not self._settings.perplexity_api_key:
            raise ValueError("Missing PERPLEXITY_API_KEY environment variable")

        client = Perplexity(api_key=self._settings.perplexity_api_key)
        response = client.responses.create(
            preset=self._settings.perplexity_preset,
            input=query,
            instructions=system_prompt,
        )

        if hasattr(response, "model_dump"):
            raw = response.model_dump()
        elif isinstance(response, dict):
            raw = response
        else:
            raw = {"response": str(response)}

        answer = getattr(response, "output_text", None)
        if not answer:
            answer = str(raw.get("output_text", "")).strip()
        if not answer:
            raise ValueError("Unexpected response format from Perplexity SDK")

        return {"answer": answer, "raw": raw}
