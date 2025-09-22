# 🤖 Telegram Bot для программистов

Интеллектуальный Telegram бот на Python с ИИ ответами для помощи программистам. Поддерживает русский язык, Markdown форматирование и использует бесплатные API.

## ✨ Возможности

- 🧠 **ИИ ответы** - умные ответы на вопросы по программированию
- 🇷🇺 **Русский язык** - полная поддержка русского языка
- 📝 **Markdown** - красивое форматирование кода и текста
- 💰 **Бесплатные API** - использует Groq и HuggingFace API
- 🔧 **Резервные ответы** - работает даже когда API недоступны
- 📚 **Помощь программистам** - специализация на вопросах разработки

## 🚀 Быстрый старт

### 🖥️ Локальный запуск

#### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

#### 2. Configure environment variables

Copy `.env.example` to `.env` and fill it with your real credentials before running the bot locally.

```bash
cp .env.example .env
# Edit .env and set TELEGRAM_TOKEN, GROQ_API_KEY, HUGGING_FACE_TOKEN
```

#### 3. Запуск
```bash
python main.py
```

### 🌐 Деплой 24/7 (Рекомендуется)

#### Автоматический деплой на Railway:
```bash
python deploy_railway.py
```

#### Ручной деплой:
1. Создайте аккаунт на [railway.app](https://railway.app)
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения
4. Бот автоматически запустится и будет работать 24/7!

#### Деплой на Render:
1. Подготовьте репозиторий (без секретов) и запушьте на GitHub.
2. На Render создайте *Blueprint* и укажите файл `render.yaml`.
3. В разделе Environment добавьте TELEGRAM_TOKEN, GROQ_API_KEY, HUGGING_FACE_TOKEN.
4. Запустите сервис — Render установит зависимости и выполнит `python main.py`.

**📖 Подробная инструкция в [DEPLOY.md](DEPLOY.md)**

## 📋 Команды бота

- `/start` - Приветствие и описание возможностей
- `/help` - Справка по использованию
- Любой текст - Вопрос программисту-ИИ

## 💡 Примеры использования

**Вопросы по Python:**
```
Как работает рекурсия в Python?
```

**Примеры кода:**
```
Покажи пример REST API на Flask
```

**Отладка:**
```
Почему выдает ошибку IndexError?
```

**Алгоритмы:**
```
Объясни алгоритм быстрой сортировки
```

## 🛠️ Структура проекта

```
├── main.py              # Основной файл бота
├── config.py            # Конфигурация и настройки
├── ai_handler.py        # Обработчик ИИ запросов
├── utils.py             # Вспомогательные функции
├── requirements.txt     # Зависимости Python
├── todo.md             # План разработки
└── README.md           # Документация
```

## 🔧 Конфигурация

### API ключи

Для полной функциональности получите бесплатные API ключи:

**Groq API (рекомендуется):**
1. Зарегистрируйтесь на [console.groq.com](https://console.groq.com)
2. Получите API ключ
3. Добавьте `GROQ_API_KEY` в `.env` или переменные окружения хостинга

**HuggingFace API:**
1. Зарегистрируйтесь на [huggingface.co](https://huggingface.co)
2. Получите токен в настройках
3. Добавьте `HUGGING_FACE_TOKEN` в `.env` или переменные окружения хостинга

### Настройки бота

В `config.py` можно изменить:
- `MAX_MESSAGE_LENGTH` - максимальная длина сообщения
- `TYPING_DELAY` - задержка печати
- `SYSTEM_PROMPT` - системный промпт для ИИ
- Тексты сообщений в `MESSAGES`

## 🚀 Развертывание

### Локальный запуск
```bash
python main.py
```

### На сервере (systemd)
```bash
# Создать сервис
sudo nano /etc/systemd/system/programmer-bot.service

# Содержимое:
[Unit]
Description=Programmer Telegram Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/bot
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target

# Запустить сервис
sudo systemctl enable programmer-bot
sudo systemctl start programmer-bot
```

### Docker
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

## 📊 Логирование

Бот ведет подробные логи:
- Запросы пользователей
- Ответы ИИ
- Ошибки и исключения
- Статистика использования

## 🔍 Отладка

Если бот не работает, проверьте:

1. **Токен бота** — задаётся через переменную окружения `TELEGRAM_TOKEN`
2. **Интернет** - доступность API
3. **Зависимости** - установлены ли все пакеты
4. **Логи** - сообщения об ошибках в консоли

## 🤝 Поддержка

Поддерживаемые языки программирования:
- Python 🐍
- JavaScript ⚡
- Java ☕
- C++ ⚙️
- C# 💎
- Go 🚀
- Rust 🦀
- PHP 🐘
- Swift 🍎
- Kotlin 📱

## 📈 Возможности расширения

- Добавление новых API провайдеров
- Интеграция с GitHub для анализа кода
- Поддержка голосовых сообщений
- Система рейтингов ответов
- Сохранение истории диалогов
- Многоязычная поддержка

## 🚀 Деплой 24/7

### 🆓 Бесплатные хостинги

- **Railway** - 500 часов/месяц, автоматический деплой
- **Render** - 750 часов/месяц, надежность
- **PythonAnywhere** - 512 МБ RAM, специализация на Python

### 📱 Автоматический деплой

```bash
# Установка зависимостей
pip install -r requirements.txt

# Автоматический деплой на Railway
python deploy_railway.py
```

### 🔧 Ручная настройка

1. Создайте аккаунт на выбранной платформе
2. Подключите GitHub репозиторий
3. Добавьте переменные окружения
4. Бот автоматически запустится!

**📖 Подробная инструкция: [DEPLOY.md](DEPLOY.md)**

## 📄 Лицензия

MIT License - используйте свободно для любых целей.

## 👨‍💻 Автор

Создано **Вадимом** (vadzim.by) для сообщества программистов.

---

**Готов помочь программистам 24/7! 🚀**

