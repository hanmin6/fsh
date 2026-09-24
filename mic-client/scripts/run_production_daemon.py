"""Production Supervisor for Made-in-China (MIC) Integration.

Launches and supervises both:
1. MIC Gateway (Playwright browser & sync runtime on 127.0.0.1:8787)
2. MIC CRM Bridge Daemon (pushes synced messages to EspoCRM)

Handles process supervision, automatic restart on transient crash, and graceful shutdown.
"""
from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    python_exe = sys.executable

    print("=" * 65)
    print(" Made-in-China (MIC) Gateway & CRM Bridge Production Supervisor")
    print(f" Working Directory: {root}")
    print(f" Python: {python_exe}")
    print("=" * 65)

    running = True

    def _sig_handler(sig, frame):
        nonlocal running
        print("\n[Supervisor] Received shutdown signal. Terminating child processes...")
        running = False

    signal.signal(signal.SIGINT, _sig_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _sig_handler)

    port = int(os.environ.get("MIC_PORT", "8787"))
    host = os.environ.get("MIC_HOST", "127.0.0.1")

    gateway_cmd = [
        python_exe, "-m", "uvicorn",
        "mic_gateway.main:create_production_app",
        "--factory",
        "--host", host,
        "--port", str(port)
    ]

    bridge_cmd = [
        python_exe, "-m", "mic_gateway.crm_bridge.cli", "daemon",
        "--interval", "30"
    ]

    gateway_proc = None
    bridge_proc = None

    try:
        print("[Supervisor] Starting MIC Gateway API...")
        gateway_proc = subprocess.Popen(gateway_cmd, cwd=str(root))

        for _ in range(5):
            if not running:
                break
            time.sleep(1)

        print("[Supervisor] Starting MIC CRM Bridge Daemon...")
        bridge_proc = subprocess.Popen(bridge_cmd, cwd=str(root))

        while running:
            # Check gateway health
            g_ret = gateway_proc.poll()
            if g_ret is not None and running:
                print(f"[Supervisor] Warning: MIC Gateway exited with code {g_ret}. Restarting...")
                gateway_proc = subprocess.Popen(gateway_cmd, cwd=str(root))

            # Check bridge health
            b_ret = bridge_proc.poll()
            if b_ret is not None and running:
                print(f"[Supervisor] Warning: CRM Bridge exited with code {b_ret}. Restarting...")
                bridge_proc = subprocess.Popen(bridge_cmd, cwd=str(root))

            time.sleep(2)

    finally:
        print("[Supervisor] Shutting down child processes...")
        for proc in (bridge_proc, gateway_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[Supervisor] All services stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
