from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any, TextIO

from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.crm_client import (
    CrmAuthError,
    CrmClient,
    CrmPermanentError,
    CrmTransientError,
)
from mic_gateway.crm_bridge.importer import (
    IncompleteHistoryError,
    MicCrmImporter,
    MicReadClient,
    PendingBatchConflictError,
    ReadGatewayAuthError,
    ReadGatewayError,
    ReadGatewayTransientError,
)
from mic_gateway.crm_bridge.state import CrmBridgeState

MIN_DAEMON_INTERVAL_SECONDS = 0.1
MAX_DAEMON_INTERVAL_SECONDS = 3_600.0


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    config: CrmBridgeConfig | None = None,
    gateway: Any | None = None,
    crm: Any | None = None,
    state: CrmBridgeState | None = None,
    output: TextIO | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    max_iterations: int | None = None,
) -> int:
    """Run the bridge operator command; injected clients keep tests offline."""
    stream = output or sys.stdout
    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.command == "daemon" and (
        not math.isfinite(args.interval)
        or args.interval < MIN_DAEMON_INTERVAL_SECONDS
        or args.interval > MAX_DAEMON_INTERVAL_SECONDS
    ):
        print(
            "daemon interval must be between 0.1 and 3600 seconds",
            file=stream,
        )
        return 2
    try:
        settings = config or CrmBridgeConfig.from_env()
        settings.validate()
        checkpoint = state or CrmBridgeState(settings.app_data_dir)
        if args.command == "status":
            return _status(checkpoint, stream)
        if args.command == "resolve-pending":
            return _resolve_pending(checkpoint, args, stream)
        crm_client = crm or CrmClient(
            settings.crm_base_url,
            settings.crm_agent_key,
            settings.crm_agent_token,
        )
        if args.command == "register":
            if not settings.crm_bootstrap_token:
                print("MIC_CRM_BOOTSTRAP_TOKEN is required for register", file=stream)
                return 2
            token = crm_client.register(settings.crm_bootstrap_token, rotate=not args.no_rotate)
            # This is the one intentional secret display: CRM-issued token is returned once.
            print(token, file=stream)
            return 0
        if not settings.crm_agent_token:
            print(
                "MIC_CRM_AGENT_TOKEN is required; run register and set the issued token",
                file=stream,
            )
            return 2
        read_gateway = gateway or MicReadClient(settings.mic_base_url, settings.mic_read_api_key)
        importer = MicCrmImporter(
            read_gateway,
            crm_client,
            checkpoint,
            account_handle=settings.account_handle,
        )
        if args.command == "backfill":
            result = importer.backfill()
            print(_result_json("backfill", result), file=stream)
            return 0
        if args.command == "once":
            result = importer.once()
            print(_result_json("once", result), file=stream)
            return 0
        if args.command == "daemon":
            iterations = 0
            transient_failures = 0
            while max_iterations is None or iterations < max_iterations:
                try:
                    result = importer.once()
                except (CrmTransientError, ReadGatewayTransientError) as exc:
                    transient_failures += 1
                    print(
                        json.dumps({"status": "retrying", "error": _safe_error_code(exc)}),
                        file=stream,
                    )
                else:
                    print(_result_json("once", result), file=stream)
                    transient_failures = 0
                iterations += 1
                if max_iterations is None or iterations < max_iterations:
                    delay = min(
                        args.interval * (2 ** min(transient_failures, 10)),
                        MAX_DAEMON_INTERVAL_SECONDS,
                    )
                    sleeper(delay)
            return 0
        parser.print_help(file=stream)
        return 2
    except KeyboardInterrupt:
        print("daemon stopped", file=stream)
        return 130
    except PendingBatchConflictError as exc:
        print(
            json.dumps(
                {
                    "status": "action_required",
                    "error": "pending_batch_conflict",
                    "resource": exc.resource,
                    "requestId": exc.request_id,
                }
            ),
            file=stream,
        )
        return 1
    except Exception as exc:
        # Print a stable code only; arbitrary transport or library text may carry secrets.
        print(f"MIC CRM bridge failed: {_safe_error_code(exc)}", file=stream)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mic-crm-bridge")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="register or rotate the MIC CRM Agent")
    register.add_argument(
        "--no-rotate", action="store_true", help="keep an existing Agent credential"
    )
    commands.add_parser("backfill", help="import all complete MIC conversation history")
    commands.add_parser("once", help="reread MIC history and import source updates")
    daemon = commands.add_parser("daemon", help="repeat MIC history sweeps on an interval")
    daemon.add_argument("--interval", type=float, default=60.0, help="seconds between sweeps")
    commands.add_parser("status", help="show non-secret import checkpoint state")
    resolve = commands.add_parser(
        "resolve-pending",
        help="resolve a pending batch conflict after checking the CRM audit requestId",
        description=(
            "Before choosing either resolution, verify the exact requestId in the CRM "
            "AutomationAudit record. Leave state unchanged if audit status is ambiguous."
        ),
    )
    resolve.add_argument("resource", choices=("conversations", "conversations:once"))
    resolve.add_argument("--request-id", required=True)
    decision = resolve.add_mutually_exclusive_group(required=True)
    decision.add_argument(
        "--verified-accepted",
        action="store_true",
        help="advance only after verifying CRM audit accepted this exact requestId",
    )
    decision.add_argument(
        "--verified-not-accepted",
        action="store_true",
        help="clear pending state only after verifying CRM did not accept this requestId",
    )
    return parser


