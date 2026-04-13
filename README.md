# itv-prep-agent

FastAPI app that exposes a `/query` endpoint and uses Perplexity to search/respond.

## 1) Setup

1. Copy `.env.example` to `.env`
2. Add your Perplexity API key in `.env`

Example:

```env
PERPLEXITY_API_KEY=your_perplexity_api_key_here
PERPLEXITY_PRESET=pro-search
```

## 2) Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Run with Docker

```bash
docker build -t itv-prep-agent .
docker run --rm -p 8000:8000 --env-file .env itv-prep-agent
```

## 4) Test endpoint

```bash
curl -X POST "http://localhost:8000/query" `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"What are the latest AI engineering interview trends?\"}"
```

Health check:

```bash
curl http://localhost:8000/health
```