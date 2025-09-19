import ipaddress
from fastapi import Depends, HTTPException, status, Request

from app.auth.base import AuthBackend, AuthContext
from app.auth.jwt_backend import JWTAuthBackend
from app.core.config import settings



def get_auth_backend() -> AuthBackend:
    return JWTAuthBackend()

async def auth_required(ctx: AuthContext = Depends(get_auth_backend().authenticate)) -> AuthContext:
    if not ctx or ctx.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return ctx


async def internal_trusted(request: Request):
    # If no allowlist is configured, accept all (as requested)
    if not settings.INTERNAL_TRUSTED_CIDRS:
        return
    client_ip = request.client.host if request.client else None
    if not client_ip:
        raise HTTPException(status_code=403, detail="Forbidden")
    ip = ipaddress.ip_address(client_ip)
    for cidr in settings.INTERNAL_TRUSTED_CIDRS:
        if ip in ipaddress.ip_network(cidr, strict=False):
            return
    raise HTTPException(status_code=403, detail="Forbidden")
