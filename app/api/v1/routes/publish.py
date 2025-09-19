from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas import PublishRequest, EventEnvelope
from app.core.security import internal_trusted
from app.core.config import settings
from app.services.pubsub import publish_event
from app.services.persistence import save_persistent_event
from app.services.push_offline import send_push_notification_if_offline
from app.utils.ids import new_event_id, now_iso



router = APIRouter(tags=["internal:publish"])

@router.post("/notify/publish")
async def publish(req: PublishRequest, _: None = Depends(internal_trusted), request: Request = None):
    envelope = EventEnvelope(
        id=new_event_id(),
        type=req.type,
        user_id=str(req.user_id),
        data=req.data,
        permalink=req.permalink,
        created_at=now_iso(),
    )

    r = request.app.state.redis
    await publish_event(r, envelope)

    if req.persistent:
        await save_persistent_event(envelope)

    await send_push_notification_if_offline(envelope)

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"accepted": True, "id": envelope.id})
