from __future__ import annotations

import hashlib
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from mic_gateway.api.auth import Principal, require_role
from mic_gateway.api.middleware import enforce_rate_limit
from mic_gateway.api.schemas import (
    JobResponse,
    ManualSyncRequest,
    ManualSyncResponse,
    MessageSubmitRequest,
)
from mic_gateway.db.models import AuditEvent
from mic_gateway.db.repositories import ConversationRepository, OutboxRepository
from mic_gateway.domain import JobState, OutboxCreateRequest, Role
from mic_gateway.errors import ApiError
from mic_gateway.policies.messages import PolicyUnavailable, evaluate_message

router = APIRouter(prefix="/v1", tags=["write"])

AgentPrincipal = Annotated[Principal, Depends(require_role(Role.AGENT_SEND))]
AdminPrincipal = Annotated[Principal, Depends(require_role(Role.ADMIN))]


def _payload_digest(
    conversation_id: UUID,
    submission: MessageSubmitRequest,
) -> str:
    payload = {
        "conversation_id": str(conversation_id),
        "intent": submission.intent.value,
        "content": submission.content,
        "caller_reference": submission.caller_reference,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


async def _record_policy_audit(
    request: Request,
    principal: Principal,
    conversation_id: UUID,
    submission: MessageSubmitRequest,
    *,
    allowed: bool,
    code: str,
) -> None:
    async with request.app.state.session_factory() as session:
        session.add(
            AuditEvent(
                request_id=request.state.request_id,
                caller_key_id=principal.key_id,
                event_type="message_policy_decision",
                entity_type="conversation",
                entity_id=str(conversation_id),
                details={
                    "allowed": allowed,
                    "code": code,
                    "intent": submission.intent.value,
                    "caller_reference": submission.caller_reference,
                },
            )
        )
        await session.commit()


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_message(
    conversation_id: UUID,
    submission: MessageSubmitRequest,
    request: Request,
    principal: AgentPrincipal,
) -> JobResponse:
    if not request.app.state.accepting_mutations:
        raise ApiError(503, "shutting_down", "The gateway is not accepting new work.")
    await enforce_rate_limit(request, principal, bucket="send", limit=10, window_seconds=60)
    conversations = ConversationRepository(request.app.state.session_factory)
    if await conversations.get(conversation_id) is None:
        raise ApiError(404, "resource_not_found", "The requested resource was not found.")

    try:
        decision = evaluate_message(submission.intent, submission.content)
    except PolicyUnavailable as exc:
        raise ApiError(
            503,
            "policy_unavailable",
            "Automatic message policy is unavailable.",
        ) from exc

    await _record_policy_audit(
        request,
        principal,
        conversation_id,
        submission,
        allowed=decision.allowed,
        code=decision.code,
    )
    create_request = OutboxCreateRequest(
        idempotency_key=submission.idempotency_key,
        payload_digest=_payload_digest(conversation_id, submission),
        conversation_id=conversation_id,
        intent=submission.intent,
        content=submission.content,
        caller_reference=submission.caller_reference,
        caller_key_id=principal.key_id,
        request_id=request.state.request_id,
        initial_state=(JobState.QUEUED if decision.allowed else JobState.REQUIRES_HUMAN_REVIEW),
    )
    result = await OutboxRepository(
        request.app.state.session_factory
    ).create_idempotent(create_request)
    return JobResponse.model_validate(result.job)


@router.post(
    "/admin/sync",
    response_model=ManualSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_manual_sync(
    submission: ManualSyncRequest,
    request: Request,
    _: AdminPrincipal,
) -> ManualSyncResponse:
    if not request.app.state.accepting_mutations:
        raise ApiError(503, "shutting_down", "The gateway is not accepting new work.")
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise ApiError(503, "scheduler_unavailable", "The scheduler is unavailable.")
    queued = scheduler.queue_manual_sync(submission.resource)
    return ManualSyncResponse(queued=queued, resource=submission.resource)
