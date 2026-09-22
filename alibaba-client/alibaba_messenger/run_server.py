# -*- coding: utf-8 -*-
import argparse
import asyncio
import sys
import uvicorn
from alibaba_messenger.config import settings
from alibaba_messenger.alibaba_bot import bot
from alibaba_messenger.server import app

def parse_args():
    parser = argparse.ArgumentParser(description="阿里巴巴国际站 Playwright 自动发信服务")
    parser.add_argument("--host", default=settings.SERVER_HOST, help="监听主机IP (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=settings.SERVER_PORT, help="监听端口 (默认: 8000)")
    parser.add_argument("--headless", action="store_true", help="是否以无头模式运行(未登录时请勿使用)")
    return parser.parse_args()

async def init_and_run(args):
    print("=" * 70)
    print("★ 正在启动阿里巴巴国际站自动发消息服务 (Playwright + FastAPI) ★")
    print("=" * 70)
    
    try:
        # 1. 启动持久化 Chromium
        print(f"[Init] 载入持久化用户配置目录: {settings.PROFILE_DIR}")
        await bot.start(headless=args.headless)
        
        # 2. 检查登录状态
        if not bot.is_logged_in:
            print("[Notice] 尚未登录，主进程等待登录完成...")
            await bot.check_and_handle_login()
        
        print("\n" + "-" * 70)
        print(">>> 自动化控制器已就绪，正在启动 HTTP API 接口服务 <<<")
        print(f"  * 接口文档地址: http://127.0.0.1:{args.port}/docs")
        print(f"  * 状态探活接口: GET  http://127.0.0.1:{args.port}/api/status")
        print(f"  * 消息发送接口: POST http://127.0.0.1:{args.port}/api/message/send")
        print("-" * 70 + "\n")
        
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    finally:
        await bot.close()

def main():
    args = parse_args()
    try:
        asyncio.run(init_and_run(args))
    except KeyboardInterrupt:
        print("\n[Server] 接收到退出信号，服务正在安全关闭...")

if __name__ == "__main__":
    main()
