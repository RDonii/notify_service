import json
from redis.asyncio import Redis

from app.api.v1.schemas import EventEnvelope



def user_channel(user_id: str) -> str:
    return f"user:{user_id}"

async def publish_event(r: Redis, envelope: EventEnvelope) -> None:
    ch = user_channel(envelope.user_id)
    payload = json.dumps(envelope.model_dump())
    await r.publish(ch, payload)
