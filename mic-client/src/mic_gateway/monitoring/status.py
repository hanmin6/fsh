from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SessionHealth
from mic_gateway.config import Settings
from mic_gateway.db.models import OutboxJob, SyncCheckpoint
from mic_gateway.domain import ServiceState
from mic_gateway.sync.engine import is_stale


class StatusService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.session_health = SessionHealth.unavailable("not_checked")

    def set_session_health(self, health: SessionHealth) -> None:
        self.session_health = health

    async def snapshot(self, now: datetime | None = None) -> dict[str, object]:
        current = now or datetime.now(UTC)
        async with self.sessions() as session:
            checkpoints = list((await session.scalars(select(SyncCheckpoint))).all())
            count_rows = (
                await session.execute(
                    select(OutboxJob.state, func.count()).group_by(OutboxJob.state)
                )
            ).all()
            counts: dict[str, int] = {
                state: int(count) for state, count in count_rows
            }
        sync: dict[str, object] = {}
        degraded = False
        for checkpoint in checkpoints:
            threshold = (
                self.settings.order_stale_seconds
                if checkpoint.resource == "orders"
                else self.settings.conversation_stale_seconds
            )
            fresh = not is_stale(
                checkpoint.last_success_at,
                current,
                threshold_seconds=threshold,
            )
            degraded = degraded or not fresh or checkpoint.failure_count > 0
            sync[checkpoint.resource] = {
                "last_attempt_at": checkpoint.last_attempt_at,
                "last_success_at": checkpoint.last_success_at,
                "failure_count": checkpoint.failure_count,
                "last_error_code": checkpoint.last_error_code,
                "paused_reason": checkpoint.paused_reason,
                "fresh": fresh,
            }
        for resource in ("orders", "conversations"):
            if resource not in sync:
                degraded = True
                sync[resource] = {
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "failure_count": 0,
                    "last_error_code": None,
                    "paused_reason": None,
                    "fresh": False,
                }
        if self.session_health.requires_operator:
            state = ServiceState.OPERATOR_ACTION_REQUIRED
        elif not self.session_health.healthy or degraded:
            state = ServiceState.DEGRADED
        else:
            state = ServiceState.HEALTHY
        return {
            "state": state.value,
            "session": {
                "state": self.session_health.state.value,
                "detail_code": self.session_health.detail_code,
            },
            "sync": sync,
            "outbox": {
                "queued": int(counts.get("queued", 0)),
                "sending": int(counts.get("sending", 0)),
                "uncertain": int(counts.get("uncertain", 0)),
            },
        }
