import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_large_model: str
    openai_small_model: str
    perplexity_api_key: str | None
    perplexity_model: str
    max_jd_chars: int
    max_cv_chars: int
    max_research_chars: int


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_large_model=os.getenv("OPENAI_LARGE_MODEL", "gpt-4.1-mini"),
        openai_small_model=os.getenv("OPENAI_SMALL_MODEL", "gpt-4.1-mini"),
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        max_jd_chars=int(os.getenv("MAX_JD_CHARS", "4000")),
        max_cv_chars=int(os.getenv("MAX_CV_CHARS", "6000")),
        max_research_chars=int(os.getenv("MAX_RESEARCH_CHARS", "8000")),
    )


settings = load_settings()
