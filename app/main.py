import asyncio

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from app.config import settings
from app.models.cv_models import JobExperience
from app.models.interview_prep_response import InterviewPrepResponse
from app.services.company_research_draft_service import CompanyResearchDraftService
from app.services.cv_extraction_service import CVExtractionService
from app.services.document_parser_service import DocumentParserService
from app.services.interview_prep_service import InterviewPrepService
from app.services.planner_agent_service import PlannerAgentService

app = FastAPI(title="ITV Prep Agent API", version="1.0.0")

document_parser_service = DocumentParserService(settings)
cv_extraction_service = CVExtractionService(settings=settings, document_parser=document_parser_service)
planner_service = PlannerAgentService(settings)
company_research_draft_service = CompanyResearchDraftService()
interview_prep_service = InterviewPrepService(
    planner_service=planner_service,
    company_research_draft_service=company_research_draft_service,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/interview-prep/query", response_model=InterviewPrepResponse)
async def interview_prep_query(
    query: str = Form(..., min_length=2),
    jd_file: UploadFile = File(...),
    cv_file: UploadFile | None = File(default=None),
    company_name: str | None = Form(default=None),
) -> InterviewPrepResponse:
    try:
        jd_task = document_parser_service.extract_text(jd_file, file_label="JD")
        cv_task = (
            cv_extraction_service.extract_job_experiences(cv_file)
            if cv_file is not None
            else _empty_job_experiences()
        )
        jd_text, job_experiences = await asyncio.gather(jd_task, cv_task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process JD/CV file: {exc}") from exc

    try:
        return interview_prep_service.process(
            user_query=query,
            jd_text=jd_text,
            company_name=company_name,
            job_experiences=job_experiences,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview prep flow failed: {exc}") from exc


async def _empty_job_experiences() -> list[JobExperience]:
    return []
