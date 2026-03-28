"""
Проверка проверки кода урока: парсер ответа + цепочка review_submission с моком Groq.
При наличии реального GROQ_API_KEY (не dummy) — одна интеграция с API.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# До импорта config
os.environ.setdefault("TELEGRAM_TOKEN", "dummy-for-test")
os.environ.setdefault("GROQ_API_KEY", os.environ.get("GROQ_API_KEY") or "dummy-for-test")
os.environ.setdefault("HUGGING_FACE_TOKEN", "dummy-for-test")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curriculum import get_lesson  # noqa: E402
from enhanced_ai_handler import (  # noqa: E402
    CODE_REVIEW_SYSTEM_PROMPT,
    EnhancedAIHandler,
    _parse_submission_review,
)


class TestParseSubmissionReview(unittest.TestCase):
    def test_ok_multiline(self):
        status, fb = _parse_submission_review(
            'OK\nКнопка есть — отлично 👍\nДобавь type="button", чтобы не слать форму.'
        )
        self.assertEqual(status, "OK")
        self.assertIn("Кнопка", fb)
        self.assertIn("type", fb)

    def test_error_multiline(self):
        status, fb = _parse_submission_review(
            "ERROR\nПока нет тега <button>\nПопробуй добавить его внутрь <body>"
        )
        self.assertEqual(status, "ERROR")
        self.assertIn("button", fb.lower())

    def test_ok_empty_rest(self):
        status, fb = _parse_submission_review("OK\n")
        self.assertEqual(status, "OK")
        self.assertTrue(len(fb) > 5)

    def test_error_empty_rest(self):
        status, fb = _parse_submission_review("ERROR")
        self.assertEqual(status, "ERROR")
        self.assertTrue(len(fb) > 5)

    def test_prompt_mentor_checklist(self):
        low = CODE_REVIEW_SYSTEM_PROMPT.lower()
        self.assertIn("чеклист", low)
        self.assertIn("ментор", low)


GOOD_M1_L1 = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>тест</title></head>
<body>
<button type="button">Нажми</button>
</body>
</html>"""

BAD_M1_L1 = """<html><body><button>Нажми</button></body></html>"""


def _make_handler_with_mock_groq(content: str) -> EnhancedAIHandler:
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=content))]
    h = EnhancedAIHandler.__new__(EnhancedAIHandler)
    h.groq_client = MagicMock()
    h.groq_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    return h


class TestReviewSubmissionMock(unittest.IsolatedAsyncioTestCase):
    async def test_ok_flow(self):
        L = get_lesson("M1-L1")
        h = _make_handler_with_mock_groq(
            'OK\nКнопка в body — вижу 👍\ntype="button" стоит как надо.'
        )
        r = await h.review_submission(
            "M1-L1",
            L["task"],
            list(L["checklist"]),
            GOOD_M1_L1,
        )
        self.assertEqual(r["status"], "OK")
        self.assertIn("Кнопка", r["feedback"])
        h.groq_client.chat.completions.create.assert_called_once()
        kwargs = h.groq_client.chat.completions.create.call_args.kwargs
        self.assertIn("messages", kwargs)
        user_msg = kwargs["messages"][1]["content"]
        self.assertIn("M1-L1", user_msg)
        self.assertIn("Чеклист", user_msg)
        self.assertIn("type", user_msg.lower())
        self.assertIn("button", user_msg.lower())

    async def test_error_flow(self):
        L = get_lesson("M1-L1")
        h = _make_handler_with_mock_groq(
            'ERROR\nАтрибут type="button" не указан — без него в форме кнопка может уехать в submit.\nДобавь type="button" к тегу.'
        )
        r = await h.review_submission(
            "M1-L1",
            L["task"],
            list(L["checklist"]),
            BAD_M1_L1,
        )
        self.assertEqual(r["status"], "ERROR")
        self.assertTrue(len(r["feedback"]) < 600)


async def _live_groq_once() -> None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key or key.startswith("dummy") or len(key) < 15:
        print("\n[live] Пропуск: нет реального GROQ_API_KEY в окружении.")
        return
    from enhanced_ai_handler import enhanced_ai_handler

    L = get_lesson("M1-L1")
    print("\n[live] Запрос к Groq (хороший код M1-L1)...")
    r_ok = await enhanced_ai_handler.review_submission(
        "M1-L1",
        L["task"],
        list(L["checklist"]),
        GOOD_M1_L1,
    )
    print(f"  status={r_ok['status']!r}")
    print(f"  feedback={r_ok['feedback']!r}")

    print("\n[live] Запрос к Groq (плохой код — без type)...")
    r_bad = await enhanced_ai_handler.review_submission(
        "M1-L1",
        L["task"],
        list(L["checklist"]),
        BAD_M1_L1,
    )
    print(f"  status={r_bad['status']!r}")
    print(f"  feedback={r_bad['feedback']!r}")

    if r_ok["status"] != "OK":
        raise SystemExit("[live] Ожидали OK для корректного решения M1-L1")
    if r_bad["status"] != "ERROR":
        print("[live] Предупреждение: для кода без type модель вернула OK — возможна мягкая проверка.")


def main() -> None:
    unittest.main(exit=False, verbosity=2)
    asyncio.run(_live_groq_once())


if __name__ == "__main__":
    main()
