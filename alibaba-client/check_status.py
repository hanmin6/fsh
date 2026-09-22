# -*- coding: utf-8 -*-
"""Health check and status verifier for Alibaba Messenger & CRM."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass

from alibaba_messenger.config import settings
from alibaba_messenger.crm_gateway import CrmGateway


def check_all() -> None:
    print("=" * 65)
    print("          富三和 - 阿里国际站自动化运行状态自检")
    print("=" * 65)

    # 1. 检查 Docker CRM API
    print("\n[1] 检查 CRM 平台与接口状态...")
    try:
        req = urllib.request.Request(
            f"{settings.CRM_API_URL}/App/user",
            headers={"X-Api-Key": settings.AGENT_TOKEN}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                print(f"  √ CRM API 服务正常响应 (HTTP {resp.getcode()}, 端口 18080)")
        except urllib.error.HTTPError as he:
            if he.code == 401:
                print("  √ CRM API 服务在线 (端口 18080 正常监听，HTTP 401 鉴权生效)")
            else:
                print(f"  ! CRM 响应状态码: HTTP {he.code}")
    except Exception as e:
        print(f"  × 无法连接到 CRM (端口 18080): {e}")

    try:
        gw = CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN)
        print(f"  √ CRM 网关配置就绪: Agent Key = {gw.agent_key}")
    except Exception as e:
        print(f"  × CRM 网关异常: {e}")

    # 2. 检查本地同步数据库与已追踪商机
    print("\n[2] 检查本地同步数据库与已追踪商机...")
    try:
        db_path = settings.SYNC_DB_PATH
        if not os.path.exists(db_path):
            print(f"  ! 同步数据库尚未生成: {db_path}")
        else:
            conn = sqlite3.connect(db_path)
            job_count = conn.execute("SELECT count(*) FROM sync_job WHERE status='completed'").fetchone()[0]
            tracked_count = conn.execute("SELECT count(*) FROM tracked_conversation").fetchone()[0]
            print(f"  √ 累计完成同步作业数: {job_count} 次")
            print(f"  √ 正在实时监测与追踪的商机数: {tracked_count} 个")

            recent = conn.execute(
                "SELECT buyer_name, last_time, unread_count, inquiry_id FROM tracked_conversation ORDER BY last_synced_at DESC LIMIT 3"
            ).fetchall()
            if recent:
                print("    最新监控样本:")
                for b_name, l_time, unread, inq_id in recent:
                    print(f"    - 商机: {inq_id} | 买家: {b_name} | 时间: {l_time} | 未读: {unread}")
            conn.close()
    except Exception as e:
        print(f"  × 同步数据库读取异常: {e}")

    # 3. 检查后台运行的 Python 进程
    print("\n[3] 检查系统后台自动化运行进程...")
    try:
        res = subprocess.run(
            ["powershell", "-Command", "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Select-Object -Property ProcessId, CommandLine"],
            capture_output=True, text=True, errors="replace"
        )
        lines = [l.strip() for l in res.stdout.strip().split("\n") if l.strip()]
        daemon_found = False
        worker_found = False
        for l in lines:
            if "run_sync" in l and "daemon" in l:
                daemon_found = True
            if "run_worker" in l:
                worker_found = True

        if daemon_found:
            print("  √ 消息自动抓取守护进程 (run_sync.py daemon): [运行中]")
        else:
            print("  - 消息自动抓取守护进程 (run_sync.py daemon): [未运行]")

        if worker_found:
            print("  √ 外呼发送守护进程 (run_worker.py): [运行中]")
        else:
            print("  - 外呼发送守护进程 (run_worker.py): [未运行]")
    except Exception as e:
        print(f"  ! 进程检测异常: {e}")

    print("\n" + "=" * 65)
    print("状态提示: 若守护进程未运行，可双击 start_all.bat 或手动启动。")
    print("=" * 65)


if __name__ == "__main__":
    check_all()
