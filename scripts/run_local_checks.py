#!/usr/bin/env python3
"""
Локальные проверки перед деплоем: компиляция, unittest, импорты с изолированным env.
Запуск из корня репозитория: python scripts/run_local_checks.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=str(ROOT), **kwargs)


def main() -> int:
    os.chdir(ROOT)
    errors = 0

    # 1) Компиляция ключевых модулей (без обхода venv)
    core = [
        "main.py",
        "course_handler.py",
        "user_progress.py",
        "scheduler_course.py",
        "render_entrypoint.py",
        "curriculum.py",
        "config.py",
        "enhanced_ai_handler.py",
    ]
    r = run([PY, "-m", "py_compile", *core], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        errors += 1
    else:
        print("OK py_compile", len(core), "files")

    # 2) verify_lesson_cooldown
    r = run([PY, str(ROOT / "scripts" / "verify_lesson_cooldown.py")], capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    if r.returncode != 0:
        errors += 1

    # 3) unittest (мок Groq, без сети)
    env = {**os.environ, "TELEGRAM_TOKEN": "0:smoke-test", "BOT_TOKEN": "0:smoke-test", "GROQ_API_KEY": "dummy"}
    r = run(
        [PY, "-m", "unittest", "test_code_review", "-v"],
        env=env,
        capture_output=True,
        text=True,
    )
    # печатаем только хвост, если ок — кратко
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        errors += 1
    else:
        for ln in r.stdout.splitlines():
            if ln.startswith("Ran ") or ln == "OK":
                print(ln)

    # 4) Изолированные импорты course_handler: CHAT_ID (свой env без CHAT_ID из родителя)
    env_base = os.environ.copy()
    env_base["TELEGRAM_TOKEN"] = "0:smoke-test"
    env_base["BOT_TOKEN"] = "0:smoke-test"
    env_base["GROQ_API_KEY"] = "dummy"
    env_base.pop("CHAT_ID", None)

    code1 = """
import os
os.environ["CHAT_ID"] = " -1001234567890 "
import importlib
ch = importlib.import_module("course_handler")
assert ch.COURSE_GROUP_CHAT_ID == -1001234567890, ch.COURSE_GROUP_CHAT_ID
assert ch.is_course_target_group(-1001234567890)
assert not ch.is_course_target_group(1)
assert ch.CHAT_ID == "-1001234567890"
assert ch.bot_deeplink_course("MyBot") == "https://t.me/MyBot?start=course"
assert ch.bot_deeplink_open_chat("MyBot") == "https://t.me/MyBot"
print("OK CHAT_ID strip + is_course_target_group + deeplinks")
"""
    r = run([PY, "-c", code1], env=env_base, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    if r.returncode != 0:
        errors += 1

    code2 = """
import os
# subprocess уже без CHAT_ID; dotenv подтянет .env — поэтому явно чистим перед импортом
os.environ.pop("CHAT_ID", None)
from course_handler import _parse_course_group_chat_id
assert _parse_course_group_chat_id(None) is None
assert _parse_course_group_chat_id("") is None
assert _parse_course_group_chat_id("  -100  ") == -100
print("OK _parse_course_group_chat_id")
"""
    env_no_chat = env_base.copy()
    env_no_chat.pop("CHAT_ID", None)
    r = run([PY, "-c", code2], env=env_no_chat, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    if r.returncode != 0:
        errors += 1

    # 5) curriculum + user_progress без course_handler
    code3 = """
import curriculum
assert len(curriculum.LESSON_ORDER) >= 1
getattr(curriculum, "get_lesson")(curriculum.LESSON_ORDER[0])
print("OK curriculum")
"""
    r = run([PY, "-c", code3], env=env_base, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode != 0:
        errors += 1

    # 6) import main (без запуска event loop)
    code4 = """
import os
os.environ.setdefault("TELEGRAM_TOKEN", "0:smoke-test")
os.environ.setdefault("BOT_TOKEN", "0:smoke-test")
os.environ.setdefault("GROQ_API_KEY", "dummy")
os.environ.setdefault("CHAT_ID", "-1001")
import main
assert hasattr(main, "version_handler")
print("OK import main")
"""
    r = run([PY, "-c", code4], env=env_base, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    if r.returncode != 0:
        errors += 1

    if errors:
        print(f"\nFAILED: {errors} step(s)", flush=True)
        return 1
    print("\nALL CHECKS PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
