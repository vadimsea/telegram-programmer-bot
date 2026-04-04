"""
Симуляция пользователя — все ветки кода. Groq заменён mock-ом.
"""
import os, sys, asyncio, json
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('TELEGRAM_TOKEN', '0:x')
os.environ.setdefault('BOT_TOKEN', '0:x')
os.environ.setdefault('GROQ_API_KEY', 'gsk_test_mock')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from enhanced_ai_handler import EnhancedAIHandler

# ---- Mock Groq --------------------------------------------------------
def _make_groq_mock(reply_text="[GROQ_MOCK] Понял вопрос, отвечаю подробно."):
    mock_choice = MagicMock()
    mock_choice.message.content = reply_text
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    groq_mock = MagicMock()
    groq_mock.chat = MagicMock()
    groq_mock.chat.completions = MagicMock()
    groq_mock.chat.completions.create = AsyncMock(return_value=mock_response)
    return groq_mock

# -----------------------------------------------------------------------

class FakeCtx:
    def __init__(self):
        self.user_id = 42
        self.skill_level = "beginner"
        self.preferences = {'favorite_languages': [], 'learning_goals': []}
        self.history = []
        self.last_tip_text = None

    def add_message(self, role, content):
        self.history.append({'role': role, 'content': content})

    def get_recent_context(self, n):
        return self.history[-n:]


async def ask(handler, ctx, msg):
    resp, is_fb = await handler.get_specialized_response(
        msg, "general", ctx,
        skill_level=ctx.skill_level,
        preferences=ctx.preferences,
    )
    ctx.add_message("user", msg)
    ctx.add_message("assistant", resp)
    return resp, is_fb


TESTS = [
    # ---- SMALL TALK ----
    ("привет", "small_talk"),
    ("как дела?", "small_talk"),
    ("доброе утро", "small_talk"),
    ("спасибо!", "small_talk"),
    ("расскажи о себе", "small_talk"),
    ("ты онлайн?", "small_talk"),
    ("помнишь меня?", "small_talk"),

    # ---- STATIC HANDLERS (без Groq) ----
    ("как начать изучать html и css?", "static_roadmap"),
    ("с чего начать программирование?", "static_learning"),
    ("калькулятор на javascript", "static_calc_js"),
    ("калькулятор на python", "static_calc_py"),
    ("найди ошибку: ```js\nfor(i=0; i<5; i++) {}\n```", "static_js_analyzer"),
    ("объясни этот код: console.log('hello')", "groq"),

    # ---- ТЕХНИЧЕСКИЕ → должны идти в Groq ----
    ("что такое promise в javascript?", "groq"),
    ("не работает fetch, выдаёт CORS ошибку", "groq"),
    ("как сделать flexbox по центру?", "groq"),
    ("объясни замыкание", "groq"),
    ("у меня баг в цикле for", "groq"),
    ("как работает async await?", "groq"),
    ("что такое event loop?", "groq"),
    ("в чём разница между let const var?", "groq"),
    ("как подключить css к html?", "groq"),

    # ---- НЕ-IT ТЕМЫ → должны уходить в Groq (system prompt сам ответит) ----
    ("как приготовить борщ?", "groq"),
    ("посоветуй фильм", "groq"),
    ("расскажи анекдот", "groq"),

    # ---- ЭМОЦИОНАЛЬНЫЕ ----
    ("блять ничего не работает, надоело", "groq"),
    ("ура! получилось наконец!", "groq"),

    # ---- ПУСТЫЕ / МУСОР ----
    ("", "fallback_or_groq"),
    ("   ", "fallback_or_groq"),
    ("???", "fallback_or_groq"),
    ("123456", "fallback_or_groq"),

    # ---- ДЛИННЫЙ КОД БЕЗ БЭКТИКОВ ----
    (
        "найди ошибку:\nfunction go() {\n  let x = 1\n  if (x = 2) {\n    console.log('yes')\n  }\n}",
        "groq_or_static"
    ),
]

async def main():
    handler = EnhancedAIHandler()
    handler.groq_client = _make_groq_mock()

    ctx = FakeCtx()
    out_lines = []
    issues = []

    for msg, expected_route in TESTS:
        resp, is_fb = await ask(handler, ctx, msg)
        route = "FALLBACK" if is_fb else "GROQ/STATIC"

        # --- Проверяем качество ответа ---
        problems = []
        if not resp or not resp.strip():
            problems.append("ПУСТОЙ ОТВЕТ")
        if len(resp) < 10:
            problems.append(f"СЛИШКОМ КОРОТКИЙ: {len(resp)} chars")
        if resp.startswith("Что-то пошло не так") and expected_route == "groq":
            problems.append("GENERIC FALLBACK вместо реального ответа")
        if resp.startswith("❌ Не могу найти код"):
            problems.append("CODE NOT FOUND — пользователь отправил код, но бот его не увидел")
        if "Быстрый ответ из кэша" in resp:
            problems.append("ЗАКЕШИРОВАННЫЙ ОТВЕТ — может быть устаревшим")
        # Проверяем: не слишком ли много блоков GROQ_MOCK в ответе
        if "[GROQ_MOCK]" in resp and len(resp) < 30:
            problems.append("MOCK ответ не обработан")

        status = "OK"
        if problems:
            status = "ISSUE"
            issues.append((msg[:50], problems))

        preview = resp[:150].replace('\n', ' ')
        out_lines.append(f"[{status}] [{route}]")
        out_lines.append(f"  IN:  {repr(msg[:60])}")
        out_lines.append(f"  OUT: {preview}")
        if problems:
            for p in problems:
                out_lines.append(f"  ⚠️  {p}")
        out_lines.append("")

    out_lines.append("=" * 60)
    out_lines.append(f"ИТОГО: {len(TESTS)} тестов | Проблем: {len(issues)}")
    if issues:
        out_lines.append("\nПРОБЛЕМЫ:")
        for inp, probs in issues:
            out_lines.append(f"  '{inp}' → {', '.join(probs)}")

    result = '\n'.join(out_lines)
    with open('simulate_full.txt', 'w', encoding='utf-8') as f:
        f.write(result)
    print("Written to simulate_full.txt")


asyncio.run(main())
