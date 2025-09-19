import time
import uuid
from datetime import datetime, timezone



def new_event_id() -> str:
    return f"{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
