from typing import Any, Optional
from pydantic import BaseModel, Field



class PublishRequest(BaseModel):
    type: str = Field(..., min_length=1, max_length=64)
    user_id: str = Field(..., min_length=1)
    data: Any
    permalink: Optional[str] = None
    persistent: bool = False

class EventEnvelope(BaseModel):
    id: str
    type: str
    user_id: str
    data: Any
    permalink: Optional[str] = None
    created_at: str
