from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.schemas import ChatRequest, ChatResponse, HealthResponse
from app.services.agent import ChatAgent
from app.services.catalog import load_catalog


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(
    title="SHL Conversational Assessment Recommender",
    version="1.0.0",
    description="Stateless SHL assessment recommender for Individual Test Solutions.",
)

agent = ChatAgent(load_catalog())


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return agent.reply(request.messages)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
