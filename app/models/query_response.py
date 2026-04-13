from typing import Any

from pydantic import BaseModel


class QueryResponse(BaseModel):
    answer: str
    raw: dict[str, Any]
