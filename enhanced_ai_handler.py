"""
Enhanced AI Handler - с правильным форматированием кода для Telegram (исправленный)
"""

import asyncio
import logging
import random
import re
from typing import List, Literal, Optional, Set, Tuple, TypedDict
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL, SYSTEM_PROMPT

try:
    from smart_features import smart_features  # ✅ Подключаем умные функции
    from database import user_db  # ✅ Подключаем базу данных
except ImportError:
    smart_features = None
    user_db = None

logger = logging.getLogger(__name__)


class SubmissionReview(TypedDict):
    """Ответ проверки кода урока: статус для логики + текст пользователю."""

    status: Literal["OK", "ERROR"]
    feedback: str


CODE_REVIEW_SYSTEM_PROMPT = (
    "Ты ментор по фронтенду (HTML/CSS/JS). Проверяешь работу новичка.\n"
    "Смотри ТОЛЬКО на пункты переданного чеклиста — не добавляй своих критериев и не требуй идеала.\n"
    "Тон: тёплый, по делу, без академизма и без длинных лекций. Не обесценивай человека.\n"
    "Найди максимум 1–2 замечания по чеклисту. Если пункты по смыслу выполнены — похвали конкретно (за что именно).\n"
    "Не выдавай готовое решение целиком и не разбирай то, чего нет в чеклисте.\n\n"
    "Формат ответа (строго):\n"
    "Строка 1 — ровно OK или ERROR (латиница, заглавные).\n"
    "Со строки 2 — короткий текст для ученика (не больше ~350 символов после строки 1):\n"
    "- при OK: одна строка похвалы; при желании вторая — одно лёгкое улучшение строго по чеклисту, если оно уместно;\n"
    "- при ERROR: что не так относительно чеклиста и одна конкретная подсказка, что сделать (без простыни).\n"
    "Без markdown-заголовков (#), без теории «как устроен браузер»."
)


def _parse_submission_review(raw: str) -> Tuple[str, str]:
    """Первая строка — OK|ERROR, остальное — feedback для пользователя."""
    text = (raw or "").strip()
    if not text:
        return "ERROR", "Пустой ответ проверки. Попробуй ещё раз или нажми «✅ Я сделал»."
    if "\n" in text:
        first, rest = text.split("\n", 1)
    else:
        first, rest = text, ""
    first_u = first.strip().upper()
    rest = rest.strip()
    if first_u == "OK" or first_u.startswith("OK ") or first_u.startswith("OK."):
        return "OK", rest or "По чеклисту всё сходится — красавчик, идём дальше."
    if first_u == "ERROR" or first_u.startswith("ERROR ") or first_u.startswith("ERROR."):
        return "ERROR", rest or "Глянь чеклист под заданием и поправь один момент — потом снова кинь код."
    # Модель забыла формат — не гадаем жёстко про зачёт
    if "ERROR" in first_u[:12]:
        return "ERROR", text
    token0 = first_u.split()[0] if first_u.split() else ""
    if token0 == "OK":
        return "OK", rest or text
    return "ERROR", text


