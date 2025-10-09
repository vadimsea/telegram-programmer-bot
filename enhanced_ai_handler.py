"""
Enhanced AI Handler - с правильным форматированием кода для Telegram (исправленный)
"""

import asyncio
import logging
import random
import re
from typing import List, Optional, Set, Tuple
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL, SYSTEM_PROMPT

try:
    from smart_features import smart_features  # ✅ Подключаем умные функции
    from database import user_db  # ✅ Подключаем базу данных
except ImportError:
    smart_features = None
    user_db = None

logger = logging.getLogger(__name__)


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
    def _match_small_talk(self, message_lower: str) -> Optional[str]:
        for preset in self.SMALL_TALK_PRESETS:
            if any(trigger in message_lower for trigger in preset["triggers"]):
                return random.choice(preset["responses"])
        return None

    def _detect_message_tone(self, message_lower: str) -> Optional[str]:
        if any(keyword in message_lower for keyword in self.NEGATIVE_KEYWORDS):
            return "negative"
        if any(keyword in message_lower for keyword in self.POSITIVE_KEYWORDS):
            return "positive"
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
                return small_talk_reply, False

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

            if "калькулятор" in message_lower:
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
                                "Хочешь расширенную версию с меню, обработкой ошибок или GUI — скажи, подскажу.")
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
            if self.groq_client:
                try:
                    prompt = self._build_personalized_prompt(
                        message,
                        mode,
                        skill_level,
                        preferences,
                        follow_up=follow_up,
                        base_question=base_question,
                        previous_answer=previous_answer,
                    )
                    logger.info(f"🔄 Отправка запроса к Groq (mode={mode}, level={skill_level}): {message[:50]}...")

                    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

                    # Add conversation history if available
                    if user_context and hasattr(user_context, 'history') and user_context.history:
                        # Get last 6 messages (3 exchanges) for context
                        recent_history = user_context.get_recent_context(6)
                        for msg in recent_history:
                            if msg['role'] == 'user':
                                messages.append({"role": "user", "content": msg['content']})
                            elif msg['role'] == 'assistant':
                                messages.append({"role": "assistant", "content": msg['content']})

                    # Add current message
                    messages.append({"role": "user", "content": prompt})

                    response = await self.groq_client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=1000,
                        timeout=15
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
                    tone = self._detect_message_tone(message_lower)
                    if tone:
                        ai_response = self._augment_with_tone(ai_response, tone)
                    ai_response = self._maybe_add_personal_tip(ai_response, preferences, user_context, message_lower)
                    logger.info("✅ Успешный ответ от Groq")
                    return self._format_for_telegram(ai_response), False

                except asyncio.TimeoutError:
                    logger.warning("⏰ Таймаут запроса к Groq")
                    return "⏰ ИИ долго думает... Попробуйте задать вопрос короче.", True
                except Exception as e:
                    logger.error(f"❌ Ошибка Groq: {e}")
                    return self._get_fallback_response(message, mode), True

            return self._get_fallback_response(message, mode), True

        except Exception as e:
            logger.error(f"🔥 Критическая ошибка: {e}")
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
        response = "🔍 **Анализ Python кода:**\n\n"
        response += f"\`\`\`python\n{code}\n\`\`\`\n\n"
        response += "✅ Код выглядит корректно для Python"
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
            "analyze_code": "Не удалось быстро разобрать код. Отправь его ещё раз и уточни, что именно смущает.",
            "debug_code": "Не получилось воспроизвести проблему. Проверь, хватает ли контекста, и пришли пример повторно.",
            "explain_concept": "Пока не удалось подобрать объяснение. Сформулируй вопрос иначе или добавь деталей.",
            "optimize_code": "Сейчас не получилось предложить оптимизацию. Попробуй описать цель подробнее и повтори запрос.",
            "architecture_advice": "Не успел сформировать архитектурный совет. Дай больше информации о проекте и спроси ещё раз.",
            "general": "Не удалось получить ответ от модели. Повтори вопрос через несколько секунд — я уже готов снова помочь."
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
    ) -> str:
        """Создает персонализированный промпт на основе уровня навыков и предпочтений"""

        # Базовые описания режимов
        mode_descriptions = {
            "analyze_code": "Проанализируй этот код",
            "debug_code": "Найди и исправь ошибки в коде",
            "explain_concept": "Объясни концепцию",
            "optimize_code": "Оптимизируй код",
            "architecture_advice": "Дай советы по архитектуре",
            "general": "Ответь на вопрос по программированию"
        }

        # Персонализация на основе уровня навыков
        level_adjustments = {
            "beginner": {
                "analyze_code": "Проанализируй этот код простыми словами, объясни каждую строку",
                "debug_code": "Найди ошибки и объясни, почему они возникли и как их исправить",
                "explain_concept": "Объясни концепцию очень простыми словами с базовыми примерами",
                "optimize_code": "Покажи как улучшить код и объясни почему эти изменения лучше",
                "architecture_advice": "Дай простые советы по структуре кода для новичков",
                "general": "Ответь простыми словами, добавь примеры для новичков"
            },
            "intermediate": {
                "analyze_code": "Проанализируй код, укажи на паттерны и потенциальные улучшения",
                "debug_code": "Найди ошибки, предложи несколько способов исправления",
                "explain_concept": "Объясни концепцию с практическими примерами и случаями использования",
                "optimize_code": "Оптимизируй код, покажи альтернативные подходы",
                "architecture_advice": "Дай советы по архитектуре с учетом масштабируемости",
                "general": "Дай подробный ответ с примерами и лучшими практиками"
            },
            "advanced": {
                "analyze_code": "Глубокий анализ: архитектура, производительность, безопасность",
                "debug_code": "Найди ошибки, проанализируй root cause, предложи системные решения",
                "explain_concept": "Детальное объяснение с продвинутыми паттернами и edge cases",
                "optimize_code": "Продвинутая оптимизация: алгоритмы, память, производительность",
                "architecture_advice": "Экспертные советы по enterprise архитектуре и паттернам",
                "general": "Экспертный ответ с глубоким техническим анализом"
            }
        }

        # Получаем персонализированное описание
        task = level_adjustments.get(skill_level, {}).get(mode,
                                                          mode_descriptions.get(mode, mode_descriptions["general"]))

        # Добавляем предпочтения по языкам программирования
        preferred_language = preferences.get('language', '')
        if preferred_language:
            task += f". Если возможно, используй примеры на {preferred_language}"

        # Добавляем стиль объяснения
        if follow_up:
            task += ". User already received a basic answer, so add new depth: advanced examples, best practices, common mistakes, and references for self-study"

        explanation_style = preferences.get('explanation_style', '')
        if explanation_style == 'detailed':
            task += ". Дай максимально подробное объяснение"
        elif explanation_style == 'concise':
            task += ". Будь кратким и по делу"

        task += ". Provide actionable next steps, add links to docs, format code in ```language``` and do not repeat previous explanations word for word"

        context_sections: List[str] = []
        if follow_up:
            context_sections.append("The user already received a basic answer earlier. Provide a deeper continuation: add advanced examples, highlight best practices, warn about common pitfalls, and suggest resources to study next.")
        if base_question:
            context_sections.append(f"Original question from the user: {base_question}")
        if previous_answer:
            trimmed_answer = previous_answer.strip()
            if len(trimmed_answer) > 800:
                trimmed_answer = trimmed_answer[:800] + '…'
            context_sections.append(f"Previous assistant answer (reference only, do not repeat): {trimmed_answer}")

        context_sections.append(f"Current user message: {message}")

        return f"{task}:\n\n" + "\n\n".join(context_sections) + "\n\nПредложи новые идеи, чтобы пользователь продвинулся дальше."


# Синглтон
enhanced_ai_handler = EnhancedAIHandler()
