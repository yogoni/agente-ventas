"""FastAPI chat interface for the sales agent."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from uuid import uuid4

from copilot import CopilotClient
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langsmith import Client as LangSmithClient
from langsmith.run_helpers import trace
from pydantic import BaseModel, Field

from agente_ventas import DB_PATH, ROOT, create_sales_session, get_api_key


logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_SESSIONS = 100

# LangSmith: cada respuesta se traza con un run_id propio, que el navegador
# devuelve después al pulsar 👍/👎 para colgar el feedback de esa traza.
load_dotenv(ROOT / ".env")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "agente-ventas")
if os.getenv("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGSMITH_TRACING", "true")

_langsmith_client: LangSmithClient | None = None
_langsmith_project_id: str | None = None


def langsmith_client() -> LangSmithClient | None:
    """Return a LangSmith client, or None when feedback is not configured."""
    global _langsmith_client
    if _langsmith_client is None and os.getenv("LANGSMITH_API_KEY"):
        _langsmith_client = LangSmithClient()
    return _langsmith_client


def langsmith_project_id() -> str | None:
    client = langsmith_client()
    if client is None:
        return None
    global _langsmith_project_id
    if _langsmith_project_id is None:
        try:
            _langsmith_project_id = client.read_project(project_name=LANGSMITH_PROJECT).id
        except Exception:
            logger.warning("No se pudo resolver el proyecto LangSmith %s", LANGSMITH_PROJECT, exc_info=True)
    return _langsmith_project_id


@dataclass
class ChatSession:
    copilot_session: object
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    run_id: str | None = None


class ResetRequest(BaseModel):
    session_id: str


class FeedbackRequest(BaseModel):
    run_id: str = Field(min_length=1)
    score: int = Field(ge=0, le=1)
    comment: str = Field(default="", max_length=500)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DB_PATH.is_file():
        raise RuntimeError(f"Sales database missing: {DB_PATH}")
    get_api_key()
    client = CopilotClient(
        mode="empty",
        working_directory=str(ROOT),
        base_directory=str(ROOT / ".copilot-state"),
    )
    await client.start()
    app.state.client = client
    app.state.sessions = {}
    app.state.sessions_lock = asyncio.Lock()
    try:
        yield
    finally:
        await client.stop()


app = FastAPI(title="Agente de ventas", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Escribe un mensaje.")

    async with app.state.sessions_lock:
        entry = app.state.sessions.get(request.session_id)
        if entry is None:
            if len(app.state.sessions) >= MAX_SESSIONS:
                raise HTTPException(status_code=503, detail="Hay demasiadas conversaciones activas.")
            try:
                copilot_session = await create_sales_session(app.state.client)
            except Exception:
                logger.exception("Failed to create sales agent session")
                raise HTTPException(status_code=502, detail="No se pudo iniciar el agente.")
            session_id = str(uuid4())
            entry = ChatSession(copilot_session)
            app.state.sessions[session_id] = entry
        else:
            session_id = request.session_id

    run_id = uuid4()
    try:
        async with entry.lock:
            with trace(
                "sales_agent_chat",
                run_type="chain",
                project_name=LANGSMITH_PROJECT,
                run_id=run_id,
                inputs={"message": message, "session_id": session_id},
                tags=["web"],
            ) as run:
                response = await entry.copilot_session.send_and_wait(message, timeout=120)
                reply = response.data.content if response and response.data else None
                if reply:
                    run.outputs = {"reply": reply}
    except Exception:
        logger.exception("Sales agent request failed")
        raise HTTPException(status_code=502, detail="El agente no pudo responder. Inténtalo de nuevo.")

    if not reply:
        raise HTTPException(status_code=502, detail="El agente no devolvió una respuesta.")
    return ChatResponse(reply=reply, session_id=session_id, run_id=str(run_id))


@app.post("/api/feedback")
async def feedback(request: FeedbackRequest):
    """Record a 👍/👎 for one answer, attached to its LangSmith trace."""
    client = langsmith_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="El feedback necesita LANGSMITH_API_KEY en el archivo .env.",
        )
    try:
        client.create_feedback(
            request.run_id,
            key="user_feedback",
            score=float(request.score),
            comment=request.comment or ("thumbs_up" if request.score else "thumbs_down"),
            session_id=langsmith_project_id(),
        )
    except Exception:
        logger.exception("Failed to record feedback for run %s", request.run_id)
        raise HTTPException(status_code=502, detail="No se pudo registrar el feedback.")
    return {"status": "ok"}


@app.post("/api/reset")
async def reset(request: ResetRequest):
    async with app.state.sessions_lock:
        entry = app.state.sessions.pop(request.session_id, None)
    if entry is not None:
        async with entry.lock:
            await app.state.client.delete_session(entry.copilot_session.session_id)
    return {"status": "ok"}
