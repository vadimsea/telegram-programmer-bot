"""
Render entrypoint (health + bot supervisor).

Render поднимает сервис как Web service и ожидает, что процесс будет держать порт
и отвечать на health-check. Если Telegram polling/инициализация падает и основной
процесс завершается, Render помечает сервис как Down.

Этот entrypoint:
1) Всегда поднимает HTTP health server на process.env.PORT.
2) Запускает main.py в отдельном subprocess.
3) При падении main.py автоматически перезапускает его с backoff.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from typing import Optional

from aiohttp import web


PORT = int(os.getenv("PORT", "8000"))
BOT_MAIN = os.getenv("BOT_MAIN", "main.py")
RESTART_BACKOFF_S = float(os.getenv("BOT_RESTART_BACKOFF_S", "2"))
RESTART_BACKOFF_MAX_S = float(os.getenv("BOT_RESTART_BACKOFF_MAX_S", "60"))


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def run_bot_subprocess_forever(stop_event: asyncio.Event) -> None:
    """
    Запускает main.py как subprocess и перезапускает при завершении.
    """
    backoff_s = RESTART_BACKOFF_S
    proc: Optional[subprocess.Popen] = None

    while not stop_event.is_set():
        # Запускаем отдельный процесс с теми же env.
        proc = subprocess.Popen([sys.executable, BOT_MAIN], env=os.environ)
        try:
            exit_code = await asyncio.to_thread(proc.wait)
        finally:
            # На случай если subprocess был убит/подвис.
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        if stop_event.is_set():
            break

        # main.py завершился: логируем и перезапускаем.
        # (stdout/stderr subprocess наследуют вывод контейнера Render, поэтому логи будут видны.)
        # Удваиваем backoff, чтобы не спамить при постоянной ошибке запуска.
        print(f"[supervisor] main.py exited with code {exit_code}. Restarting in {backoff_s:.1f}s...", flush=True)
        await asyncio.sleep(backoff_s)
        backoff_s = min(backoff_s * 2, RESTART_BACKOFF_MAX_S)


async def main() -> None:
    stop_event = asyncio.Event()

    def _stop(*_: object) -> None:
        stop_event.set()

    # SIGTERM — основной сигнал для остановки на Render.
    try:
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
    except Exception:
        # На некоторых платформах могут быть ограничения на signal.
        pass

    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    print(f"[supervisor] Health server running on port {PORT}", flush=True)

    try:
        await run_bot_subprocess_forever(stop_event)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

