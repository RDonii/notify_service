from dataclasses import dataclass
from typing import List, Optional
from fastapi import Request



@dataclass
class AuthContext:
    user_id: Optional[str]
    scopes: List[str]

class AuthBackend:
    async def authenticate(self, request: Request) -> AuthContext:
        raise NotImplementedError
