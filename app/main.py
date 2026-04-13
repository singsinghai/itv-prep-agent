from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.config import settings
from app.models.query_response import QueryResponse
from app.services.perplexity_service import PerplexitySearchService

app = FastAPI(title="ITV Prep Agent API", version="1.0.0")

search_service = PerplexitySearchService(settings)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Question to search with Perplexity")
    system_prompt: str | None = Field(
        default="You are a helpful research assistant. Keep the answer concise.",
        description="Optional system instruction for Perplexity",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
async def query_perplexity(payload: QueryRequest) -> QueryResponse:
    try:
        result = search_service.query(payload.query, payload.system_prompt)
        return QueryResponse(answer=result["answer"], raw=result["raw"])
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Perplexity request failed: {exc}") from exc
