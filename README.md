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
- Step-level logs include function calls and execution times.
- Current JD parser support: `.pdf`, `.md`, `.txt` (image parsing is intentionally disabled for now).

Response shape is grouped into:
- `user_job_experiences`
- `company_information`
- `job_requirement`

Health check:

```bash
curl http://localhost:8080/health
```