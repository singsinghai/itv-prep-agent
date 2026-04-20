from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from fastapi import UploadFile
from pydantic import BaseModel, Field
import logging

from app.config import Settings
from app.models.cv_models import JobExperience
from app.services.document_parser_service import DocumentParserService
from app.utils.timing import timed


class CVExtractionResult(BaseModel):
    job_experiences: list[JobExperience] = Field(default_factory=list)


class CVExtractionService:
    def __init__(self, settings: Settings, document_parser: DocumentParserService) -> None:
        self._settings = settings
        self._document_parser = document_parser
        self._logger = logging.getLogger(__name__)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Extract structured work experiences from a candidate CV.\n"
                    "Return job experiences sorted from most recent to oldest.\n"
                    "For each experience, extract role, company (if available), period, tech stack, and projects.\n"
                    "Each project should include main_work, key_improvements, key_designs, and notable_results when available.\n"
                    "Do not hallucinate missing data.",
                ),
                ("human", "CV content:\n{cv_text}"),
            ]
        )

    @timed("cv_extraction.extract_job_experiences")
    async def extract_job_experiences(self, cv_file: UploadFile) -> list[JobExperience]:
        if not self._settings.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable for CV extraction")

        cv_text = await self._document_parser.extract_text(cv_file, file_label="CV")
        if not cv_text.strip():
            return []

        llm = ChatOpenAI(
            api_key=self._settings.openai_api_key,
            model=self._settings.openai_small_model,
            temperature=0,
        )
        chain = self._prompt | llm.with_structured_output(CVExtractionResult)
        result = chain.invoke({"cv_text": cv_text[: self._settings.max_cv_chars]})
        return result.job_experiences
