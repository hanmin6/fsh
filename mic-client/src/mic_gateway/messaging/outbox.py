from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from mic_gateway.adapters.base import SendOutcome, SiteAdapter
from mic_gateway.browser.runtime import BrowserRuntime, BrowserRuntimeCrashed
from mic_gateway.db.models import OutboxJob
from mic_gateway.db.repositories import OutboxRepository
from mic_gateway.domain import JobState
from mic_gateway.policies.messages import normalize_content
from mic_gateway.sync.engine import BackoffPolicy


def _utc_now() -> datetime:
    return datetime.now(UTC)


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def content_digest(content: str) -> str:
    return hashlib.sha256(normalize_content(content).encode()).hexdigest()


class OutboxWorker:
    def __init__(
        self,
        *,
        jobs: OutboxRepository,
        adapter: SiteAdapter,
        runtime: BrowserRuntime,
        send_interval_seconds: float = 10.0,
        backoff: BackoffPolicy | None = None,
        clock: Callable[[], datetime] = _utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = _sleep,
    ) -> None:
        self.jobs = jobs
        self.adapter = adapter
        self.runtime = runtime
        self.send_interval_seconds = max(10.0, send_interval_seconds)
        self.backoff = backoff or BackoffPolicy()
        self.clock = clock
        self.monotonic = monotonic
        self.sleeper = sleeper
        self._last_send_at: float | None = None

    async def run_once(self) -> OutboxJob | None:
        job = await self.jobs.claim_next(self.clock())
        if job is None:
            return None
        conversation_source_id = await self.jobs.conversation_source_id(job.conversation_id)
        if conversation_source_id is None:
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.FAILED.value,
                now=self.clock(),
                failure_code="conversation_not_found",
            )

        await self._pace_send()
        try:
            attempt = await self.adapter.send_message(conversation_source_id, job.content)
        except BrowserRuntimeCrashed:
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.UNCERTAIN.value,
                now=self.clock(),
                failure_code="browser_runtime_crashed",
            )
        except Exception:
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.UNCERTAIN.value,
                now=self.clock(),
                failure_code="unclassified_send_error",
            )
        finally:
            self._last_send_at = self.monotonic()

        now = self.clock()
        if attempt.outcome is SendOutcome.SENT:
            metadata = (
                {"source_message_id": attempt.source_message_id}
                if attempt.source_message_id is not None
                else {}
            )
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.SENT.value,
                now=now,
                sent_at=now,
                safe_result_metadata=metadata,
            )
        if attempt.outcome is SendOutcome.TRANSIENT_FAILURE:
            delay = self.backoff.next_delay(job.attempt_count)
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.QUEUED.value,
                now=now,
                failure_code=attempt.code,
                next_attempt_at=now + timedelta(seconds=delay),
            )
        if attempt.outcome is SendOutcome.PERMANENT_FAILURE:
            return await self.jobs.transition(
                job.id,
                expected_state=JobState.SENDING.value,
                new_state=JobState.FAILED.value,
                now=now,
                failure_code=attempt.code,
            )
        return await self.jobs.transition(
            job.id,
            expected_state=JobState.SENDING.value,
            new_state=JobState.UNCERTAIN.value,
            now=now,
            failure_code=attempt.code or "confirmation_missing",
        )

    async def reconcile_uncertain(self, job_id: UUID) -> OutboxJob | None:
        job = await self.jobs.get(job_id)
        if job is None or job.state != JobState.UNCERTAIN.value:
            return job
        conversation_source_id = await self.jobs.conversation_source_id(job.conversation_id)
        if conversation_source_id is None:
            return job
        earliest = job.attempted_at or job.created_at
        match = await self.adapter.find_outbound_match(
            conversation_source_id,
            content_digest(job.content),
            earliest,
        )
        if match is None:
            return job
        now = self.clock()
        return await self.jobs.transition(
            job.id,
            expected_state=JobState.UNCERTAIN.value,
            new_state=JobState.SENT.value,
            now=now,
            sent_at=match.source_created_at,
            failure_code=None,
            safe_result_metadata={"source_message_id": match.source_id},
        )

    async def recover_after_restart(self) -> int:
        return await self.jobs.recover_sending(self.clock())

    async def _pace_send(self) -> None:
        if self._last_send_at is None:
            return
        remaining = self.send_interval_seconds - (self.monotonic() - self._last_send_at)
        if remaining > 0:
            await self.sleeper(remaining)