class EnhancedAIHandler:
    SMALL_TALK_PRESETS = [
        {
            "triggers": ("не работает", "сломалось", "не запускается", "ошибка", "баг", "падает", "у меня баг"),
            "responses": [
                "🛠 Понимаю, как неприятно, когда что-то ломается. Давай посмотрим на детали и разнесём этот баг вместе.",
                "🧯 Ох, похоже система просит внимания. Расскажи, какие ошибки видишь — попробуем разрулить.",
                "🤖 Техдолг настиг! Кинь информацию об ошибке, и мы шаг за шагом найдём решение.",
            ],
        },
        {
            "triggers": ("получилось", "готово", "сделал", "успех", "заработало", "завелось"),
            "responses": [
                "🔥 Красота! Люблю такие апдейты. Если хочешь закрепить результат, могу подсказать, что ещё проверить.",
                "🎉 Отличная работа! Можем сразу подумать, как автоматизировать следующий шаг.",
                "🙌 Вот это скорость! Если хочешь, помогу задокументировать успех, чтобы повторить в следующий раз.",
            ],
        },
        {
            "triggers": ("как дела", "как жизнь", "как ты", "как настроение"),
            "responses": [
                "😊 Всё отлично! С утра разруливал пару бойлерплейтов, а сейчас могу подсказать тебе. Что сегодня в планах?",
                "💪 Держусь бодро: ревьюлю код, подпиливаю бота и слежу, чтобы деплой на Render не заснул. Как у тебя прогресс?",
                "☕ Пью виртуальный кофе и мониторю логи, чтобы всё работало 24/7. Что новенького у тебя?",
            ],
        },
        {
            "triggers": ("что делаешь", "чем занимаешься", "чем занят"),
            "responses": [
                "🧰 Сейчас перебираю логи и допиливаю ответы, чтобы они звучали живее. Хочешь — подключу мозговой штурм к твоему вопросу.",
                "🔍 Чищу техдолг, чтобы бот не повторялся и быстрее находил решения. Расскажи, что у тебя наболело?",
                "🛠 Кручусь между задачами: тестирую идеи, пишу сниппеты, помогаю пользователям. Давай разберёмся и с твоей задачей!",
            ],
        },
        {
            "triggers": ("что нового", "какие новости"),
            "responses": [
                "📰 Читаю свежие апдейты по FastAPI и Groq — любопытно, что они придумали. А у тебя какие новости?",
                "📬 Разбираю фидбек от пользователей и думаю, как прокачать ответы. Делись, что у тебя интересного.",
                "🧭 Пробую новые трюки в промптинге, чтобы бот отвечал точнее. Если есть идеи — обсудим!",
            ],
        },
        {
            "triggers": ("доброе утро",),
            "responses": [
                "🌅 Доброе утро! Отличное время добить злосчастный баг до того, как проснётся вся команда.",
                "☀️ Привет! Предлагаю начать день с небольшой победы — с чего начнём?",
                "🧠 Утренний мозг заряжен. Готов помочь тебе разгрести любую задачу.",
            ],
        },
        {
            "triggers": ("добрый день",),
            "responses": [
                "🌞 Добрый день! Если нужно ускорить фичу или починить тесты — я рядом.",
                "🥪 Как проходит день? Если зависаешь на задаче, давай разберём её вместе.",
                "🧭 Полдень — время навести порядок в коде. С чего начнём?",
            ],
        },
        {
            "triggers": ("добрый вечер",),
            "responses": [
                "🌇 Добрый вечер! Отличный момент подвести итоги и запланировать, что закрыть завтра.",
                "🎧 Я тут, если хочешь быстро пройтись по задачам перед оффлайном.",
                "🛋 Вечер — отличное время обсудить архитектуру или набросать идеи для рефакторинга.",
            ],
        },
        {
            "triggers": ("доброй ночи", "спокойной ночи"),
            "responses": [
                "🌙 Доброй ночи! Если хочешь, могу оставить для тебя чек-лист на утро.",
                "🛌 Отдыхай! Утром продолжим штурмовать код — идеи уже подкипают.",
                "😴 Понимаю, смена была жаркая. Я побуду на страже, когда вернёшься.",
            ],
        },
        {
            "triggers": ("привет", "приветик", "здорово", "здравствуйте", "hello", "hi", "hey"),
            "responses": [
                "👋 Привет! Всегда рад поговорить о коде и проектах. Что сейчас в работе?",
                "🤖 Привет! Я уже разогрел модель — давай к делу?",
                "🙌 Привет! Слушаю внимательно. Расскажи, с чем помочь.",
            ],
        },
        {
            "triggers": ("спасибо", "благодарю"),
            "responses": [
                "✨ Всегда пожалуйста! Если появятся новые вопросы — не стесняйся, помогу.",
                "😊 Рад, что пригодилось. Готов обсудить следующий шаг, когда будешь готов.",
                "🤗 Обращайся в любое время! Люблю видеть прогресс проектов.",
            ],
        },
        {
            "triggers": ("расскажи о себе", "ты кто"),
            "responses": [
                "Я Помощник Программиста — меня создал Вадим (vadzim.by). Люблю Python, автотесты и дружелюбный онбординг в IT.",
                "Меня зовут Помощник Программиста. Я — проект Вадима (vadzim.by) и обожаю помогать с кодом.",
                "Я цифровой напарник Вадима (vadzim.by). Подсказки, ревью, идеи — это ко мне.",
            ],
        },
        {
            "triggers": ("ты тут", "ты здесь", "на связи", "ты онлайн"),
            "responses": [
                "Всегда здесь! Давай посмотрим, что можно улучшить прямо сейчас.",
                "На связи! Подкидывай код или вопрос — вместе решим.",
                "Да, я рядом. Рассказывай, что происходит.",
            ],
        },
        {
            "triggers": ("помнишь меня",),
            "responses": [
                "Конечно! Я веду историю диалога — расскажи, на чём остановились.",
                "Помню! Готов продолжить с того места, где мы заканчивали.",
                "Да, держу контекст. Что обновилось с тех пор?",
            ],
        },
        {
            "triggers": ("что посоветуешь", "какой совет"),
            "responses": [
                "Могу подсказать подход, ресурс или инструмент. Уточни тему — и я подберу что-то дельное.",
                "Давай сузим запрос: какую область хочешь подтянуть? Я подскажу, с чего начать.",
                "Люблю делиться находками! Направь, что хочется улучшить, и подберу чек-лист.",
            ],
        },
        {
            "triggers": ("скучаешь",),
            "responses": [
                "😄 Тут не до скуки: всегда есть чей-то pet-проект, который ждёт подсказки. Как твои дела?",
                "😂 Я занят тем, что читаю логи и придумываю новые фичи. Лучше расскажи, что интересного у тебя!",
                "🤓 Скучать не приходится — проекты кипят. Так что залетай со своими задачами.",
            ],
        },
    ]

    POSITIVE_KEYWORDS = (
        "ура",
        "получилось",
        "готово",
        "сделал",
        "сделала",
        "заработало",
        "заработал",
        "успех",
        "сработало",
        "вышло",
        "fixed",
        "done",
        "solved",
        "ready",
        "закоммитил",
        "задеплоил",
    )

    NEGATIVE_KEYWORDS = (
        "не работает",
        "сломалось",
        "не выходит",
        "ошибка",
        "ошибку",
        "баг",
        "не запускается",
        "упало",
        "упал",
        "падает",
        "не собирается",
        "fail",
        "problem",
        "issue",
        "traceback",
        "stack trace",
        "вылетает",
        "не проходит тест",
        "не компилируется",
    )

    SUPPORTIVE_REACTIONS = {
        "positive": [
            "🎉 Рад слышать, что всё получилось! Можно вычеркнуть одну задачу из списка.",
            "🚀 Отличная новость! Давай подумаем, чем закрепить успех — тестами или рефакторингом?",
            "🙌 Супер! Если хочешь, помогу задокументировать решение, чтобы повторить без боли.",
        ],
        "negative": [
            "🤝 Держись, такое ловят даже сеньоры. Опиши, что видишь в логах — разберёмся.",
            "🧘 Понимаю боль. Скинь стек или фрагмент кода, и вместе найдём слабое место.",
            "🛟 Расскажи подробности: язык, фреймворк, что в ошибке. Помогу навести порядок.",
        ],
        "frustrated": [
            "😤 Понимаю, как это бесит. Давай по шагам разберём проблему — вместе точно решим.",
            "💪 Знаю, что это утомительно. Но мы справимся! Опиши, что именно не работает.",
            "🤗 Бывает. Не переживай — такие баги встречаются у всех. Давай найдём причину.",
        ],
        "excited": [
            "🔥 Отлично! Вижу, что ты вдохновлён. Давай сделаем это ещё лучше!",
            "⚡ Здорово, что ты так заинтересован! Готов помочь углубиться в тему.",
            "🎯 Круто! Давай разберём это детально и сделаем что-то действительно стоящее.",
        ],
        "confused": [
            "🤔 Ничего страшного, все когда-то начинали. Давай разберём по шагам.",
            "💡 Понимаю, что может быть непонятно. Объясню простыми словами с примерами.",
            "📚 Это нормально задавать вопросы! Давай разберём вместе, что именно непонятно.",
        ],
    }

    PERSONAL_TIPS = {
        "python": [
            "Запусти проект через `ruff` или `flake8` — мелкие стилистические огрехи проявятся сразу.",
            "Если много I/O, посмотри на `asyncio.to_thread` или `anyio`, чтобы не блокировать цикл.",
            "Типизация через `typing` + `pydantic` помогает ловить баги ещё до запуска.",
        ],
        "javascript": [
            "Настрой `eslint` + `prettier` в pre-commit — команда будет писать код в одном стиле.",
            "Если проект растёт, подумай о TypeScript или хотя бы JSDoc для ключевых модулей.",
            "Используй `console.group` и `console.table` — так логирование становится информативнее.",
        ],
        "debugging": [
            "Собери минимальный пример, где воспроизводится проблема — половина пути.",
            "Включи подробные логи (уровень DEBUG) вокруг подозрительных участков — часто этого хватает.",
            "Не забывай про `git bisect`: быстро найдёт коммит, который внёс баг.",
        ],
        "learning": [
            "Веди короткие заметки после каждой практики: что пробовал, что сработало, что нет.",
            "Параллельно веди pet-проект — лучше всего учиться на том, что интересно.",
            "Ставь измеримые цели на неделю и отмечай прогресс — мотивация растёт.",
        ],
        "fastapi": [
            "Используй `Depends` и `BackgroundTasks` — так код чище и тестировать проще.",
            "Документируй публичные эндпоинты через описание в FastAPI, чтобы OpenAPI был понятнее.",
            "Валидация через `pydantic`-модели спасает от кривых запросов ещё до бизнес-логики.",
        ],
        "telegram": [
            "Вынеси бизнес-логику из хендлеров — становится проще писать тесты и расширять бота.",
            "Если нагрузки растут, подумай о вебхуках + очереди сообщений (Redis, RabbitMQ).",
            "Не забывай хранить состояние пользователей — это база для сценариев и персонализации.",
        ],
    }

    TOPIC_LABELS = {
        "python": "Python",
        "javascript": "JavaScript",
        "debugging": "отладке",
        "learning": "обучению",
        "fastapi": "FastAPI",
        "telegram": "Telegram-ботам",
    }

    def __init__(self):
        self.groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        logger.info("🤖 EnhancedAIHandler инициализирован")
    # Триггеры, которые совпадают только с коротким сообщением (≤ слов в триггере + 1).
    # Если пользователь написал "не работает fetch" — это техвопрос, а не small-talk.
    _PROBLEM_TRIGGERS = frozenset({
        "не работает", "сломалось", "не запускается", "ошибка", "баг", "падает",
        "у меня баг", "вылетает",
    })

    # Технические слова, означающие что сообщение — реальный вопрос, а не small talk.
    _TECH_WORDS = frozenset({
        "fetch", "promise", "async", "await", "css", "html", "js", "javascript",
        "python", "react", "node", "api", "dom", "flex", "grid", "function",
        "class", "import", "export", "const", "let", "var", "def", "return",
        "console", "error", "typeerror", "syntaxerror", "uncaught", "undefined",
        "null", "nan", "http", "cors", "json", "git", "npm", "webpack", "vite",
        "django", "flask", "fastapi", "sql", "database", "sql", "docker",
        "render", "deploy", "heroku", "vercel", "lambda", "event", "callback",
        "selector", "property", "attribute", "margin", "padding", "display",
        "overflow", "position", "z-index", "border", "animation", "transition",
    })

    def _match_small_talk(self, message_lower: str) -> Optional[str]:
        trimmed = message_lower.strip()
        if not trimmed:
            return None

        trimmed_for_check = trimmed.rstrip('?.,!')
        words = trimmed_for_check.split()

        # Если сообщение содержит явные технические слова — сразу в Groq.
        if any(w in self._TECH_WORDS for w in words):
            return None

        # Технические intent-фразы — сразу в Groq (проверяем ДО пресетов).
        intent_keywords = (
            "что такое", "кто такой", "как создать", "как сделать",
            "как написать", "как использовать", "зачем нужен", "почему не работает",
            "передай", "расскажи про", "скажи про", "подскажи как",
            "напиши код", "сделай программу", "создай", "объясни код",
            "о программировании", "про python", "про javascript",
        )
        if any(kw in trimmed_for_check for kw in intent_keywords):
            return None

        for preset in self.SMALL_TALK_PRESETS:
            for trigger in preset["triggers"]:
                is_exact = trigger == trimmed_for_check
                is_substr = trigger in trimmed_for_check

                if not is_exact and not is_substr:
                    continue

                # Для «проблемных» триггеров ("не работает", "ошибка" и т.п.)
                # применяем только точное совпадение или совпадение с коротким
                # сообщением (не длиннее trigger + 1 слово).
                if trigger in self._PROBLEM_TRIGGERS and not is_exact:
                    trigger_len = len(trigger.split())
                    if len(words) > trigger_len + 1:
                        continue

                return random.choice(preset["responses"])

        # Простые вопросы со знаком "?" — проверяем отдельно.
        if "?" in trimmed:
            simple_questions = (
                "как дела", "как жизнь", "как ты", "как настроение",
                "что делаешь", "чем занимаешься", "что нового", "какие новости",
            )
            trimmed_no_punct = trimmed_for_check.strip()
            for q in simple_questions:
                if q in trimmed_no_punct or trimmed_no_punct == q:
                    for preset in self.SMALL_TALK_PRESETS:
                        for trigger in preset["triggers"]:
                            if q in trigger or trigger in q:
                                return random.choice(preset["responses"])
                    return "Всё отлично! 😊 Готов помочь с программированием. Что у тебя на уме?"

        return None

    def _detect_message_tone(self, message_lower: str) -> Optional[str]:
        """Определяет эмоциональный тон сообщения"""
        if any(keyword in message_lower for keyword in self.NEGATIVE_KEYWORDS):
            return "negative"
        if any(keyword in message_lower for keyword in self.POSITIVE_KEYWORDS):
            return "positive"
        
        # Дополнительные признаки эмоций
        frustration_words = ["блять", "черт", "долбаный", "ненавижу", "бесит", "устал", "надоело"]
        if any(word in message_lower for word in frustration_words):
            return "frustrated"
        
        excited_words = ["вау", "круто", "супер", "отлично", "класс", "здорово", "ура"]
        if any(word in message_lower for word in excited_words):
            return "excited"
        
        confused_words = ["не понимаю", "не понял", "запутался", "не знаю", "как это", "что это"]
        if any(phrase in message_lower for phrase in confused_words):
            return "confused"
        
        return None

    def _augment_with_tone(self, response: str, tone: str) -> str:
        reactions = self.SUPPORTIVE_REACTIONS.get(tone)
        if not reactions:
            return response
        addition = random.choice(reactions)
        if addition in response:
            return response
        return f"{response}\n\n{addition}"

    def _maybe_add_personal_tip(
        self,
        response: str,
        preferences: dict,
        user_context=None,
        message_lower: str = "",
    ) -> str:
        topics: List[str] = []

        if preferences:
            for value in preferences.get('favorite_languages', []):
                topic_key = self._map_topic_to_tip_key(value)
                if topic_key:
                    topics.append(topic_key)
            for value in preferences.get('learning_goals', []):
                topic_key = self._map_topic_to_tip_key(value)
                if topic_key:
                    topics.append(topic_key)

        message_lower = (message_lower or "").lower()
        if 'fastapi' in message_lower:
            topics.append('fastapi')
        if 'telegram' in message_lower or 'бот' in message_lower:
            topics.append('telegram')

        if user_context and hasattr(user_context, 'user_id') and getattr(user_context, 'user_id', None) and user_db:
            try:
                user_data = user_db.get_user(user_context.user_id)
            except Exception:
                user_data = None
            if user_data:
                for value in user_data.get('favorite_topics', []):
                    topic_key = self._map_topic_to_tip_key(value)
                    if topic_key:
                        topics.append(topic_key)

        ordered_topics: List[str] = []
        seen: Set[str] = set()
        for topic in topics:
            if not topic or topic not in self.PERSONAL_TIPS:
                continue
            if topic not in seen:
                seen.add(topic)
                ordered_topics.append(topic)

        if not ordered_topics:
            return response

        last_tip = getattr(user_context, 'last_tip_text', None) if user_context else None
        for topic in ordered_topics:
            tips = self.PERSONAL_TIPS.get(topic)
            if not tips:
                continue
            tip_choice = random.choice(tips)
            if last_tip and tip_choice == last_tip and len(tips) > 1:
                alternatives = [tip for tip in tips if tip != last_tip]
                if alternatives:
                    tip_choice = random.choice(alternatives)
            addition = f"💡 Персональный совет по {self._tip_topic_label(topic)}:\n{tip_choice}"
            if addition in response:
                continue
            if user_context:
                setattr(user_context, 'last_tip_topic', topic)
                setattr(user_context, 'last_tip_text', tip_choice)
            return f"{response}\n\n{addition}"
        return response

    def _map_topic_to_tip_key(self, topic: str) -> Optional[str]:
        if not topic:
            return None
        normalized = topic.lower()
        mapping = {
            'python': 'python',
            'py': 'python',
            'javascript': 'javascript',
            'js': 'javascript',
            'ts': 'javascript',
            'typescript': 'javascript',
            'debugging': 'debugging',
            'debug': 'debugging',
            'ошибка': 'debugging',
            'learning': 'learning',
            'learning_basics': 'learning',
            'учить': 'learning',
            'fastapi': 'fastapi',
            'telegram': 'telegram',
            'бот': 'telegram',
            'tg': 'telegram',
        }
        for key, value in mapping.items():
            if key in normalized:
                return value
        return None

    def _tip_topic_label(self, topic_key: str) -> str:
        return self.TOPIC_LABELS.get(topic_key, topic_key)



    async def get_specialized_response(
        self,
        message: str,
        mode: str = "general",
        user_context=None,
        skill_level: str = "beginner",
        preferences: dict = None,
    ) -> Tuple[str, bool]:
        """Generate a reply for Telegram and flag whether it is a fallback."""
        follow_up = False
        try:
            if preferences is None:
                preferences = {}

            if user_context and hasattr(user_context, 'user_id'):
                    logger.info(f"🔄 Обработка запроса от пользователя {user_context.user_id} (уровень: {skill_level})")

            message_lower = message.lower().strip()
            
            # Early truncation to keep answers compact
            max_rows = 10
            lines = message.splitlines()
            if len(lines) > max_rows:
                message = "\n".join(lines[:max_rows]) + "\n…"
                message_lower = message.lower().strip()

            small_talk_reply = self._match_small_talk(message_lower)
            if small_talk_reply:
                tone = self._detect_message_tone(message_lower)
                if tone:
                    small_talk_reply = self._augment_with_tone(small_talk_reply, tone)
                # is_fallback=True: small-talk не кешируется (ответы случайны, у каждого свой)
                return small_talk_reply, True

            quick_responses = self._get_personalized_quick_responses(skill_level, preferences)
            follow_up_keywords = ("подробнее", "детальнее", "поподробнее", "ещё", "еще", "расскажи больше", "расскажи подробнее", "больше информации", "tell me more", "more detail")
            if any(keyword in message_lower for keyword in follow_up_keywords):
                follow_up = True
            elif user_context and hasattr(user_context, 'history') and user_context.history:
                recent_user_messages = [entry['content'].lower().strip() for entry in reversed(user_context.history) if entry.get('role') == 'user']
                if recent_user_messages:
                    last_question = recent_user_messages[0]
                    if last_question == message_lower or (len(message_lower) > 12 and message_lower in last_question):
                        follow_up = True

            if follow_up and skill_level != 'advanced':
                skill_level = 'intermediate' if skill_level == 'beginner' else 'advanced'

            base_question = None
            previous_answer = None
            if user_context and hasattr(user_context, 'history') and user_context.history:
                for entry in reversed(user_context.history):
                    if entry.get('role') == 'assistant':
                        previous_answer = entry.get('content', '')
                        if previous_answer:
                            previous_answer = previous_answer.strip()
                        break
                for entry in reversed(user_context.history):
                    if entry.get('role') != 'user':
                        continue
                    prior_text = entry.get('content', '')
                    if not prior_text:
                        continue
                    normalized = prior_text.lower().strip()
                    if normalized == message_lower:
                        continue
                    if any(keyword in normalized for keyword in follow_up_keywords):
                        continue
                    if len(normalized.split()) <= 3:
                        continue
                    base_question = prior_text.strip()
                    break

            if message_lower in quick_responses and len(message_lower.split()) <= 3:
                response = quick_responses[message_lower]
                tone = self._detect_message_tone(message_lower)
                if tone:
                    response = self._augment_with_tone(response, tone)
                return response, False

            if ("html" in message_lower and "css" in message_lower and
                    any(word in message_lower for word in ["нач", "start", "уч", "изуч", "learn"])):
                roadmap = (
                    "<b>Как начать с HTML и CSS</b>\n"
                    "• <b>1. Базовая разметка</b> — изучи теги <code>&lt;html&gt;</code>, <code>&lt;head&gt;</code>, "
                    "<code>&lt;body&gt;</code>, заголовки, параграфы, списки. Закрепи, сверстав «визитку».\n"
                    "• <b>2. Семантика</b> — используй <code>&lt;header&gt;</code>, <code>&lt;nav&gt;</code>, "
                    "<code>&lt;main&gt;</code>, <code>&lt;section&gt;</code>, <code>&lt;footer&gt;</code> вместо "
                    "абстрактных <code>&lt;div&gt;</code>.\n"
                    "• <b>3. Основы CSS</b> — селекторы, каскад, наследование, единицы измерения, переменные. "
                    "Попрактикуйся со шрифтами, цветами и отступами.\n"
                    "• <b>4. Макеты</b> — Flexbox для горизонтальных блоков, CSS Grid для сложных сеток. "
                    "Создай адаптивный лейаут, используй <code>minmax</code> и <code>auto-fit</code>.\n"
                    "• <b>5. Практика и ресурсы</b>\n"
                    "  — freeCodeCamp Responsive Web Design\n"
                    "  — HTML Academy интерактивные курсы\n"
                    "  — Книги: «HTML и CSS. Разработка и дизайн веб‑сайтов» Даккетта\n"
                    "• <b>6. Следующий шаг</b> — проект «одностраничник»: шапка, блок преимуществ, портфолио, форма контактов. "
                    "Разбей стили на логические модули (base, layout, components).\n"
                    "Практикуйся ежедневно, сохраняй примеры в репозитории и постепенно добавляй новые приёмы."
                )
                return roadmap, False

            if "калькулятор" in message_lower or "calculator" in message_lower:
                if "javascript" in message_lower or "js" in message_lower:
                    calc_example = ("Вот простой HTML + JavaScript интерактивный калькулятор:\n\n"
                                    "```html\n"
                                    "<div class=\"calc\">\n"
                                    "  <input id=\"a\" type=\"number\" placeholder=\"Первое число\">\n"
                                    "  <select id=\"op\">\n"
                                    "    <option value=\"+\">+</option>\n"
                                    "    <option value=\"-\">-</option>\n"
                                    "    <option value=\"*\">*</option>\n"
                                    "    <option value=\"/\">/</option>\n"
                                    "  </select>\n"
                                    "  <input id=\"b\" type=\"number\" placeholder=\"Второе число\">\n"
                                    "  <button id=\"calc\">Вычислить</button>\n"
                                    "  <p id=\"result\"></p>\n"
                                    "</div>\n"
                                    "<script>\n"
                                    "  const calcBtn = document.getElementById('calc');\n"
                                    "  const resultEl = document.getElementById('result');\n"
                                    "  calcBtn.addEventListener('click', () => {\n"
                                    "    const a = Number(document.getElementById('a').value);\n"
                                    "    const b = Number(document.getElementById('b').value);\n"
                                    "    const op = document.getElementById('op').value;\n"
                                    "    let result;\n"
                                    "    switch (op) {\n"
                                    "      case '+': result = a + b; break;\n"
                                    "      case '-': result = a - b; break;\n"
                                    "      case '*': result = a * b; break;\n"
                                    "      case '/':\n"
                                    "        result = b !== 0 ? a / b : 'Ошибка: деление на ноль';\n"
                                    "        break;\n"
                                    "      default:\n"
                                    "        result = 'Неизвестная операция';\n"
                                    "    }\n"
                                    "    resultEl.textContent = `Результат: ${result}`;\n"
                                    "  });\n"
                                    "</script>\n"
                                    "```\n\n"
                                    "Можете улучшить калькулятор добавив стили, валидацию или TS или GUI — дерзайте.")
                else:
                    calc_example = ("Вот простой консольный калькулятор на Python:\n\n"
                                    "```python\n"
                                    "def calculator():\n"
                                    "    operations = {\n"
                                    "        '+': lambda a, b: a + b,\n"
                                    "        '-': lambda a, b: a - b,\n"
                                    "        '*': lambda a, b: a * b,\n"
                                    "        '/': lambda a, b: a / b if b != 0 else 'Ошибка: деление на ноль'\n"
                                    "    }\n\n"
                                    "    op = input('Операция (+, -, *, /): ').strip()\n"
                                    "    a = float(input('Первое число: '))\n"
                                    "    b = float(input('Второе число: '))\n\n"
                                    "    if op not in operations:\n"
                                    "        return 'Неизвестная операция'\n\n"
                                    "    result = operations[op](a, b)\n"
                                    "    return f'Результат: {result}'\n\n"
                                    "if __name__ == '__main__':\n"
                                    "    print(calculator())\n"
                                    "```\n\n"
                                    "Можете улучшить калькулятор добавив GUI или веб-интерфейс, дерзайте.")
                return calc_example, False

            if "найди ошибку" in message_lower or "find error" in message_lower:
                analysis = await self._analyze_code_for_errors(message)
                return analysis, False

            if any(phrase in message_lower for phrase in
                   ["с чего начать", "как начать", "начать учить", "начать изучать"]):
                advice = await self._get_learning_advice(message)
                return advice, False

            if "оптимизируй" in message_lower or "optimize" in message_lower:
                mode = "optimize_code"
            elif "объясни" in message_lower or "explain" in message_lower:
                mode = "explain_concept"
            elif "ошибка" in message_lower or "debug" in message_lower:
                mode = "debug_code"
            elif "архитектур" in message_lower or "architecture" in message_lower:
                mode = "architecture_advice"
            elif "анализируй" in message_lower or "проанализируй" in message_lower or "analyze" in message_lower:
                mode = "analyze_code"
            else:
                mode = "general"

            if "объясни этот код" in message_lower or "что делает этот код" in message_lower:
                explanation = await self.explain_code(message)
                return explanation, False

            if "проанализируй этот код" in message_lower or "analyze this code" in message_lower:
                explanation = await self.explain_code(message)
                return explanation, False

            # === Обращение к Groq API ===
            if not self.groq_client:
                logger.warning("Groq клиент не инициализирован")
                return self._get_fallback_response(message, mode), True
            
            # Определяем эмоциональный тон сообщения
            user_tone = self._detect_message_tone(message_lower)
            
            # Получаем имя пользователя из контекста, если доступно
            user_name = None
            if user_context and hasattr(user_context, 'user_id') and user_db:
                try:
                    user_data = user_db.get_user(user_context.user_id)
                    user_name = user_data.get('first_name') or user_data.get('username')
                except Exception:
                    pass
                
            try:
                prompt = self._build_personalized_prompt(
                    message,
                    mode,
                    skill_level,
                    preferences,
                    follow_up=follow_up,
                    base_question=base_question,
                    previous_answer=previous_answer,
                    user_tone=user_tone,
                    user_name=user_name,
                )
                logger.info(f"🔄 Отправка запроса к Groq (mode={mode}, level={skill_level}): {message[:50]}...")

                messages = [{"role": "system", "content": SYSTEM_PROMPT}]

                # Add conversation history if available
                if user_context and hasattr(user_context, 'history') and user_context.history:
                    # Get last 6 messages (3 exchanges) for context
                    recent_history = user_context.get_recent_context(6)
                    for msg in recent_history:
                        if msg.get('role') == 'user':
                            messages.append({"role": "user", "content": msg.get('content', '')})
                        elif msg.get('role') == 'assistant':
                            messages.append({"role": "assistant", "content": msg.get('content', '')})

                # Add current message
                messages.append({"role": "user", "content": prompt})

                response = await self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    temperature=0.7,  # Увеличена температура для более естественных и вариативных ответов
                    max_tokens=1200,  # Увеличено для более полных ответов
                    timeout=20  # Увеличено время ожидания
                )

                if not response or not hasattr(response, "choices") or not response.choices:
                    logger.warning("⚠️ Пустой ответ от Groq. Используем fallback.")
                    return self._get_fallback_response(message, mode), True

                choice = response.choices[0]
                content = getattr(choice.message, "content", None) if hasattr(choice, "message") else None

                if not content:
                    logger.warning("⚠️ Пустое содержимое ответа. Используем fallback.")
                    return self._get_fallback_response(message, mode), True

                ai_response = content.strip()
                if not ai_response:
                    logger.warning("⚠️ Пустой ответ после обработки. Используем fallback.")
                    return self._get_fallback_response(message, mode), True
                    
                # Добавляем эмоциональную поддержку, если нужно
                if user_tone and user_tone in self.SUPPORTIVE_REACTIONS:
                    tone_reaction = random.choice(self.SUPPORTIVE_REACTIONS[user_tone])
                    # Добавляем реакцию только если её нет в ответе
                    if tone_reaction.lower() not in ai_response.lower():
                        ai_response = f"{tone_reaction}\n\n{ai_response}"
                    
                ai_response = self._maybe_add_personal_tip(ai_response, preferences, user_context, message_lower)
                logger.info("✅ Успешный ответ от Groq")
                formatted = self._format_for_telegram(ai_response)
                return formatted, False

            except asyncio.TimeoutError:
                logger.warning("⏰ Таймаут запроса к Groq")
                return "⏰ ИИ долго думает... Попробуйте задать вопрос короче.", True
            except Exception as e:
                logger.error(f"❌ Ошибка Groq: {e}", exc_info=True)
                return self._get_fallback_response(message, mode), True

        except Exception as e:
            logger.error(f"🔥 Критическая ошибка: {e}", exc_info=True)
            return self._get_fallback_response(message, mode), True

    async def _analyze_code_for_errors(self, message: str) -> str:
        """Анализ кода на ошибки"""
        code_match = re.search(r'\`\`\`[\w]*\n?(.*?)\n?\`\`\`', message, re.DOTALL)

        if code_match:
            code = code_match.group(1).strip()
        else:
            lowered = message.lower()
            if "проанализируй код" in lowered:
                code = message[lowered.index("проанализируй код") + len("проанализируй код"):].strip()
            elif "analyze code" in lowered:
                code = message[lowered.index("analyze code") + len("analyze code"):].strip()
            else:
                code = ""

        if not code:
            return "❌ Не могу найти код в сообщении. Пожалуйста, приложите код для анализа."

        # Определяем язык
        if any(keyword in code.lower() for keyword in ['let', 'const', 'var', 'console.log', 'for(']):
            return self._analyze_javascript_errors(code)
        elif any(keyword in code for keyword in ['def ', 'print(', 'import ', 'for ']):
            return self._analyze_python_errors(code)
        elif "<div" in code.lower() or "<html" in code.lower() or "<h1>" in code.lower():
            return f"🔍 **Анализ HTML кода:**\n\n\`\`\`html\n{code}\n\`\`\`\n\n⚠️ Ошибка: у `<div>` отсутствует закрывающий символ `>`.\n✅ Добавьте его: `<div class=\"container\">`"
        else:
            return f"🔍 **Анализ кода:**\n\n\`\`\`\n{code}\n\`\`\`\n\n❓ Не могу определить язык программирования. Укажите язык для более точного анализа."

    def _analyze_javascript_errors(self, code: str) -> str:
        errors = []
        suggestions = []
        if re.search(r'for\s*\(\s*i\s*=', code):
            errors.append("❌ Переменная `i` не объявлена (отсутствует `let`, `const` или `var`)")
            suggestions.append("✅ Используйте `let i = 0` вместо `i = 0`")
        if 'var ' in code:
            suggestions.append("💡 Рекомендуется использовать `let` или `const` вместо `var`")
        lines = code.split('\n')
        for line in lines:
            if line.strip() and not line.strip().endswith((';', '{', '}')):
                if any(keyword in line for keyword in ['console.log', 'let ', 'const ', 'var ']):
                    suggestions.append("💡 Добавьте точки с запятой в конце строк")
                    break
        response = "🔍 **Анализ JavaScript кода:**\n\n"
        response += f"\`\`\`javascript\n{code}\n\`\`\`\n\n"
        if errors:
            response += "🚨 **Найденные ошибки:**\n"
            for error in errors:
                response += f"{error}\n"
            response += "\n"
        if suggestions:
            response += "💡 **Рекомендации:**\n"
            for suggestion in suggestions:
                response += f"{suggestion}\n"
            response += "\n"
        fixed_code = code
        if re.search(r'for\s*\(\s*i\s*=', code):
            fixed_code = re.sub(r'for\s*\(\s*i\s*=', 'for(let i=', fixed_code)
        response += "✅ **Исправленный код:**\n"
        response += f"\`\`\`javascript\n{fixed_code}\n\`\`\`"
        return response

    def _analyze_python_errors(self, code: str) -> str:
        errors = []
        suggestions = []

        # Базовые проверки без запуска интерпретатора
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            # Функции/классы без двоеточия
            if re.match(r"^\s*(def |class )\w+.*[^:]$", stripped):
                errors.append(f"❌ Строка {i}: возможно пропущено `:` в конце def/class")
            # print без скобок (Python 2 стиль)
            if re.match(r"^\s*print\s+[^\(]", stripped):
                errors.append(f"❌ Строка {i}: `print` без скобок — это Python 2, используй `print(...)`")
            # = вместо == в условии
            if re.search(r"\bif\b.*[^=!<>]=[^=]", stripped) and "==" not in stripped:
                errors.append(f"⚠️ Строка {i}: возможно `=` вместо `==` в условии")

        if "except:" in code and "except Exception" not in code:
            suggestions.append("💡 Используй `except Exception as e:` вместо голого `except:` — так проще отлаживать")
        if "\t" in code and "    " in code:
            suggestions.append("💡 Смешаны табы и пробелы — выбери одно (PEP 8 рекомендует 4 пробела)")
        if re.search(r"l\s*=\s*\[\].*\nfor.*:\n.*l\.append", code, re.MULTILINE):
            suggestions.append("💡 Можно заменить цикл с append на list comprehension")

        response = "🔍 **Анализ Python кода:**\n\n"
        response += f"\`\`\`python\n{code}\n\`\`\`\n\n"
        if errors:
            response += "🚨 **Найденные проблемы:**\n" + "\n".join(errors) + "\n\n"
        if suggestions:
            response += "💡 **Рекомендации:**\n" + "\n".join(suggestions) + "\n\n"
        if not errors and not suggestions:
            response += "✅ Явных проблем не найдено. Для глубокого анализа отправь код через `объясни этот код`."
        return response

    async def _get_learning_advice(self, message: str) -> str:
        return """🚀 **С чего начать изучение программирования?**

📚 **Рекомендуемый путь для новичков:**

**1. Выберите первый язык:**
• **Python** - простой синтаксис, много материалов
• **JavaScript** - для веб-разработки
• **Java** - для серьезных приложений

**2. Основы программирования:**
• Переменные и типы данных
• Условия (if/else)
• Циклы (for/while)
• Функции
• Массивы/списки

**3. Практика:**
• Решайте задачи на Codewars, LeetCode
• Создавайте небольшие проекты
• Читайте чужой код

**4. Ресурсы для изучения:**
• **Бесплатно:** freeCodeCamp, Codecademy
• **Книги:** "Изучаем Python" Марка Лутца
• **YouTube:** каналы по программированию

**5. Следующие шаги:**
• Изучите Git и GitHub
• Освойте базы данных (SQL)
• Выберите специализацию (веб, мобильные приложения, ИИ)

💡 **Главный совет:** Программируйте каждый день, даже по 30 минут!

🤝 **Нужна помощь?** Обращайтесь к создателю: @vadzim_belarus"""

    async def explain_code(self, code: str) -> str:
        if not smart_features:
            return "⚠️ Анализ кода недоступен (smart_features не подключён)."
        language = self._guess_language(code)
        analysis = smart_features.analyze_code_quality(code, language)
        human_explanation = self._generate_human_explanation(code, language)
        response = f"📝 Объяснение кода\n\n"
        response += f"**Определённый язык:** {language}\n\n"
        response += f"📖 Смысл кода:\n{human_explanation}\n\n"
        response += f"📊 Метрики:\n"
        response += f"- Всего строк: {analysis['total_lines']}\n"
        response += f"- Кодовых строк: {analysis['code_lines']}\n"
        response += f"- Средняя длина строки: {analysis['avg_line_length']:.1f}\n"
        response += f"- Сложность: {analysis['complexity_score']}\n"
        response += f"- Читаемость: {analysis['readability_score']:.1f}/10\n\n"
        if analysis['issues']:
            response += "⚠️ Найденные проблемы:\n"
            for issue in analysis['issues']:
                response += f"- {issue['type']}: {issue['message']}\n"
            response += "\n"
        if analysis['suggestions']:
            response += "💡 Советы по улучшению:\n"
            for s in analysis['suggestions']:
                response += f"- {s}\n"
        return response.strip()

    def _generate_human_explanation(self, code: str, language: str) -> str:
        code_lower = code.lower()
        if language == "javascript":
            if "console.log" in code_lower:
                return "Этот код выводит сообщение или значение в консоль браузера."
        if language == "python":
            if "print(" in code_lower:
                return "Этот код печатает текст или значение в консоль."
            if "for " in code_lower and "range(" in code_lower:
                return "Этот цикл перебирает диапазон чисел и выполняет действие на каждой итерации."
        if language == "java":
            if "system.out.println" in code_lower:
                return "Этот код выводит текст в консоль в Java."
        if language == "html":
            if "<h1>" in code_lower:
                return "Этот HTML-код отображает заголовок на веб-странице."
        if language == "sql":
            if "select" in code_lower:
                return "Этот SQL-запрос выбирает данные из таблицы базы данных."
        return "Код выполняет заданные инструкции. Для точного объяснения нужен дополнительный контекст."

    def _guess_language(self, code: str) -> str:
        code_lower = code.lower()
        if "def " in code or "print(" in code or "import " in code:
            return "python"
        if "function " in code_lower or "console.log(" in code_lower or "let " in code_lower:
            return "javascript"
        if "public static void main" in code_lower or "class " in code:
            return "java"
        if "<html" in code_lower or "<div" in code_lower or "</body>" in code_lower:
            return "html"
        if "select " in code_lower or "insert into" in code_lower or "create table" in code_lower:
            return "sql"
        return smart_features.detect_language_by_code(code) if smart_features else "неизвестный"

    def _build_prompt(self, message: str, mode: str) -> str:
        mode_descriptions = {
            "analyze_code": "Проанализируй этот код. Весь код оформляй в ОДИН блок с \`\`\`язык",
            "debug_code": "Найди и исправь ошибки в коде. Весь код оформляй в ОДИН блок с \`\`\`язык",
            "explain_concept": "Объясни концепцию простыми словами с примерами кода. Код в \`\`\`язык",
            "optimize_code": "Оптимизируй код. Весь код оформляй в ОДИН блок с \`\`\`язык",
            "architecture_advice": "Дай советы по архитектуре с примерами. Код в \`\`\`язык",
            "general": "Ответь на вопрос по программированию. Код оформляй в \`\`\`язык"
        }
        task = mode_descriptions.get(mode, mode_descriptions["general"])
        return f"{task}:\n\n{message}"

    def _format_for_telegram(self, text: str) -> str:
        if not text:
            return text
        code_blocks = re.findall(r'\`\`\`(\w+)?\s*(.*?)\`\`\`', text, re.DOTALL)
        if not code_blocks:
            return text
        formatted_text = text
        for lang, code in code_blocks:
            escaped_code = code.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            if lang:
                telegram_code_block = f'\`\`\`{lang}\n{escaped_code}\n\`\`\`'
            else:
                telegram_code_block = f'\`\`\`\n{escaped_code}\n\`\`\`'
            original_block = f'\`\`\`{lang or ""}\n{code}\n\`\`\`'
            formatted_text = formatted_text.replace(original_block, telegram_code_block)
        return formatted_text

    def _get_fallback_response(self, message: str, mode: str) -> str:
        fallbacks = {
            "analyze_code": "Сейчас не могу быстро разобрать код. Отправь его ещё раз и уточни, что именно смущает — разберёмся вместе.",
            "debug_code": "Не получилось сразу найти проблему. Проверь, хватает ли контекста (ошибки, логи), и пришли пример повторно — посмотрю внимательнее.",
            "explain_concept": "Пока не удалось подобрать объяснение. Сформулируй вопрос иначе или добавь деталей — так будет проще помочь.",
            "optimize_code": "Сейчас не получилось предложить оптимизацию. Попробуй описать цель подробнее (производительность, читаемость, масштабируемость) и спроси ещё раз.",
            "architecture_advice": "Не успел сформировать архитектурный совет. Дай больше информации о проекте (размер, требования, стек) и спроси ещё раз — подумаю над решением.",
            "general": "Что-то пошло не так с ответом. Попробуй переформулировать вопрос или задать его по-другому — я готов помочь!"
        }
        return fallbacks.get(mode, fallbacks["general"])

    def _get_personalized_quick_responses(self, skill_level: str, preferences: dict) -> dict:
        """Персонализированные быстрые ответы на основе уровня навыков"""
        base_responses = {
            'привет': """👋 Привет! Я Помощник Программиста
🚀 Создан Вадимом (vadzim.by)

💻 Помогу с:
• Анализом и отладкой кода
• Объяснением концепций программирования
• Оптимизацией и архитектурой приложений
• Решением проблем и ошибок
• Персональным обучением программированию

🎯 Я адаптируюсь под ваш уровень и стиль обучения!
📊 Используйте кнопки для обратной связи - это помогает мне становиться лучше

📝 Просто напишите свой вопрос или код!

⚡ Быстрые команды:
/help - Получить справку
/settings - Настроить предпочтения
/about - О создателе

👇 Также можете воспользоваться кнопками ниже:""",
            'hello': "Hello! 👋 I'm Programming Assistant. Created by Vadim (vadzim.by)",
            'hi': "Hi there! 👋 Programming Assistant here!",
            'здравствуй': "Здравствуй! 👋 Помощник Программиста к вашим услугам!",
            'как дела': "Всё отлично! 😊 Готов помочь с программированием!",
            'how are you': "I'm great! 😊 Ready to help with programming!",
            'сайт': "👨‍💻 Создатель: Вадим\n🌐 Сайт: vadzim.by\n🚀 Специализация: разработка сайтов и Telegram ботов",
            'вадим': "👨‍💻 Создатель: Вадим\n🌐 Сайт: vadzim.by\n💻 Стек: Python, JavaScript, Django, React",
            'vadzim': "👨‍💻 Creator: Vadzim\n🌐 Website: vadzim.by\n💻 Tech stack: Python, JavaScript, Django, React",
            'кто тебя создал': "Меня создал Вадим (vadzim.by) - full-stack разработчик из Беларуси 🚀",
            'who created you': "I was created by Vadzim (vadzim.by) - full-stack developer from Belarus 🚀"
        }

        # Персонализация на основе уровня навыков
        if skill_level == "beginner":
            base_responses['помощь'] = "🎯 Для новичков рекомендую начать с Python! Хотите пошаговый план обучения?"
            base_responses[
                'help'] = "🎯 For beginners, I recommend starting with Python! Want a step-by-step learning plan?"
        elif skill_level == "intermediate":
            base_responses[
                'помощь'] = "💪 Отлично! Готов помочь с более сложными задачами. Какой проект разрабатываете?"
            base_responses['help'] = "💪 Great! Ready to help with more complex tasks. What project are you working on?"
        elif skill_level == "advanced":
            base_responses['помощь'] = "🚀 Эксперт в деле! Готов обсудить архитектуру, оптимизацию и лучшие практики."
            base_responses['help'] = "🚀 Expert level! Ready to discuss architecture, optimization and best practices."

        return base_responses

    def _build_personalized_prompt(
        self,
        message: str,
        mode: str,
        skill_level: str,
        preferences: dict,
        follow_up: bool = False,
        base_question: Optional[str] = None,
        previous_answer: Optional[str] = None,
        user_tone: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> str:
        """Создает персонализированный промпт на основе уровня навыков и предпочтений"""

        # Базовые описания режимов с более естественными формулировками
        mode_descriptions = {
            "analyze_code": "Проанализируй этот код",
            "debug_code": "Найди и исправь ошибки в коде",
            "explain_concept": "Объясни концепцию",
            "optimize_code": "Оптимизируй код",
            "architecture_advice": "Дай советы по архитектуре",
            "general": "Ответь на вопрос по программированию"
        }

        # Персонализация на основе уровня навыков с более живыми формулировками
        level_adjustments = {
            "beginner": {
                "analyze_code": "Проанализируй этот код простыми словами, как будто объясняешь коллеге-новичку. Объясни каждую важную строку.",
                "debug_code": "Найди ошибки и объясни, почему они возникли и как их исправить. Будь терпеливым и понятным.",
                "explain_concept": "Объясни концепцию очень простыми словами с базовыми примерами. Представь, что объясняешь другу, который только начинает.",
                "optimize_code": "Покажи как улучшить код и объясни почему эти изменения лучше. Используй простые аналогии.",
                "architecture_advice": "Дай простые советы по структуре кода для новичков. Не перегружай терминами.",
                "general": "Ответь простыми словами, добавь примеры для новичков. Будь терпеливым и понятным."
            },
            "intermediate": {
                "analyze_code": "Проанализируй код как опытный коллега: укажи на паттерны, потенциальные улучшения, лучшие практики и частые ошибки.",
                "debug_code": "Найди ошибки и предложи несколько способов исправления с объяснением плюсов и минусов каждого. Предложи лучшие практики.",
                "explain_concept": "Объясни концепцию с практическими примерами и случаями использования. Покажи, где это применяется в реальных проектах и какие есть альтернативы.",
                "optimize_code": "Оптимизируй код, покажи альтернативные подходы и объясни trade-offs. Предложи несколько вариантов с объяснением когда что использовать.",
                "architecture_advice": "Дай советы по архитектуре с учетом масштабируемости, поддерживаемости и лучших практик. Покажи примеры.",
                "general": "Дай подробный ответ с примерами и лучшими практиками. Покажи несколько подходов, если это уместно. Всегда предлагай конкретные следующие шаги."
            },
            "advanced": {
                "analyze_code": "Глубокий анализ как senior-разработчик: архитектура, производительность, безопасность, edge cases, рефакторинг. Будь критичным и конструктивным, предлагай конкретные улучшения.",
                "debug_code": "Найди ошибки, проанализируй root cause, предложи системные решения и профилактику. Покажи несколько подходов с trade-offs.",
                "explain_concept": "Детальное объяснение с продвинутыми паттернами, edge cases, альтернативными подходами и реальными примерами из production.",
                "optimize_code": "Продвинутая оптимизация: алгоритмы, память, производительность, масштабируемость. Покажи trade-offs и когда что использовать.",
                "architecture_advice": "Экспертные советы по enterprise архитектуре, паттернам, anti-patterns и масштабированию. Дай практические рекомендации.",
                "general": "Экспертный ответ с глубоким техническим анализом. Можешь быть более кратким и техничным, но всегда с практическими примерами."
            }
        }

        # Получаем персонализированное описание
        task = level_adjustments.get(skill_level, {}).get(mode,
                                                          mode_descriptions.get(mode, mode_descriptions["general"]))

        # Добавляем эмоциональный контекст
        tone_context = ""
        if user_tone == "frustrated":
            tone_context = " Пользователь расстроен и раздражён — будь особенно терпеливым и поддерживающим."
        elif user_tone == "confused":
            tone_context = " Пользователь запутался — объясняй максимально просто и пошагово."
        elif user_tone == "excited":
            tone_context = " Пользователь вдохновлён — поддерживай энтузиазм и предлагай интересные идеи."
        elif user_tone == "negative":
            tone_context = " Пользователь столкнулся с проблемой — будь поддерживающим и конструктивным."

        # Добавляем предпочтения по языкам программирования
        preferred_language = preferences.get('language', '')
        if preferred_language:
            task += f" Если возможно, используй примеры на {preferred_language}."

        # Добавляем стиль объяснения
        if follow_up:
            task += " Пользователь уже получил базовый ответ, так что добавь глубины: продвинутые примеры, лучшие практики, частые ошибки и ресурсы для самостоятельного изучения."

        explanation_style = preferences.get('explanation_style', '')
        if explanation_style == 'detailed':
            task += " Дай максимально подробное объяснение с примерами."
        elif explanation_style == 'concise':
            task += " Будь кратким и по делу, без лишней воды."

        # Добавляем имя пользователя для более личного общения
        name_context = ""
        if user_name:
            name_context = f" Пользователя зовут {user_name} — используй имя естественно, но не слишком часто."

        task += tone_context + name_context
        task += " Предлагай конкретные следующие шаги, добавляй ссылки на документацию, форматируй код в ```язык``` и не повторяй предыдущие объяснения слово в слово."
        task += " Избегай markdown таблиц, предпочитай короткие абзацы или списки, держи ответ в пределах 1200 символов, если только код не требует больше места."
        
        # Добавляем инструкцию про упоминание Вадима когда уместно
        vadzim_context = ""
        message_lower_for_vadzim = message.lower()
        if any(word in message_lower_for_vadzim for word in ["telegram", "бот", "боты", "python", "javascript", "django", "react", "создател", "вадим", "vadzim"]):
            vadzim_context = " Если уместно, можешь упомянуть, что создатель бота Вадим (vadzim.by, @vadzim_belarus) специализируется на Python, JavaScript и Telegram-ботах. Но делай это естественно, только когда это релевантно."
        
        task += vadzim_context

        context_sections: List[str] = []
        if follow_up:
            context_sections.append("Пользователь уже получил базовый ответ ранее. Предоставь более глубокое продолжение: добавь продвинутые примеры, выдели лучшие практики, предупреди о частых ошибках и предложи ресурсы для дальнейшего изучения.")
        if base_question:
            context_sections.append(f"Исходный вопрос пользователя: {base_question}")
        if previous_answer:
            trimmed_answer = previous_answer.strip()
            if len(trimmed_answer) > 800:
                trimmed_answer = trimmed_answer[:800] + '…'
            context_sections.append(f"Предыдущий ответ ассистента (только для справки, не повторяй): {trimmed_answer}")

        context_sections.append(f"Текущее сообщение пользователя: {message}")

        return f"{task}:\n\n" + "\n\n".join(context_sections) + "\n\nВажно: Дай ответ, которым бы гордился senior-разработчик. Будь конкретным, практичным и полезным. Предложи новые идеи, чтобы пользователь продвинулся дальше."

    async def review_submission(
        self,
        lesson_id: str,
        task_summary: str,
        checklist: List[str],
        code: str,
    ) -> SubmissionReview:
        """
        Проверка кода по чеклисту урока (ментор, не валидатор).
        Возвращает status OK|ERROR для логики бота и feedback — текст в чат пользователю.
        """
        if not self.groq_client:
            return {
                "status": "ERROR",
                "feedback": (
                    "Проверка временно недоступна. Если уверен в задании — нажми «✅ Я сделал»; "
                    "иначе попробуй прислать код чуть позже."
                ),
            }

        checklist_text = "\n".join(f"- {c}" for c in checklist) if checklist else "(чеклист пуст — ориентируйся на формулировку задания)"
        user_msg = (
            f"Урок: {lesson_id}\n"
            f"Задание (кратко): {task_summary}\n\n"
            f"Чеклист — проверяй только это:\n{checklist_text}\n\n"
            f"Код ученика:\n{code[:3500]}"
        )
        try:
            response = await self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": CODE_REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.35,
                max_tokens=280,
                timeout=25,
            )
            content = (response.choices[0].message.content or "").strip()
            status, feedback = _parse_submission_review(content)
            return {"status": status, "feedback": feedback}
        except Exception as exc:
            logger.error("review_submission: %s", exc, exc_info=True)
            return {
                "status": "ERROR",
                "feedback": "Сервис проверки перегружен. Попробуй через минуту или нажми «✅ Я сделал».",
            }


# Синглтон
enhanced_ai_handler = EnhancedAIHandler()
