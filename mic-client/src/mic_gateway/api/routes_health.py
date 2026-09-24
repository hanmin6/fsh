from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "code": "database_unavailable"},
        )
    service = getattr(request.app.state, "status_service", None)
    if service is not None:
        snapshot = await service.snapshot()
        if snapshot["state"] != "healthy":
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "code": str(snapshot["state"])},
            )
    return JSONResponse(content={"status": "ready"})
