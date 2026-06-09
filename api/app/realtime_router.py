from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["realtime"])


@router.get("/realtime/ping")
async def realtime_ping() -> dict[str, str]:
    return {"status": "ok"}
