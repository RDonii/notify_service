from fastapi import APIRouter



router = APIRouter(tags=["health"])

@router.get("/health/live")
async def live():
    return {"status": "ok"}

@router.get("/health/ready")
async def ready():
    return {"status": "ok"}
