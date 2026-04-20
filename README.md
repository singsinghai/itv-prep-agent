# itv-prep-agent

FastAPI app for interview preparation.

It accepts a user query plus a JD file (`.pdf`, `.md`, `.txt`), optional CV file (`.pdf`, `.md`, `.txt`), and optional `company_name`, then runs extraction-focused planning with OpenAI (via LangChain).
JD parsing is handled through `PyMuPDF` (for PDF) and plain text decode (for MD/TXT).

## 1) Setup

1. Copy `.env.example` to `.env`
2. Add your OpenAI API key in `.env`

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
```

## 2) Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

No extra system OCR setup is required in this version.

## 3) Run with Docker Compose

```bash
docker compose up --build -d
```

Stop the service:

```bash
docker compose down
```

## 4) Interview prep endpoint

```bash
curl -X POST "http://localhost:8080/interview-prep/query" `
  -F "query=What should I focus on for this role interview?" `
  -F "company_name=Your Target Company (optional)" `
  -F "user_id=your_user_id_optional" `
  -F "cv_file=@./sample-cv.pdf" `
  -F "jd_file=@./sample-jd.pdf"
```

Behavior:
- If `company_name` is provided in request, it overrides JD company detection.
- If `company_name` is not provided, planner uses LLM extraction over JD context to infer the company.
- System runs two parallel pipelines:
  - user profile flow: CV text -> CV LLM extraction
  - job/company flow: company resolve -> (job requirement extraction + company research in parallel)
- CV file is optional. If provided, CV extraction runs in parallel with JD extraction.
- CV extraction output is sorted job experiences (`JobExperience`) with nested projects (`Project`) and project highlights.
- Planner only performs extraction-focused outputs:
  - scope of work
  - key qualifications
  - tech stacks
  - JD gaps or ambiguities
- Planner also returns interview strategy output derived from JD + CV:
  - If interview process/rounds are explicitly stated in JD, those stages are used.
  - If not, planner falls back to default stage flow:
    1) Technical interview
    2) Cultural / past experience interview
    3) CEO interview
  - For each stage, output includes:
    - stage objective
    - why this stage matters for this role
    - revision roadmap (non-generic, tied to candidate experience)
    - expected questions
    - questions candidate should ask interviewer
  - Strategy is enriched with extracted structured job experiences to produce deeper project-anchored, scenario-based and fundamentals-probing interview questions.
- JD context selection is relevance-based chunking (keyword/query scoring), not plain first-N slicing.
- If company is resolved, Perplexity company research runs right after planning to extract:
  - core products
  - brief summary of top products
  - CEO profile (including founder/cofounder signal, background, publications/side products)
  - CEO work + contribution
  - culture
  - vision
  - business model
- Perplexity search results are filtered to top 5 most relevant matches to reduce noisy context and payload size.
- If company is unresolved, Perplexity research is skipped.
- If `company_name` is explicitly provided by user, it is treated as the source of truth and exact-name matching is enforced in company research.
- Markdown artifacts are written during processing to `OUTPUT_DATA_DIR/{resolved_user_id}/`.
- `resolved_user_id` resolution order:
  1) request `user_id` (if provided)
  2) CV identifier fallback (GitHub handle, else email, else phone)
  3) `anonymous_user` when CV or identifier is unavailable
- Component export files:
  - `user_profile_summarization.md` after CV extraction component finishes
  - `company_info_and_jd_brief.md` after job/company component finishes
  - `round_XX_<stage>.md` files after interview strategy is finalized (one file per round)
- Step-level logs include function calls and execution times.
- Current JD parser support: `.pdf`, `.md`, `.txt` (image parsing is intentionally disabled for now).

Response shape is grouped into:
- `user_job_experiences`
- `company_information`
- `job_requirement`
- `interview_strategy`

Health check:

```bash
curl http://localhost:8080/health
```