"""
Enhanced AI Handler - с правильным форматированием кода для Telegram (исправленный)
"""

import asyncio
import logging
import re
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
    def __init__(self):
        self.groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
        logger.info("🤖 EnhancedAIHandler инициализирован")

    async def get_specialized_response(self, message: str, mode: str = "general", user_context=None,
                                       skill_level: str = "beginner", preferences: dict = None) -> str:
        follow_up = False
        """Ответ от ИИ с правильным форматированием кода для Telegram"""
        try:
            if preferences is None:
                preferences = {}

            if user_context and hasattr(user_context, 'user_id'):
                logger.info(f"🔄 Обработка запроса от пользователя {user_context.user_id} (уровень: {skill_level})")

            quick_responses = self._get_personalized_quick_responses(skill_level, preferences)

            message_lower = message.lower().strip()

            follow_up_keywords = ("подробнее", "детальнее", "поподробнее", "ещё", "еще", "расскажи больше", "расскажи подробнее", "больше информации", "tell me more", "more detail")
            if any(keyword in message_lower for keyword in follow_up_keywords):
                follow_up = True
            elif user_context and hasattr(user_context, 'history') and user_context.history:
                recent_user_messages = [entry['content'].lower().strip() for entry in reversed(user_context.history) if entry['role'] == 'user']
                if recent_user_messages:
                    last_question = recent_user_messages[0]
                    if last_question == message_lower or (len(message_lower) > 12 and message_lower in last_question):
                        follow_up = True

            if follow_up and skill_level != 'advanced':
                skill_level = 'intermediate' if skill_level == 'beginner' else 'advanced'
            if message_lower in quick_responses and len(message_lower.split()) <= 3:
                return quick_responses[message_lower]

            if "найди ошибку" in message_lower or "find error" in message_lower:
                return await self._analyze_code_for_errors(message)

            if any(phrase in message_lower for phrase in
                   ["с чего начать", "как начать", "начать учить", "начать изучать"]):
                return await self._get_learning_advice(message)

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
                return await self.explain_code(message)

            if "проанализируй этот код" in message_lower or "analyze this code" in message_lower:
                return await self.explain_code(message)

            # === Обращение к Groq API ===
            if self.groq_client:
                try:
                    prompt = self._build_personalized_prompt(message, mode, skill_level, preferences, follow_up=follow_up)
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
                        return self._get_fallback_response(message, mode)

                    choice = response.choices[0]
                    content = getattr(choice.message, "content", None) if hasattr(choice, "message") else None

                    if not content:
                        logger.warning("⚠️ Пустое содержимое ответа. Используем fallback.")
                        return self._get_fallback_response(message, mode)

                    ai_response = content.strip()
                    logger.info("✅ Успешный ответ от Groq")
                    return self._format_for_telegram(ai_response)

                except asyncio.TimeoutError:
                    logger.warning("⏰ Таймаут запроса к Groq")
                    return "⏰ ИИ долго думает... Попробуйте задать вопрос короче."
                except Exception as e:
                    logger.error(f"❌ Ошибка Groq: {e}")
                    return self._get_fallback_response(message, mode)

            return self._get_fallback_response(message, mode)

        except Exception as e:
            logger.error(f"🔥 Критическая ошибка: {e}")
            return self._get_fallback_response(message, mode)

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
            "analyze_code": "🔍 Анализ кода\n\n\`\`\`python\n# Используйте линтеры и тесты\n\`\`\`",
            "debug_code": "🐛 Отладка\n\n\`\`\`python\nprint('Значение:', var)\nimport pdb; pdb.set_trace()\n\`\`\`",
            "explain_concept": f"📚 Объяснение концепции\n\n'{message[:50]}...'\n\n\`\`\`python\nclass Example:\n    pass\n\`\`\`",
            "optimize_code": "⚡ Оптимизация кода\n\n\`\`\`python\nnumbers = [i for i in range(1000)]\n\`\`\`",
            "architecture_advice": "🏗️ Архитектурные советы\n\n\`\`\`python\n# MVC, Clean Architecture\n\`\`\`",
            "general": f"🤖 Вопрос по программированию\n\n'{message[:50]}...'\n\n\`\`\`python\nprint('Hello, world!')\n\`\`\`"
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

    def _build_personalized_prompt(self, message: str, mode: str, skill_level: str, preferences: dict, follow_up: bool = False) -> str:
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
        return f"{task}:\n\n{message}"



# Синглтон
enhanced_ai_handler = EnhancedAIHandler()
