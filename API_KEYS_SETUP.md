# Настройка API ключей

Документ поможет подготовить проект к публикации на GitHub и запуску на Render. Все секреты теперь считываются из переменных окружения, поэтому **никогда не храните реальные ключи в репозитории**.

## 1. Telegram Bot Token
1. Откройте @BotFather и создайте бота.
2. Сохраните токен вида `123456789:AA...`.
3. Добавьте его в файл `.env` (переменная `TELEGRAM_TOKEN`) или настройте в панели Render.

## 2. Groq API
1. Зарегистрируйтесь на [console.groq.com](https://console.groq.com).
2. Создайте API key на вкладке *API Keys*.
3. Запишите значение в `GROQ_API_KEY` внутри `.env`.
4. При необходимости укажите модель (по умолчанию `openai/gpt-oss-20b`) через переменную `GROQ_MODEL`.

## 3. HuggingFace API
1. Войдите на [huggingface.co](https://huggingface.co) и откройте *Settings → Access Tokens*.
2. Сгенерируйте токен с правами `Read`.
3. Сохраните его в `HUGGING_FACE_TOKEN`.
4. Для защищённых моделей нажмите кнопку *Agree and access* на странице модели.

## 4. Файл `.env`

Пример:
```bash
cp .env.example .env
# затем отредактируйте .env
```

`.env` должен содержать минимум:
```
TELEGRAM_TOKEN=...
GROQ_API_KEY=...
HUGGING_FACE_TOKEN=...
# Optional admin settings
CREATOR_USER_ID=
ADMIN_USER_IDS=
```

## 5. Проверка ключей

После заполнения `.env` запустите:
```bash
python test_api.py
python test_models.py
```

## 6. Полезные советы
- Не коммитьте `.env` и реальные значения токенов.
- Для продакшена на Render заведите переменные окружения через Dashboard.
- При ошибках 401/403 убедитесь, что аккаунт подтверждён и модель доступна для вашего токена.

Удачи с деплоем!

## 7. Google Sheets Storage (optional)
1. Enable the Google Sheets API in a Google Cloud project and create a service account.
2. Generate a JSON key for the service account and share the target spreadsheet with the service-account e-mail.
3. Base64-encode the JSON and place the result into the GOOGLE_SHEETS_CREDENTIALS environment variable (example on macOS/Linux: base64 -w0 service-account.json).
4. Set GOOGLE_SHEETS_SPREADSHEET to the spreadsheet URL, key, or name and GOOGLE_SHEETS_WORKSHEET to the tab title (defaults to Users).
5. On Render, add the variables under **Environment** and redeploy. The bot will now persist user statistics directly to the specified sheet.
