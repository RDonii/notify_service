import asyncio
import json
import contextlib
from typing import AsyncGenerator
from redis.asyncio import Redis

from app.core.config import settings



def _format_sse(data: str, event: str | None = None, id: str | None = None, retry_ms: int | None = None) -> str:
    lines = []
    if id is not None:
        lines.append(f"id: {id}")
    if retry_ms is not None:
        lines.append(f"retry: {retry_ms}")
    if event:
        lines.append(f"event: {event}")
    for line in data.splitlines() or [""]:
        lines.append(f"data: {line}")
    lines.append("")  # end of message
    return "\n".join(lines) + "\n"

def _heartbeat() -> str:
    return ":\n\n"

async def sse_event_stream(r: Redis, user_id: str, request) -> AsyncGenerator[bytes, None]:
    """
    Subscribes to Redis pubsub channel for user and streams SSE.
    Sends heartbeats.
    """
    pubsub = r.pubsub()
    channel = f"user:{user_id}"
    await pubsub.subscribe(channel)

    heartbeat_interval = settings.SSE_HEARTBEAT_SECONDS
    retry_ms = settings.SSE_RETRY_MILLISECONDS

    queue: asyncio.Queue[str] = asyncio.Queue()

    async def reader():
        try:
            async for msg in pubsub.listen():
                if msg is None:
                    continue
                if msg.get("type") != "message":
                    continue
                data = msg.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode()
                try:
                    payload = json.loads(data)
                    event_type = payload.get("type", "message")
                    event_id = payload.get("id")
                    sse = _format_sse(json.dumps(payload), event=event_type, id=event_id)
                except Exception:
                    sse = _format_sse(str(data))
                await queue.put(sse)
        finally:
            await pubsub.unsubscribe(channel)

    reader_task = asyncio.create_task(reader())

    # Initial retry hint
    yield _format_sse("stream-open", event="ready", retry_ms=retry_ms).encode()

    try:
        last_hb = asyncio.get_event_loop().time()
        while True:
            if await request.is_disconnected():
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield item.encode()
            except asyncio.TimeoutError:
                pass

            now = asyncio.get_event_loop().time()
            if now - last_hb >= heartbeat_interval:
                yield _heartbeat().encode()
                last_hb = now
    finally:
        reader_task.cancel()
        with contextlib.suppress(Exception): # to avoid CancelledError
            await reader_task
