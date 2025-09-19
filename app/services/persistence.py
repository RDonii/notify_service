from app.api.v1.schemas import EventEnvelope



async def save_persistent_event(envelope: EventEnvelope) -> None:
    # placeholder (TimescaleDB in future)
    return None
