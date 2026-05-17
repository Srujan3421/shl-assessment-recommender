# SHL Conversational Assessment Recommender

FastAPI backend for the SHL AI Intern assignment. The API recommends, refines, and compares SHL assessments using only the provided SHL catalog JSON. It has no runtime LLM dependency and keeps every `/chat` request stateless.

## API

- `GET /health` returns `{"status":"ok"}`
- `POST /chat` accepts `{"messages":[{"role":"user","content":"..."}]}`
- `/chat` always returns `reply`, `recommendations`, and `end_of_conversation`
- Recommendations are capped at 10 and every URL is copied from the local SHL catalog

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Download Catalog

```powershell
python scripts\download_catalog.py
```

This downloads the official assignment catalog from:

`https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json`

and saves normalized records to `app/data/catalog.json`.

## Run Backend

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` for the simple local UI.

## Test The API

Health:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Chat:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -ContentType 'application/json' `
  -Body '{"messages":[{"role":"user","content":"Hiring a Java backend engineer with Spring, SQL, AWS and Docker experience"}]}'
```

Vague query:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat `
  -ContentType 'application/json' `
  -Body '{"messages":[{"role":"user","content":"I need an assessment"}]}'
```

Run tests:

```powershell
pytest
```

## Deploy On Render Or Railway

Use the included `render.yaml`, or configure manually:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

The deployed service should expose:

- `https://your-url/health`
- `https://your-url/chat`

## Project Layout

```text
app/
  main.py                  FastAPI entrypoint
  schemas.py               Strict request/response models
  data/catalog.json        Official SHL catalog snapshot
  services/
    agent.py               Stateless dialogue policy and guardrails
    catalog.py             Catalog normalization and validation
    retrieval.py           Intent extraction, ranking, aliases, comparison matching
frontend/index.html        Lightweight local demo UI
scripts/download_catalog.py
tests/
```
