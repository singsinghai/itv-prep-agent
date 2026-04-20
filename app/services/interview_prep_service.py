import logging
import asyncio
from pathlib import Path

from app.models.company_research import CEOProfile, CompanyResearchResult
from app.models.cv_models import JobExperience
from app.models.interview_prep_response import (
    CompanyInformationSection,
    InterviewStageStrategySection,
    InterviewStrategySection,
    InterviewPrepResponse,
    JobRequirementSection,
    UserJobExperiencesSection,
)
from app.models.planner_decision import JobRequirementExtraction
from app.services.artifact_export_service import ArtifactExportService
from app.services.cv_extraction_service import CVExtractionService
from app.services.company_research_service import CompanyResearchService
from app.services.planner_agent_service import PlannerAgentService
from app.utils.timing import timed


class InterviewPrepService:
    def __init__(
        self,
        planner_service: PlannerAgentService,
        company_research_service: CompanyResearchService,
        cv_extraction_service: CVExtractionService,
        artifact_export_service: ArtifactExportService,
    ) -> None:
        self._planner_service = planner_service
        self._company_research_service = company_research_service
        self._cv_extraction_service = cv_extraction_service
        self._artifact_export_service = artifact_export_service
        self._logger = logging.getLogger(__name__)

    @timed("interview_prep.process")
    async def process(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        cv_text: str | None,
        user_id: str | None,
    ) -> InterviewPrepResponse:
        user_folder = await self._artifact_export_service.resolve_user_folder(
            user_id=user_id,
            cv_text=cv_text,
        )
        cv_task = asyncio.create_task(self._run_user_profile_flow(cv_text))
        job_company_task = asyncio.create_task(
            self._run_job_company_flow(
                user_query=user_query,
                jd_text=jd_text,
                company_name=company_name,
                cv_text=cv_text,
            )
        )
        task_map = {
            cv_task: "cv",
            job_company_task: "job_company",
        }

        job_experiences: list[JobExperience] = []
        job_company_result: tuple | None = None

        while task_map:
            done, _ = await asyncio.wait(task_map.keys(), return_when=asyncio.FIRST_COMPLETED)
            for done_task in done:
                task_type = task_map.pop(done_task)
                result = done_task.result()
                if task_type == "cv":
                    job_experiences = result
                    await self._write_user_profile_component(
                        user_folder=user_folder,
                        job_experiences=job_experiences,
                    )
                    continue

                job_company_result = result
                (
                    requirements_partial,
                    resolved_company_partial,
                    company_source_partial,
                    research_enabled_partial,
                    research_result_partial,
                    _,
                ) = job_company_result
                await self._write_company_component(
                    user_folder=user_folder,
                    company_name=resolved_company_partial,
                    company_source=company_source_partial,
                    requirements=requirements_partial,
                    company_research_enabled=research_enabled_partial,
                    company_research=research_result_partial,
                )

        if job_company_result is None:
            raise RuntimeError("Job/company planning task did not produce a result")

        (
            requirements,
            resolved_company,
            company_source,
            research_enabled,
            research_result,
            research_raw,
        ) = job_company_result

        requirements = await self._enrich_strategy_from_extracted_experiences(
            user_query=user_query,
            jd_text=jd_text,
            resolved_company=resolved_company,
            company_source=company_source,
            requirements=requirements,
            job_experiences=job_experiences,
        )
        await self._write_interview_round_components(
            user_folder=user_folder,
            requirements=requirements,
        )

        return InterviewPrepResponse(
            user_job_experiences=UserJobExperiencesSection(
                cv_provided=bool(job_experiences),
                job_experiences=job_experiences,
            ),
            company_information=CompanyInformationSection(
                company_name=resolved_company,
                company_source=company_source,
                routing_reason=requirements.reason,
                company_research_enabled=research_enabled,
                core_products=research_result.core_products if research_result else [],
                top_products_brief=research_result.top_products_brief if research_result else [],
                ceo=research_result.ceo_profile if research_result else CEOProfile(),
                culture=research_result.culture if research_result else [],
                vision=research_result.vision if research_result else [],
                business_model=research_result.business_model if research_result else [],
            ),
            job_requirement=JobRequirementSection(
                scope_of_work=requirements.scope_of_work,
                key_qualifications=requirements.key_qualifications,
                tech_stacks=requirements.tech_stacks,
                jd_gaps_or_ambiguities=requirements.jd_gaps_or_ambiguities,
            ),
            interview_strategy=InterviewStrategySection(
                interview_process_source=requirements.interview_strategy.interview_process_source,
                process_reason=requirements.interview_strategy.process_reason,
                stage_plans=[
                    InterviewStageStrategySection(
                        stage_name=stage.stage_name,
                        stage_objective=stage.stage_objective,
                        why_this_matters_for_this_role=stage.why_this_matters_for_this_role,
                        revision_roadmap=stage.revision_roadmap,
                        expected_questions=stage.expected_questions,
                        questions_to_ask_interviewer=stage.questions_to_ask_interviewer,
                    )
                    for stage in requirements.interview_strategy.stage_plans
                ],
            ),
            answer=(
                "Planner extraction complete. Perplexity company research executed."
                if research_enabled
                else "Planner extraction complete. Company unresolved, skipped Perplexity company research."
            ),
            raw={
                "planner_decision": {
                    "company_name": resolved_company,
                    "company_source": company_source,
                    "requirements": requirements.model_dump(),
                },
                "company_research": research_raw,
                "artifact_exports": {
                    "user_folder": str(user_folder),
                },
            },
        )

    @timed("interview_prep.user_profile_flow")
    async def _run_user_profile_flow(self, cv_text: str | None) -> list[JobExperience]:
        if cv_text:
            return await self._cv_extraction_service.extract_job_experiences_from_text(cv_text)
        return await _empty_job_experiences()

    @timed("interview_prep.job_company_flow")
    async def _run_job_company_flow(
        self,
        user_query: str,
        jd_text: str,
        company_name: str | None,
        cv_text: str | None,
    ) -> tuple:
        if company_name and company_name.strip():
            resolved_company = company_name.strip()
            company_source = "request"
        else:
            resolved_company, company_source = await asyncio.to_thread(
                self._planner_service.resolve_company,
                company_name,
                jd_text,
            )

        research_enabled = bool(resolved_company)
        requirements_task = asyncio.to_thread(
            self._planner_service.extract_job_requirements,
            user_query,
            jd_text,
            resolved_company,
            company_source,
            cv_text,
        )

        if research_enabled:
            research_task = asyncio.to_thread(
                self._company_research_service.research,
                resolved_company or "",
                company_source == "request",
            )
        else:
            research_task = _empty_company_research()

        requirements, research_output = await asyncio.gather(
            requirements_task,
            research_task,
        )

        research_result = None
        research_raw = None
        if research_enabled:
            research_result, research_raw = research_output

        return (
            requirements,
            resolved_company,
            company_source,
            research_enabled,
            research_result,
            research_raw,
        )

    @timed("interview_prep.enrich_strategy_from_extracted_experiences")
    async def _enrich_strategy_from_extracted_experiences(
        self,
        user_query: str,
        jd_text: str,
        resolved_company: str | None,
        company_source: str,
        requirements: JobRequirementExtraction,
        job_experiences: list[JobExperience],
    ) -> JobRequirementExtraction:
        try:
            enriched_strategy = await asyncio.to_thread(
                self._planner_service.enrich_interview_strategy,
                user_query,
                jd_text,
                resolved_company,
                company_source,
                requirements,
                job_experiences,
            )
            requirements.interview_strategy = enriched_strategy
        except Exception as exc:
            self._logger.warning(
                "Failed to enrich interview strategy with extracted experiences; fallback to base strategy. error=%s",
                exc,
            )
        return requirements

    async def _write_user_profile_component(
        self,
        user_folder: Path,
        job_experiences: list[JobExperience],
    ) -> None:
        try:
            await self._artifact_export_service.write_user_profile_summary(
                user_folder=user_folder,
                job_experiences=job_experiences,
            )
        except Exception as exc:
            self._logger.warning("Failed writing user profile summary markdown. error=%s", exc)

    async def _write_company_component(
        self,
        user_folder: Path,
        company_name: str | None,
        company_source: str,
        requirements: JobRequirementExtraction,
        company_research_enabled: bool,
        company_research: CompanyResearchResult | None,
    ) -> None:
        try:
            await self._artifact_export_service.write_company_info_and_jd_brief(
                user_folder=user_folder,
                company_name=company_name,
                company_source=company_source,
                requirements=requirements,
                company_research_enabled=company_research_enabled,
                company_research=company_research,
            )
        except Exception as exc:
            self._logger.warning("Failed writing company and JD markdown. error=%s", exc)

    async def _write_interview_round_components(
        self,
        user_folder: Path,
        requirements: JobRequirementExtraction,
    ) -> None:
        try:
            await self._artifact_export_service.write_interview_round_files(
                user_folder=user_folder,
                strategy=requirements.interview_strategy,
            )
        except Exception as exc:
            self._logger.warning("Failed writing interview round markdown files. error=%s", exc)


async def _empty_company_research() -> tuple[None, None]:
    return (None, None)


async def _empty_job_experiences() -> list[JobExperience]:
    return []
