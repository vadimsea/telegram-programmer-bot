# Симуляция реального пользователя в чате с ботом
import os, sys, asyncio
os.environ.setdefault('TELEGRAM_TOKEN', '0:x')
os.environ.setdefault('BOT_TOKEN', '0:x')
os.environ.setdefault('GROQ_API_KEY', os.environ.get('GROQ_API_KEY', ''))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from enhanced_ai_handler import EnhancedAIHandler

handler = EnhancedAIHandler()

class FakeContext:
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

async def chat(ctx, messages):
    results = []
    for msg in messages:
        resp, is_fallback = await handler.get_specialized_response(
            msg, "general", ctx,
            skill_level=ctx.skill_level,
            preferences=ctx.preferences
        )
        ctx.add_message("user", msg)
        ctx.add_message("assistant", resp)
        route = "SMALL_TALK/FALLBACK" if is_fallback else "GROQ"
        results.append({
            'input': msg,
            'route': route,
            'length': len(resp),
            'response_preview': resp[:200].replace('\n', ' '),
        })
    return results

async def main():
    out = []

    # === БЛОК 1: Small talk и приветствия ===
    out.append("=" * 60)
    out.append("БЛОК 1: Small talk")
    out.append("=" * 60)
    ctx = FakeContext()
    tests = [
        "привет",
        "как дела?",
        "ты кто?",
        "доброе утро",
        "спасибо за помощь",
        "помнишь меня?",
    ]
    for r in await chat(ctx, tests):
        out.append(f"\n[USER] {r['input']}")
        out.append(f"[BOT/{r['route']}] ({r['length']} chars)")
        out.append(f"  {r['response_preview']}")

    # === БЛОК 2: Технические вопросы (должны идти в Groq) ===
    out.append("\n" + "=" * 60)
    out.append("БЛОК 2: Технические вопросы")
    out.append("=" * 60)
    ctx2 = FakeContext()
    tests2 = [
        "что такое promise в javascript?",
        "не работает fetch, выдаёт CORS ошибку",
        "как сделать flexbox по центру?",
        "объясни что такое замыкание",
        "у меня баг в цикле for",
        "как работает async await?",
    ]
    for r in await chat(ctx2, tests2):
        out.append(f"\n[USER] {r['input']}")
        out.append(f"[BOT/{r['route']}] ({r['length']} chars)")
        out.append(f"  {r['response_preview']}")

    # === БЛОК 3: Граничные случаи ===
    out.append("\n" + "=" * 60)
    out.append("БЛОК 3: Граничные / странные вводы")
    out.append("=" * 60)
    ctx3 = FakeContext()
    tests3 = [
        "",                                # пустая строка
        "   ",                             # пробелы
        "?",                               # только знак вопроса
        "111",                             # только цифры
        "а",                               # одна буква
        "блять не работает ничего блин",   # фрустрация без кода
        "хочу стать программистом",         # общий запрос
    ]
    for r in await chat(ctx3, tests3):
        out.append(f"\n[USER] {repr(r['input'])}")
        out.append(f"[BOT/{r['route']}] ({r['length']} chars)")
        out.append(f"  {r['response_preview']}")

    # === БЛОК 4: Не-IT темы ===
    out.append("\n" + "=" * 60)
    out.append("БЛОК 4: Темы вне IT")
    out.append("=" * 60)
    ctx4 = FakeContext()
    tests4 = [
        "как приготовить борщ?",
        "что думаешь о политике?",
        "посоветуй фильм",
        "я хочу похудеть",
        "расскажи анекдот",
    ]
    for r in await chat(ctx4, tests4):
        out.append(f"\n[USER] {r['input']}")
        out.append(f"[BOT/{r['route']}] ({r['length']} chars)")
        out.append(f"  {r['response_preview']}")

    # === БЛОК 5: Длинное сообщение (> 10 строк - срабатывает truncation) ===
    out.append("\n" + "=" * 60)
    out.append("БЛОК 5: Длинный код (truncation тест)")
    out.append("=" * 60)
    ctx5 = FakeContext()
    long_code = "найди ошибку в коде:\n" + "\n".join([
        "function fetchUsers() {",
        "  const url = 'https://api.example.com/users';",
        "  fetch(url)",
        "    .then(res => res.json())",
        "    .then(data => {",
        "      data.forEach(user => {",
        "        console.log(user.name)",
        "      })",
        "    })",
        "    .catch(err => console.error(err))",
        "}",
        "fetchUsers()",
        "// вот тут что-то идёт не так",
    ])
    r = (await chat(ctx5, [long_code]))[0]
    total_lines = long_code.count('\n') + 1
    out.append(f"\n[USER] (код {total_lines} строк, {len(long_code)} символов)")
    out.append(f"[BOT/{r['route']}] ({r['length']} chars)")
    out.append(f"  {r['response_preview']}")

    with open('simulate_result.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print("Done. See simulate_result.txt")

asyncio.run(main())
