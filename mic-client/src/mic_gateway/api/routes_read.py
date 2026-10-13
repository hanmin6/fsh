from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from mic_gateway.api.auth import Principal, require_role
from mic_gateway.api.schemas import (
    ConversationResponse,
    CursorPage,
    JobResponse,
    MessageResponse,
    OrderLineResponse,
    OrderResponse,
)
from mic_gateway.db.repositories import (
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    OutboxRepository,
)
from mic_gateway.domain import Role
from mic_gateway.errors import ApiError
from mic_gateway.monitoring.status import StatusService

router = APIRouter(prefix="/v1", tags=["read"])

CrmPrincipal = Annotated[Principal, Depends(require_role(Role.CRM_READ))]
PageLimit = Annotated[int, Query(ge=1, le=200)]


def _not_found() -> ApiError:
    return ApiError(404, "resource_not_found", "The requested resource was not found.")


def _validate_updated_after(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ApiError(422, "validation_error", "The request is invalid")
    return value


async def _order_response(repository: OrderRepository, order: object) -> OrderResponse:
    response = OrderResponse.model_validate(order)
    lines = await repository.list_lines(response.id)
    return response.model_copy(
        update={"lines": [OrderLineResponse.model_validate(line) for line in lines]}
    )


@router.get("/orders", response_model=CursorPage[OrderResponse])
async def list_orders(
    request: Request,
    _: CrmPrincipal,
    limit: PageLimit = 50,
    cursor: str | None = None,
    updated_after: datetime | None = None,
    status: str | None = None,
    buyer: str | None = None,
) -> CursorPage[OrderResponse]:
    repository = OrderRepository(request.app.state.session_factory)
    rows, next_cursor = await repository.list_page(
        limit=limit,
        cursor=cursor,
        updated_after=_validate_updated_after(updated_after),
        status=status,
        buyer_reference=buyer,
    )
    items = [await _order_response(repository, row) for row in rows]
    return CursorPage(items=items, next_cursor=next_cursor)


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    request: Request,
    _: CrmPrincipal,
) -> OrderResponse:
    repository = OrderRepository(request.app.state.session_factory)
    order = await repository.get(order_id)
    if order is None:
        raise _not_found()
    return await _order_response(repository, order)


@router.get("/conversations", response_model=CursorPage[ConversationResponse])
async def list_conversations(
    request: Request,
    _: CrmPrincipal,
    limit: PageLimit = 50,
    cursor: str | None = None,
    updated_after: datetime | None = None,
    unread: bool | None = None,
    buyer: str | None = None,
) -> CursorPage[ConversationResponse]:
    repository = ConversationRepository(request.app.state.session_factory)
    rows, next_cursor = await repository.list_page(
        limit=limit,
        cursor=cursor,
        updated_after=_validate_updated_after(updated_after),
        unread=unread,
        buyer_reference=buyer,
    )
    return CursorPage(
        items=[ConversationResponse.model_validate(row) for row in rows],
        next_cursor=next_cursor,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=CursorPage[MessageResponse],
)
async def list_messages(
    conversation_id: UUID,
    request: Request,
    _: CrmPrincipal,
    limit: PageLimit = 50,
    cursor: str | None = None,
) -> CursorPage[MessageResponse]:
    conversations = ConversationRepository(request.app.state.session_factory)
    if await conversations.get(conversation_id) is None:
        raise _not_found()
    repository = MessageRepository(request.app.state.session_factory)
    rows, next_cursor = await repository.list_page_for_conversation(
        conversation_id, limit=limit, cursor=cursor
    )
    return CursorPage(
        items=[MessageResponse.model_validate(row) for row in rows],
        next_cursor=next_cursor,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    request: Request,
    _: CrmPrincipal,
) -> JobResponse:
    repository = OutboxRepository(request.app.state.session_factory)
    job = await repository.get(job_id)
    if job is None:
        raise _not_found()
    return JobResponse.model_validate(job)


@router.get("/status")
async def get_status(request: Request, _: CrmPrincipal) -> dict[str, object]:
    service: StatusService | None = getattr(request.app.state, "status_service", None)
    if service is None:
        raise ApiError(503, "status_unavailable", "Runtime status is unavailable.")
    snapshot = await service.snapshot()
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None and hasattr(scheduler, "diagnostics"):
        snapshot["poller"] = scheduler.diagnostics()
    return snapshot
