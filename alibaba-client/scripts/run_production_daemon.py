"""Production Daemon Supervisor for Alibaba Client.

Orchestrates the Alibaba incremental sync daemon with keep-alive,
automatic crash restart with backoff, and clean shutdown handling.
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

    print("=" * 60)
    print(" Alibaba Production Sync Daemon Supervisor")
    print(f" Working Directory: {root}")
    print(f" Python: {python_exe}")
    print("=" * 60)

    env_file = root / ".env"
    if env_file.exists():
        print(f"[Supervisor] Loading environment from {env_file}")

    cmd = [python_exe, "-m", "alibaba_messenger.run_sync", "daemon", "--interval", "60"]
    if "--headless" in sys.argv:
        cmd.append("--headless")

    running = True

    def _sig_handler(sig, frame):
        nonlocal running
        print("\n[Supervisor] Received shutdown signal. Terminating children...")
        running = False

    signal.signal(signal.SIGINT, _sig_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _sig_handler)

    restart_count = 0
    max_restarts = 50
    backoff = 3

    while running and restart_count < max_restarts:
        print(f"[Supervisor] Launching daemon process (attempt {restart_count + 1})...")
        start_time = time.time()
        proc = subprocess.Popen(cmd, cwd=str(root))

        while running:
            ret = proc.poll()
            if ret is not None:
                duration = time.time() - start_time
                print(f"[Supervisor] Daemon exited with code {ret} after {int(duration)}s.")
                if ret == 0:
                    print("[Supervisor] Clean exit requested.")
                    return 0
                restart_count += 1
                if duration > 120:
                    restart_count = 1  # Reset restart count if it was healthy for > 2 mins
                print(f"[Supervisor] Re-spawning in {backoff}s...")
                time.sleep(backoff)
                break
            time.sleep(1)

        if not running and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    return 0


if __name__ == "__main__":
    sys.exit(main())