def _status(state: CrmBridgeState, output: TextIO) -> int:
    resources = ("conversations", "conversations:once")
    rows: dict[str, dict[str, Any]] = {}
    for resource in resources:
        pending = state.pending_batch(resource)
        conflict = pending is not None and pending.get("conflict") is True
        rows[resource] = {
            "checkpoint": state.checkpoint(resource),
            "pendingRequestId": pending.get("request_id") if pending else None,
            "pending": pending is not None,
            "actionRequired": conflict,
            "actionCode": "pending_batch_conflict" if conflict else None,
        }
    print(
        json.dumps(
            {
                "statePath": str(state.path),
                "resources": rows,
                "manualResolutions": state.manual_resolutions(limit=10),
            },
            ensure_ascii=False,
        ),
        file=output,
    )
    return 0


def _resolve_pending(state: CrmBridgeState, args: Any, output: TextIO) -> int:
    print(
        "OPERATOR CHECK REQUIRED: Verify CRM AutomationAudit for this exact requestId "
        "before resolving.",
        file=output,
    )
    pending = state.pending_batch(args.resource)
    if pending is None or pending.get("conflict") is not True:
        print("No pending batch conflict requires operator resolution", file=output)
        return 2
    if pending.get("request_id") != args.request_id:
        print("requestId does not match the pending conflict", file=output)
        return 2
    accepted = bool(args.verified_accepted)
    state.resolve_pending_by_operator(args.resource, args.request_id, accepted=accepted)
    outcome = "verified_acceptance_confirmed" if accepted else "pending_cleared_without_advance"
    print(
        json.dumps(
            {
                "status": "resolved",
                "resource": args.resource,
                "requestId": args.request_id,
                "resolution": outcome,
            }
        ),
        file=output,
    )
    return 0


def _result_json(mode: str, result: Any) -> str:
    return json.dumps(
        {
            "mode": mode,
            "conversations": result.conversations,
            "messages": result.messages,
            "batches": result.batches,
            "actionRequiredCodes": result.action_required_codes,
        }
    )


def _safe_error_code(error: Exception) -> str:
    if isinstance(error, CrmAuthError):
        return "crm_auth"
    if isinstance(error, CrmTransientError):
        return "crm_unavailable"
    if isinstance(error, CrmPermanentError):
        return "crm_rejected"
    if isinstance(error, PendingBatchConflictError):
        return "pending_batch_conflict"
    if isinstance(error, ReadGatewayAuthError):
        return "mic_gateway_auth"
    if isinstance(error, ReadGatewayTransientError):
        return "mic_gateway_unavailable"
    if isinstance(error, IncompleteHistoryError):
        return "incomplete_history"
    if isinstance(error, ReadGatewayError):
        return "mic_gateway_error"
    return "unexpected_error"


if __name__ == "__main__":
    raise SystemExit(main())
