from app.api.v1.schemas import EventEnvelope



async def send_push_notification_if_offline(envelope: EventEnvelope) -> None:
    # placeholder (FCM/APNS/web-push later)
    return None
