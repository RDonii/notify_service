import jwt
from typing import List
from fastapi import Request, HTTPException, status

from app.auth.base import AuthBackend, AuthContext
from app.core.config import settings



class JWTAuthBackend(AuthBackend):
    def __init__(self):
        self.alg = settings.JWT_ALG
        self.secret = settings.JWT_SECRET
        self.user_claim = settings.JWT_USER_ID_CLAIM

    async def authenticate(self, request: Request) -> AuthContext:
        token = request.query_params.get("token")

        if not token:
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                token = auth.removeprefix("Bearer ").strip()

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing token"
            )

        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.alg])
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user_id = payload.get(self.user_claim)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user claim"
            )

        scopes: List[str] = payload.get("scopes", [])
        return AuthContext(user_id=str(user_id), scopes=scopes)
