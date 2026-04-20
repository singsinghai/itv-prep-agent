# itv-prep-agent

`itv-prep-agent` is a FastAPI service that turns a job description + candidate profile into a practical, senior-level interview preparation package.

It combines:
- JD requirement extraction
- Company research
- CV experience extraction
- Stage-by-stage interview strategy generation
- Progressive markdown exports per component (so users can read results early)

## What this app does

Given a query and JD input, the app generates:
- `user_job_experiences`: structured candidate experiences/projects from CV
- `company_information`: company + CEO + culture/vision/business model research
- `job_requirement`: scope, qualifications, tech stack, JD ambiguities
- `interview_strategy`: stage plans with roadmap, expected questions, and questions to ask interviewers

The strategy is designed to be non-generic and grounded in extracted project history (for deeper scenario questions and fundamentals checks).

## Input options

JD input supports two modes:
- `jd_file` (`.pdf`, `.md`, `.txt`)
- `jd_url` (`http` / `https`)

Rules:
- At least one of `jd_file` or `jd_url` is required.
- If `jd_url` is provided, URL-based planning path is used and file parsing is skipped.
- CV is optional (`.pdf`, `.md`, `.txt`).
- `company_name` is optional and overrides JD company detection when provided.
- `user_id` is optional and controls artifact folder naming.

## Processing flow

High-level orchestration:
- Parse inputs (or use `jd_url` directly for JD path)
- Run two flows in parallel:
  - User profile flow: CV -> structured job experiences
  - Job/company flow:
    - resolve company
    - extract JD requirements
    - run company research (if company resolved)
- Enrich interview strategy using both JD outputs and extracted job experiences
- Return API response and write markdown artifacts

## Progressive markdown exports

Artifacts are written to:
- `OUTPUT_DATA_DIR/{resolved_user_id}/`

`resolved_user_id` priority:
1) request `user_id`
2) CV-derived identifier (GitHub handle, else email, else phone)
3) `anonymous_user`

Export files:
- `user_profile_summarization.md` (after CV extraction)
- `company_info_and_jd_brief.md` (after job/company flow)
- `round_XX_<stage>.md` (one file per interview round after strategy finalization)

## Environment configuration

1. Copy `.env.example` -> `.env`
2. Fill required keys

Example:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_LARGE_MODEL=gpt-4.1
OPENAI_SMALL_MODEL=gpt-4.1-mini
PERPLEXITY_API_KEY=your_perplexity_api_key_here
PERPLEXITY_MODEL=sonar
MAX_JD_CHARS=4000
MAX_CV_CHARS=6000
MAX_RESEARCH_CHARS=8000
MAX_THREAD_WORKERS=32
OUTPUT_DATA_DIR=data
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run with Docker Compose

```bash
docker compose up --build -d
```

Stop:

```bash
docker compose down
```

Compose exposes service at `http://localhost:8080` and mounts `./data` to `/app/data`.

## API usage

Endpoint:
- `POST /interview-prep/query`

### Example A: JD URL + CV

```bash
curl -X POST "http://localhost:8080/interview-prep/query" \
  -F "query=What should I prioritize for this interview?" \
  -F "jd_url=https://example.com/jobs/senior-applied-ai-engineer" \
  -F "cv_file=@./sample-cv.pdf" \
  -F "company_name=AItomatic" \
  -F "user_id=duong"
```

### Example B: JD file + CV

```bash
curl -X POST "http://localhost:8080/interview-prep/query" \
  -F "query=What should I prioritize for this interview?" \
  -F "jd_file=@./sample-jd.pdf" \
  -F "cv_file=@./sample-cv.pdf"
```

## Response shape

Top-level response fields:
- `user_job_experiences`
- `company_information`
- `job_requirement`
- `interview_strategy`
- `answer`
- `raw`

## Notes and current limitations

- JD image parsing is intentionally disabled in current parser mode.
- Company research runs only when company can be resolved.
- Provider/API quality depends on source JD/CV quality and external search coverage.