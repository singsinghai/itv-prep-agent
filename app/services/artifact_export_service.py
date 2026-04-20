import asyncio
import re
from pathlib import Path

from app.models.company_research import CompanyResearchResult
from app.models.cv_models import JobExperience
from app.models.planner_decision import InterviewStrategyExtraction, JobRequirementExtraction


class ArtifactExportService:
    def __init__(self, output_root: str) -> None:
        self._output_root = Path(output_root)

    async def resolve_user_folder(self, user_id: str | None, cv_text: str | None) -> Path:
        identifier = self._resolve_user_identifier(user_id=user_id, cv_text=cv_text)
        folder = self._output_root / identifier
        await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
        return folder

    async def write_user_profile_summary(self, user_folder: Path, job_experiences: list[JobExperience]) -> None:
        sections = ["# User Profile Summarization", ""]
        if not job_experiences:
            sections.extend(
                [
                    "CV was not provided or no job experiences were extracted.",
                    "",
                    "## Suggested Next Step",
                    "- Upload CV so project-level summary can be generated.",
                ]
            )
            await self._write_text(user_folder / "user_profile_summarization.md", "\n".join(sections))
            return

        sections.append("## Core Roles")
        for experience in job_experiences:
            company = f" @ {experience.company}" if experience.company else ""
            period = f" ({experience.period})" if experience.period else ""
            sections.append(f"- {experience.role}{company}{period}")

        sections.extend(["", "## Core Techniques"])
        seen_techniques: set[str] = set()
        for experience in job_experiences:
            for tech in experience.tech_stack:
                normalized = tech.strip()
                if not normalized:
                    continue
                key = normalized.lower()
                if key in seen_techniques:
                    continue
                seen_techniques.add(key)
                sections.append(f"- {normalized}")

        sections.extend(["", "## Project Highlights"])
        has_project = False
        for experience in job_experiences:
            for project in experience.projects:
                has_project = True
                sections.append(f"### {project.name}")
                if project.main_work:
                    sections.append("- Core Work:")
                    sections.extend([f"  - {item}" for item in project.main_work])
                if project.key_designs:
                    sections.append("- Core Designs:")
                    sections.extend([f"  - {item}" for item in project.key_designs])
                if project.key_improvements:
                    sections.append("- Core Improvements:")
                    sections.extend([f"  - {item}" for item in project.key_improvements])
                if project.notable_results:
                    sections.append("- Outputs:")
                    sections.extend([f"  - {item}" for item in project.notable_results])
                sections.append("")
        if not has_project:
            sections.append("- No structured project entries were extracted from CV.")

        await self._write_text(user_folder / "user_profile_summarization.md", "\n".join(sections).strip() + "\n")

    async def write_company_info_and_jd_brief(
        self,
        user_folder: Path,
        company_name: str | None,
        company_source: str,
        requirements: JobRequirementExtraction,
        company_research_enabled: bool,
        company_research: CompanyResearchResult | None,
    ) -> None:
        sections = [
            "# Company Info",
            "",
            f"- Company Name: {company_name or 'Unknown'}",
            f"- Company Source: {company_source}",
            f"- Company Research Enabled: {company_research_enabled}",
            "",
            "## JD Brief",
            "",
            "### Scope Of Work",
            *self._bullet_lines(requirements.scope_of_work, "- Not available."),
            "",
            "### Key Qualifications",
            *self._bullet_lines(requirements.key_qualifications, "- Not available."),
            "",
            "### Tech Stack",
            *self._bullet_lines(requirements.tech_stacks, "- Not available."),
            "",
            "### JD Gaps Or Ambiguities",
            *self._bullet_lines(requirements.jd_gaps_or_ambiguities, "- None identified."),
            "",
        ]

        sections.extend(["## Company Research", ""])
        if not company_research_enabled or company_research is None:
            sections.append("- Company research is unavailable for this request.")
        else:
            sections.extend(
                [
                    "### Core Products",
                    *self._bullet_lines(company_research.core_products, "- Not available."),
                    "",
                    "### Top Products Brief",
                    *self._bullet_lines(company_research.top_products_brief, "- Not available."),
                    "",
                    "### CEO",
                    f"- Name: {company_research.ceo_profile.name or 'Unknown'}",
                    f"- Founder/Cofounder: {company_research.ceo_profile.is_founder_or_cofounder}",
                    "- Main Background:",
                    *self._nested_bullet_lines(company_research.ceo_profile.main_background, "  - Not available."),
                    "- Publications Or Side Products:",
                    *self._nested_bullet_lines(
                        company_research.ceo_profile.publications_or_side_products,
                        "  - Not available.",
                    ),
                    "- Work And Contribution:",
                    *self._nested_bullet_lines(company_research.ceo_profile.work_and_contribution, "  - Not available."),
                    "",
                    "### Culture",
                    *self._bullet_lines(company_research.culture, "- Not available."),
                    "",
                    "### Vision",
                    *self._bullet_lines(company_research.vision, "- Not available."),
                    "",
                    "### Business Model",
                    *self._bullet_lines(company_research.business_model, "- Not available."),
                ]
            )

        await self._write_text(user_folder / "company_info_and_jd_brief.md", "\n".join(sections).strip() + "\n")

    async def write_interview_round_files(
        self,
        user_folder: Path,
        strategy: InterviewStrategyExtraction,
    ) -> None:
        for idx, stage in enumerate(strategy.stage_plans, start=1):
            slug = self._slugify(stage.stage_name) or f"round_{idx}"
            path = user_folder / f"round_{idx:02d}_{slug}.md"
            sections = [
                f"# {stage.stage_name}",
                "",
                "## Stage Objective",
                stage.stage_objective or "Not available.",
                "",
                "## Why This Matters For This Role",
                *self._bullet_lines(stage.why_this_matters_for_this_role, "- Not available."),
                "",
                "## Revision Roadmap",
                *self._bullet_lines(stage.revision_roadmap, "- Not available."),
                "",
                "## Expected Questions",
                *self._bullet_lines(stage.expected_questions, "- Not available."),
                "",
                "## Questions To Ask Interviewer",
                *self._bullet_lines(stage.questions_to_ask_interviewer, "- Not available."),
                "",
                "## Metadata",
                f"- interview_process_source: {strategy.interview_process_source}",
                f"- process_reason: {strategy.process_reason}",
            ]
            await self._write_text(path, "\n".join(sections))

    async def _write_text(self, path: Path, content: str) -> None:
        await asyncio.to_thread(path.write_text, content, "utf-8")

    def _resolve_user_identifier(self, user_id: str | None, cv_text: str | None) -> str:
        if user_id and user_id.strip():
            return self._sanitize_identifier(user_id.strip())

        if cv_text:
            github_match = re.search(r"github\.com/([A-Za-z0-9-]+)", cv_text, flags=re.IGNORECASE)
            if github_match:
                return self._sanitize_identifier(f"github_{github_match.group(1)}")

            email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", cv_text)
            if email_match:
                return self._sanitize_identifier(email_match.group(0))

            phone_match = re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", cv_text)
            if phone_match:
                digits = re.sub(r"\D", "", phone_match.group(0))
                if digits:
                    return self._sanitize_identifier(f"phone_{digits}")

        return "anonymous_user"

    def _sanitize_identifier(self, value: str) -> str:
        cleaned = value.strip().lower()
        cleaned = re.sub(r"[^a-z0-9._-]+", "_", cleaned)
        cleaned = cleaned.strip("._-")
        if not cleaned:
            return "anonymous_user"
        return cleaned[:80]

    def _slugify(self, value: str) -> str:
        return self._sanitize_identifier(value).replace(".", "_")

    def _bullet_lines(self, items: list[str], fallback: str) -> list[str]:
        if items:
            return [f"- {item}" for item in items]
        return [fallback]

    def _nested_bullet_lines(self, items: list[str], fallback: str) -> list[str]:
        if items:
            return [f"  - {item}" for item in items]
        return [fallback]
