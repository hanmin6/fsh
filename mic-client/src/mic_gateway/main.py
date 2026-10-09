from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mic_gateway import __version__
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.api.middleware import RateLimiter, RequestContextMiddleware, safe_error_payload
from mic_gateway.api.routes_health import router as health_router
from mic_gateway.api.routes_read import router as read_router
from mic_gateway.api.routes_write import router as write_router
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings, get_settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import (
    CheckpointRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    OutboxRepository,
)
from mic_gateway.errors import ApiError
from mic_gateway.messaging.outbox import OutboxWorker
from mic_gateway.monitoring.status import StatusService
from mic_gateway.runtime.scheduler import GatewayScheduler
from mic_gateway.sync.engine import SyncEngine


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    browser_runtime: BrowserRuntime | None = None,
    outbox_worker: OutboxWorker | None = None,
    status_service: StatusService | None = None,
    scheduler: GatewayScheduler | None = None,
    production: bool = False,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_engine: AsyncEngine | None = None
    if session_factory is None:
        database_engine, session_factory = create_engine_and_sessionmaker(resolved_settings)
    adapter: MadeInChinaAdapter | None = None
    sync_engine: SyncEngine | None = None
    if production:
        if any(
            dependency is not None
            for dependency in (
                browser_runtime,
                outbox_worker,
                status_service,
                scheduler,
            )
        ):
            raise ValueError("production composition cannot mix injected runtime services")
        browser_runtime = BrowserRuntime(resolved_settings)
        adapter = MadeInChinaAdapter(browser_runtime)
        orders = OrderRepository(session_factory)
        conversations = ConversationRepository(session_factory)
        messages = MessageRepository(session_factory)
        checkpoints = CheckpointRepository(session_factory)
        jobs = OutboxRepository(session_factory)
        sync_engine = SyncEngine(
            adapter=adapter,
            sessions=session_factory,
            orders=orders,
            conversations=conversations,
            messages=messages,
            checkpoints=checkpoints,
        )
        outbox_worker = OutboxWorker(
            jobs=jobs,
            adapter=adapter,
            runtime=browser_runtime,
            send_interval_seconds=resolved_settings.send_interval_seconds,
        )
        status_service = StatusService(session_factory, settings=resolved_settings)
        scheduler = GatewayScheduler(
            adapter=adapter,
            browser_runtime=browser_runtime,
            sync_engine=sync_engine,
            outbox_worker=outbox_worker,
            status_service=status_service,
            conversation_interval=resolved_settings.conversation_sync_seconds,
            order_interval=resolved_settings.order_sync_seconds,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings.app_data_dir.mkdir(parents=True, exist_ok=True)
        if database_engine is not None:
            async with database_engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        if outbox_worker is not None:
            await outbox_worker.recover_after_restart()
        if browser_runtime is not None:
            await browser_runtime.start()
        if scheduler is not None:
            await scheduler.start()
        try:
            yield
        finally:
            app.state.accepting_mutations = False
            if scheduler is not None:
                await scheduler.stop()
            if outbox_worker is not None:
                await outbox_worker.recover_after_restart()
            if browser_runtime is not None:
                await browser_runtime.stop()
            if database_engine is not None:
                await database_engine.dispose()

    app = FastAPI(
        title="Made-in-China Automation Gateway",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.rate_limiter = RateLimiter()
    app.state.accepting_mutations = True
    app.state.status_service = status_service
    app.state.scheduler = scheduler
    app.state.browser_runtime = browser_runtime
    app.state.adapter = adapter
    app.state.sync_engine = sync_engine
    app.state.outbox_worker = outbox_worker
    app.add_middleware(
        RequestContextMiddleware,
        max_request_bytes=resolved_settings.max_request_bytes,
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=error.status_code,
            content=safe_error_payload(error, request_id),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, _: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        error = ApiError(422, "validation_error", "The request is invalid")
        return JSONResponse(
            status_code=422,
            content=safe_error_payload(error, request_id),
            headers={"X-Request-ID": request_id},
        )

    app.include_router(health_router)
    app.include_router(read_router)
    app.include_router(write_router)
    return app


def create_production_app() -> FastAPI:
    """Uvicorn factory for the fully composed local gateway."""
    return create_app(production=True)
