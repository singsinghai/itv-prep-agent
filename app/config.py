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
    max_thread_workers: int
    output_data_dir: str


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_large_model=os.getenv("OPENAI_LARGE_MODEL", "gpt-5.4"),
        openai_small_model=os.getenv("OPENAI_SMALL_MODEL", "gpt-5.4-mini"),
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "pro-search"),
        max_jd_chars=int(os.getenv("MAX_JD_CHARS", "4000")),
        max_cv_chars=int(os.getenv("MAX_CV_CHARS", "6000")),
        max_research_chars=int(os.getenv("MAX_RESEARCH_CHARS", "8000")),
        max_thread_workers=int(os.getenv("MAX_THREAD_WORKERS", "32")),
        output_data_dir=os.getenv("OUTPUT_DATA_DIR", "data"),
    )


settings = load_settings()
