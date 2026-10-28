---
title: OpenResearch Scout Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# OpenResearch Scout Agent

A lightweight tool-using research assistant designed for Hugging Face Spaces + FastAPI.

## Use case

Given a research topic, the agent searches arXiv, ranks papers, returns a grounded research brief, lists tool calls, applies basic safety guardrails, and logs monitoring data.

## Why this project fits the assignment

- Agent handler: `app/agent.py` exposes `run_agent()`.
- FastAPI API: `app/main.py` exposes `/agent`, `/health`, `/metrics`, and `/docs`.
- Tools:
  1. `arxiv_search`: retrieves candidate papers from arXiv.
  2. `paper_ranker`: ranks evidence using transparent keyword overlap and recency.
  3. `cost_estimator`: estimates token volume for cost reporting.
- Guardrails:
  - Input length validation with Pydantic.
  - Unsafe/sensitive prompt pattern blocking.
  - Search sanitization.
  - Structured output schema with Pydantic.
  - Source-grounded responses with URLs.
- Evaluation:
  - `eval/eval.py` runs regression checks on quality, safety, latency, schema validity, and tool usage.
- Monitoring:
  - JSONL request logs.
  - `/metrics` endpoint with request count, blocked count, failures, average latency, and recent requests.

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 7860
```

Open:

```text
http://localhost:7860/docs
```

## Example request

```bash
curl -X POST http://localhost:7860/agent \
  -H "Content-Type: application/json" \
  -d '{"query":"agentic AI evaluation for RAG systems", "max_papers":5, "year_from":2023}'
```

## Example response shape

```json
{
  "answer": "Research brief for: ...",
  "papers": [
    {
      "title": "...",
      "authors": ["..."],
      "year": 2024,
      "summary": "...",
      "url": "https://arxiv.org/abs/...",
      "relevance_score": 0.82,
      "matched_terms": ["evaluation", "rag"]
    }
  ],
  "tool_calls": [
    {"name": "arxiv_search", "latency_ms": 512.4, "success": true}
  ],
  "safety": {"allowed": true, "reason": "ok", "flags": []},
  "cost": {"estimated_total_tokens": 1800, "note": "..."},
  "monitoring_id": "abc123...",
  "created_at": "..."
}
```

## Hugging Face Spaces deployment

1. Create a new Hugging Face Space.
2. Choose Docker as the Space SDK.
3. Push these files to the Space repository.
4. The Space should expose the app on port `7860`.
5. Test the endpoint at:

```text
https://<your-username>-<your-space-name>.hf.space/agent
```

## Run evaluation

```bash
python eval/eval.py
```

The script prints a compact mini-report with pass/fail status for each test case.

## Mini-report draft

### Objective

The project implements a deployable research scouting agent that helps users identify relevant academic papers for a technical topic. It is designed for low-cost deployment on Hugging Face Spaces while still demonstrating agentic behavior through explicit tool calls.

### Agent design

The system follows a simple handler-based architecture. The FastAPI endpoint receives a validated request, applies input guardrails, calls the arXiv search tool, ranks retrieved papers, estimates token cost, returns a structured JSON response, and writes a monitoring log entry.

### Tools

The first tool searches arXiv for candidate papers. The second tool ranks the results based on keyword overlap and recency. A third optional tool estimates token volume for cost reporting.

### Guardrails and safety

The agent blocks requests that appear to ask for credential extraction, prompt leakage, unsafe cyber abuse, or personal-data lookup. It also sanitizes search strings before external API calls and validates all responses with Pydantic schemas.

### Evaluation

The evaluation script checks schema validity, successful tool use, minimum paper count, keyword coverage, safe blocking behavior, and latency. This produces a small but defensible evaluation section for the assignment.

### Monitoring

The app logs request metadata to JSONL: monitoring ID, latency, status, safety flags, number of papers returned, tool calls, and token estimate. The `/metrics` endpoint aggregates total requests, blocked requests, failures, average latency, and recent requests.

### Cost

The base application has no paid dependency. It calls the public arXiv API and uses deterministic ranking. If an LLM summarizer is added later, cost should be calculated from input tokens, output tokens, provider price per million tokens, and observed request volume.

### Limitations

The ranking is intentionally simple and explainable. It does not replace a full semantic retrieval system. The guardrails are rule-based and should be strengthened with a classifier for production use.
