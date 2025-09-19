from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.security import auth_required
from app.auth.base import AuthContext
from app.services.sse_manager import sse_event_stream



router = APIRouter(tags=["external:stream"])

@router.get("/notify/stream")
async def stream(request: Request, ctx: AuthContext = Depends(auth_required)):
    """
    SSE stream for the authenticated user.
    One connection per browser session recommended.
    """
    user_id = ctx.user_id
    generator = sse_event_stream(request.app.state.redis, user_id, request)
    return StreamingResponse(generator, media_type="text/event-stream")
