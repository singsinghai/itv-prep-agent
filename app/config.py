import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_planner_model: str
    openai_cv_extractor_model: str
    max_jd_chars: int
    max_cv_chars: int


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_planner_model=os.getenv("OPENAI_PLANNER_MODEL", "gpt-4.1-mini"),
        openai_cv_extractor_model=os.getenv("OPENAI_CV_EXTRACTOR_MODEL", "gpt-4.1-mini"),
        max_jd_chars=int(os.getenv("MAX_JD_CHARS", "4000")),
        max_cv_chars=int(os.getenv("MAX_CV_CHARS", "6000")),
    )


settings = load_settings()
