from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .agent import run_agent
from .monitoring import get_metrics
from .schemas import AgentRequest, AgentResponse, ErrorResponse, MetricsResponse

app = FastAPI(
    title="OpenResearch Scout Agent",
    description="A lightweight tool-using research assistant deployable on Hugging Face Spaces.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <head><title>OpenResearch Scout Agent</title></head>
      <body style="font-family: system-ui; max-width: 850px; margin: 40px auto; line-height: 1.5;">
        <h1>OpenResearch Scout Agent</h1>
        <p>POST a JSON request to <code>/agent</code> or open <code>/docs</code> for Swagger UI.</p>
        <pre>{"query":"agentic AI evaluation for RAG systems", "max_papers":5, "year_from":2023}</pre>
      </body>
    </html>
    """


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse | ErrorResponse)
def agent_endpoint(request: AgentRequest):
    result = run_agent(request)
    if isinstance(result, ErrorResponse):
        return JSONResponse(status_code=400, content=result.model_dump(mode="json"))
    return result


@app.get("/metrics", response_model=MetricsResponse)
def metrics_endpoint() -> MetricsResponse:
    return get_metrics()
