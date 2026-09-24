from __future__ import annotations

import argparse
import math
import re
import sys
import time
from collections.abc import Callable, Sequence

from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.crm_client import CrmClient
from mic_gateway.crm_bridge.state import CrmBridgeState
from mic_gateway.crm_bridge.worker import MicOutboundWorker, WorkerResult

DEFAULT_INTERVAL_SECONDS = 30.0
MIN_INTERVAL_SECONDS = 1.0
MAX_INTERVAL_SECONDS = 3_600.0
MAX_BACKOFF_SECONDS = 300.0
_RETRYABLE_RESULT_STATUSES = {"gateway_unavailable", "heartbeat_failed", "gateway_not_ready"}


def _interval_argument(value: str) -> float:
    try:
        interval = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("interval must be a number") from None
    if not math.isfinite(interval) or not MIN_INTERVAL_SECONDS <= interval <= MAX_INTERVAL_SECONDS:
        raise argparse.ArgumentTypeError(
            "interval must be between "
            f"{MIN_INTERVAL_SECONDS:g} and {MAX_INTERVAL_SECONDS:g} seconds"
        )
    return interval


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the approved Made-in-China CRM outbound worker."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one reconciliation/claim iteration and exit",
    )
    parser.add_argument(
        "--interval",
        type=_interval_argument,
        default=DEFAULT_INTERVAL_SECONDS,
        metavar="SECONDS",
        help=(
            f"poll delay in seconds ({MIN_INTERVAL_SECONDS:g}-{MAX_INTERVAL_SECONDS:g}; "
            f"default: {DEFAULT_INTERVAL_SECONDS:g})"
        ),
    )
    return parser


def _build_worker(config: CrmBridgeConfig) -> MicOutboundWorker:
    # The Agent must be registered separately through the bridge register CLI.
    # Its issued token belongs in MIC_CRM_AGENT_TOKEN; startup never registers.
    if not config.mic_send_api_key:
        raise ValueError("MIC gateway send API key is required")
    if not config.crm_agent_token:
        raise ValueError("registered CRM Agent token is required")
    config.validate()
    crm = CrmClient(
        config.crm_base_url,
        config.crm_agent_key,
        config.crm_agent_token,
    )
    state = CrmBridgeState(config.app_data_dir)
    return MicOutboundWorker.from_config(config=config, crm=crm, state=state)


def _iteration_failed(result: WorkerResult) -> bool:
    return result.status in _RETRYABLE_RESULT_STATUSES


def _emit_result(result: WorkerResult, emit: Callable[[str], None]) -> None:
    status = result.status if re.fullmatch(r"[a-z_]+", result.status) else "unknown"
    emit(f"MIC outbound worker status={status}")


def run_loop(
    worker: MicOutboundWorker,
    *,
    interval_seconds: float,
    once: bool = False,
    sleeper: Callable[[float], None] = time.sleep,
    emit: Callable[[str], None] = print,
    error_emit: Callable[[str], None] = lambda message: print(message, file=sys.stderr),
    max_iterations: int | None = None,
) -> int:
    """Run one-shot or repeated worker cycles with bounded exponential backoff."""
    failures = 0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        action_required = False
        try:
            result = worker.run_once()
        except Exception:
            error_emit("MIC outbound worker iteration failed; retrying safely")
            failed = True
        else:
            _emit_result(result, emit)
            failed = _iteration_failed(result)
            action_required = result.action_required

        if once:
            return 1 if failed or action_required else 0
        if max_iterations is not None and iterations >= max_iterations:
            break

        if failed:
            failures = min(failures + 1, 16)
            delay = min(interval_seconds * (2 ** (failures - 1)), MAX_BACKOFF_SECONDS)
        else:
            failures = 0
            delay = interval_seconds
        sleeper(delay)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = CrmBridgeConfig.from_env()
        worker = _build_worker(config)
    except Exception:
        print(
            "MIC outbound worker startup failed; check bridge configuration "
            "and registered credentials",
            file=sys.stderr,
        )
        return 2

    try:
        return run_loop(
            worker,
            interval_seconds=args.interval,
            once=args.once,
        )
    except KeyboardInterrupt:
        print("MIC outbound worker stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
