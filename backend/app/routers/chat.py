import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.chat_models import UserQuery, AgentResponse
from app.services.llm_agent import run_agent, run_agent_stream
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(query: UserQuery):
    """Stream chat responses via SSE."""
    from app.main import app

    db_path = app.state.db_path

    async def event_generator():
        async for event in run_agent_stream(db_path, query):
            event_type = event["event"]
            data = json.dumps(event["data"], default=str)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/query", response_model=AgentResponse)
async def chat_query(query: UserQuery):
    """Non-streaming chat query."""
    from app.main import app

    db_path = app.state.db_path
    return await run_agent(db_path, query)


@router.get("/health")
async def chat_health():
    return {
        "status": "ok",
        "llm_provider": "gemini-flash",
        "guardrails": "active",
    }
