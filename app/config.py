import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    perplexity_api_key: str | None
    perplexity_preset: str


def load_settings() -> Settings:
    return Settings(
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        perplexity_preset=os.getenv("PERPLEXITY_PRESET", "pro-search"),
    )


settings = load_settings()
