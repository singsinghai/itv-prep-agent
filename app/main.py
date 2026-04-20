import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from app.config import settings
from app.models.interview_prep_response import InterviewPrepResponse
from app.services.company_research_service import CompanyResearchService
from app.services.artifact_export_service import ArtifactExportService
from app.services.cv_extraction_service import CVExtractionService
from app.services.document_parser_service import DocumentParserService
from app.services.interview_prep_service import InterviewPrepService
from app.services.planner_agent_service import PlannerAgentService
from app.utils.timing import timed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ITV Prep Agent API", version="1.0.0")
thread_pool: ThreadPoolExecutor | None = None

document_parser_service = DocumentParserService(settings)
cv_extraction_service = CVExtractionService(settings=settings)
planner_service = PlannerAgentService(settings)
company_research_service = CompanyResearchService(settings)
artifact_export_service = ArtifactExportService(output_root=settings.output_data_dir)
interview_prep_service = InterviewPrepService(
    planner_service=planner_service,
    company_research_service=company_research_service,
    cv_extraction_service=cv_extraction_service,
    artifact_export_service=artifact_export_service,
)


@app.on_event("startup")
async def configure_thread_pool() -> None:
    global thread_pool
    loop = asyncio.get_running_loop()
    thread_pool = ThreadPoolExecutor(max_workers=settings.max_thread_workers)
    loop.set_default_executor(thread_pool)
    logger.info("Configured default thread pool with max_workers=%d", settings.max_thread_workers)


@app.on_event("shutdown")
async def shutdown_thread_pool() -> None:
    global thread_pool
    if thread_pool:
        thread_pool.shutdown(wait=False, cancel_futures=False)
        thread_pool = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/interview-prep/query", response_model=InterviewPrepResponse)
@timed("endpoint.interview_prep_query")
async def interview_prep_query(
    query: str = Form(..., min_length=2),
    jd_file: UploadFile = File(...),
    cv_file: UploadFile | None = File(default=None),
    company_name: str | None = Form(default=None),
    user_id: str | None = Form(default=None),
) -> InterviewPrepResponse:
    try:
        jd_text, cv_text = await _parse_inputs_parallel(jd_file, cv_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process JD/CV file: {exc}") from exc

    try:
        return await _run_interview_prep_process(query, jd_text, company_name, cv_text, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Interview prep flow failed: {exc}") from exc


@timed("endpoint.parse_inputs_parallel")
async def _parse_inputs_parallel(
    jd_file: UploadFile,
    cv_file: UploadFile | None,
) -> tuple[str, str | None]:
    jd_task = document_parser_service.extract_text(jd_file, file_label="JD")
    cv_task = document_parser_service.extract_text(cv_file, file_label="CV") if cv_file is not None else _empty_cv_text()
    return await asyncio.gather(jd_task, cv_task)


@timed("endpoint.interview_prep_process")
async def _run_interview_prep_process(
    query: str,
    jd_text: str,
    company_name: str | None,
    cv_text: str | None,
    user_id: str | None,
) -> InterviewPrepResponse:
    return await interview_prep_service.process(
        user_query=query,
        jd_text=jd_text,
        company_name=company_name,
        cv_text=cv_text,
        user_id=user_id,
    )


async def _empty_cv_text() -> str | None:
    return None
