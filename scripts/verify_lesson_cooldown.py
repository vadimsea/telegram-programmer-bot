#!/usr/bin/env python3
"""Проверка в терминале: нет старого текста про «~1 мин» и логика cooldown после успеха."""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    old_snippet = "Между уроками короткая пауза"
    main_py = os.path.join(ROOT, "main.py")
    text = open(main_py, encoding="utf-8").read()
    if old_snippet in text:
        print("FAIL: в main.py всё ещё есть старый текст про паузу ~1 мин")
        return 1
    if "Только что выдал урок" not in text and "С последней выдачи урока" not in text:
        print("FAIL: в main.py нет нового текста rate-hint для /start course")
        return 1

    from user_progress import UserProgressManager, get_lesson_cooldown_seconds

    sec = get_lesson_cooldown_seconds()
    if not (5 <= sec <= 120):
        print(f"FAIL: get_lesson_cooldown_seconds()={sec} вне [5,120]")
        return 1

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        path = f.name
        f.write("{}")
    try:
        m = UserProgressManager(path)
        uid = 42424242
        assert not m.is_lesson_request_cooldown(uid), "без mark не должно быть cooldown"
        assert not m.is_lesson_request_cooldown(uid)
        m.mark_lesson_request_done(uid)
        assert m.is_lesson_request_cooldown(uid), "после mark должен быть cooldown"
        print("OK: main.py без старого текста; cooldown только после mark_lesson_request_done")
        print(f"OK: lesson_cooldown_sec={sec}")
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
