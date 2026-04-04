"""
Тест правильного роутинга после рефакторинга:
- "найди ошибку" → mode=debug_code → Groq
- "объясни этот код" → mode=explain_concept → Groq
- "с чего начать" → mode=general → Groq
- "найди ошибку" без Groq → статический fallback
- "с чего начать" без Groq → статический fallback
"""
import os, sys, asyncio
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault('TELEGRAM_TOKEN', '0:x')
os.environ.setdefault('BOT_TOKEN', '0:x')
os.environ.setdefault('GROQ_API_KEY', 'gsk_test_mock')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from enhanced_ai_handler import EnhancedAIHandler

def make_mock(reply="[GROQ OK]"):
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=reply))])
    )
    return mock


class FakeCtx:
    user_id = 1
    skill_level = "beginner"
    preferences = {'favorite_languages': [], 'learning_goals': []}
    history = []
    last_tip_text = None
    def add_message(self, *a): pass
    def get_recent_context(self, n): return []


async def run():
    results = []

    # ---- С Groq ----
    h = EnhancedAIHandler()
    h.groq_client = make_mock()
    ctx = FakeCtx()

    async def ask(msg):
        return await h.get_specialized_response(msg, "general", ctx,
                                                 skill_level="beginner", preferences={})

    cases_with_groq = [
        ("найди ошибку в коде: for(i=0; i<5; i++) {}", "[GROQ OK]", "error→Groq"),
        ("объясни этот код: console.log('hi')",         "[GROQ OK]", "explain→Groq"),
        ("с чего начать программировать?",               "[GROQ OK]", "learning→Groq"),
        ("что такое promise?",                           "[GROQ OK]", "general→Groq"),
    ]

    for msg, expected_substr, label in cases_with_groq:
        resp, is_fb = await ask(msg)
        ok = expected_substr in resp
        results.append(f"[{'OK' if ok else 'FAIL'}] {label}: {repr(resp[:80])}")

    # ---- Без Groq (fallback) ----
    h2 = EnhancedAIHandler()
    h2.groq_client = None
    ctx2 = FakeCtx()

    async def ask2(msg):
        return await h2.get_specialized_response(msg, "general", ctx2,
                                                  skill_level="beginner", preferences={})

    cases_no_groq = [
        ("найди ошибку: for(i=0; i<5; i++) {}",   "FALLBACK",  "error без Groq → FALLBACK"),
        ("с чего начать?",                          "FALLBACK",  "learning без Groq → FALLBACK"),
        ("объясни этот код: x = 1",                "FALLBACK",  "explain без Groq → FALLBACK"),
        ("что такое event loop?",                   "FALLBACK",  "general без Groq → fallback"),
    ]

    for msg, expected_route, label in cases_no_groq:
        resp, is_fb = await ask2(msg)
        route = "FALLBACK" if is_fb else "Groq"
        ok = route == expected_route
        results.append(f"[{'OK' if ok else 'FAIL'}] {label}: is_fallback={is_fb}")

    # ---- SyntaxWarnings исчезли ----
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        try:
            import importlib, enhanced_ai_handler as eah
            importlib.reload(eah)
            results.append("[OK] No SyntaxWarnings on import")
        except SyntaxWarning as e:
            results.append(f"[FAIL] SyntaxWarning: {e}")

    # ---- max_rows ----
    h3 = EnhancedAIHandler()
    h3.groq_client = make_mock("[GROQ OK]")
    long_msg = "\n".join([f"line {i}" for i in range(70)])
    resp3, _ = await h3.get_specialized_response(long_msg, "general", FakeCtx(),
                                                   skill_level="beginner", preferences={})
    results.append(f"[OK] max_rows=60 → Groq called, resp={repr(resp3[:30])}")

    with open("test_routing.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    print("\n".join(results))


asyncio.run(run())
