"""
Планировщик постов в группу: короткие анонсы без теории.
Полный контент уроков — только в curriculum.py и в ЛС бота.
"""

import asyncio
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from curriculum import get_lesson, lesson_id_for_scheduler_index, total_lessons

try:
    from course_handler import bot_deeplink_course, resolve_bot_username
except Exception:  # при минимальном окружении без course_handler
    async def resolve_bot_username(bot):  # type: ignore
        return (os.getenv("TELEGRAM_BOT_USERNAME") or os.getenv("BOT_USERNAME") or "").strip().lstrip("@")

    def bot_deeplink_course(username: str) -> str:  # type: ignore
        un = (username or "").strip().lstrip("@")
        return f"https://t.me/{un}?start=course"

load_dotenv()

logger = logging.getLogger(__name__)

try:
    from config import TELEGRAM_GROUP_USERNAME, TELEGRAM_TOKEN  # type: ignore
except Exception:
    raw_group_username = os.getenv("TELEGRAM_GROUP_USERNAME", "@learncoding_team") or "@learncoding_team"
    raw_group_username = raw_group_username.strip() or "@learncoding_team"
    if not raw_group_username.startswith("@"):
        raw_group_username = f"@{raw_group_username}"
    TELEGRAM_GROUP_USERNAME = raw_group_username
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")

BOT_TOKEN = TELEGRAM_TOKEN if "TELEGRAM_TOKEN" in locals() else (os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN"))
CHAT_ID = os.getenv("CHAT_ID")
PERIOD_DAYS = int(os.getenv("PERIOD_DAYS", "4"))
TZ = os.getenv("TZ", "Europe/Minsk")
COURSE_SCHEDULER_ENABLED = os.getenv("COURSE_SCHEDULER_ENABLED", "0") == "1"
STATE_FILE = os.getenv("STATE_FILE", "state.json")
# Напоминания: через сколько дней неактивности слать (0 = отключено)
REMINDER_INACTIVE_DAYS = int(os.getenv("REMINDER_INACTIVE_DAYS", "3"))
# Час отправки напоминаний (по TZ), по умолчанию 10:00
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "10"))

MENTOR_URL = "https://t.me/vadzimbelarus"
SITE_URL = "https://vadzim.by/"


_ALLOWED_INLINE_TAGS = {"b", "i", "code", "pre", "a"}


def _sanitize_html_fragment(text: str) -> str:
    """
    Telegram HTML parse_mode не поддерживает произвольные теги (например <button>).
    Оставляем только базовые теги, остальное экранируем.
    """
    if not text:
        return ""

    def repl(m: re.Match) -> str:
        raw = m.group(0)
        inner = m.group(1) or ""
        inner = inner.strip()
        if not inner:
            return html.escape(raw, quote=False)
        # tag name: first token without leading '/'
        first = inner.split()[0]
        name = first.lstrip("/").lower()
        if name in _ALLOWED_INLINE_TAGS:
            return raw
        return html.escape(raw, quote=False)

    return re.sub(r"<([^>]+)>", repl, text)


class CourseScheduler:
    """Публикация в группу: мотивация + кнопки (источник тем — curriculum)."""

    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
        self.scheduler = AsyncIOScheduler(timezone=TZ)
        self.current_index = self.load_index()

    def load_index(self) -> int:
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return int(data.get("lesson_index", 0))
        except Exception as e:
            logger.error("Ошибка загрузки индекса планировщика: %s", e)
        return 0

    def save_index(self, index: int) -> None:
        try:
            data = {"lesson_index": index, "last_updated": datetime.now().isoformat()}
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Ошибка сохранения индекса: %s", e)

    def make_announcement(self, idx: int) -> Dict[str, str]:
        lid = lesson_id_for_scheduler_index(idx)
        L = get_lesson(lid)
        opening = (L.get("opening") or "").strip()
        hook = (L.get("hook") or "").strip()
        teaser_line = opening.split("\n")[0] if opening else (hook[:160] + "…" if len(hook) > 160 else hook)
        return {
            "lesson_id": lid,
            # title может содержать неподдерживаемые HTML-теги (например "<button>")
            "title": _sanitize_html_fragment(str(L.get("title", lid))),
            "badge": html.escape((L.get("progress_badge") or "").strip(), quote=False),
            # teaser часто содержит <code> — оставляем, но режем неподдерживаемые теги
            "teaser": _sanitize_html_fragment(teaser_line),
        }

    async def post_lesson(self) -> None:
        if not self.bot or not CHAT_ID:
            logger.error("BOT_TOKEN или CHAT_ID не настроены")
            return
        if total_lessons() <= 0:
            logger.warning("В curriculum нет уроков — пропуск публикации")
            return

        try:
            ann = self.make_announcement(self.current_index)
            badge_line = f"📍 <b>{ann['badge']}</b>\n\n" if ann["badge"] else ""
            lid_esc = html.escape(str(ann["lesson_id"]), quote=False)
            message_text = (
                f"👋 <b>Сейчас в фокусе курса</b>\n\n"
                f"{badge_line}"
                f"📚 <b>{ann['title']}</b>\n"
                f"<code>{lid_esc}</code>\n\n"
                f"💡 {ann['teaser']}\n\n"
                f"🎯 <b>Теория и практика — только в личке у бота.</b>\n"
                f"Если с ботом ещё не переписывался — жми <b>«Открыть бота»</b> (откроется чат и придёт урок). "
                f"Либо <b>«Начать или продолжить»</b> — тот же шаг по прогрессу.\n\n"
                f"⚡ <b>Быстрый тест</b> — короткая проверка в ЛС (не дублирует полный урок).\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y')}"
            )
            group_slug = TELEGRAM_GROUP_USERNAME.lstrip("@")
            keyboard_rows = []
            bot_un = await resolve_bot_username(self.bot)
            if bot_un:
                keyboard_rows.append(
                    [InlineKeyboardButton("💬 Открыть бота (урок в личке)", url=bot_deeplink_course(bot_un))]
                )
            keyboard_rows.extend(
                [
                    [InlineKeyboardButton("▶️ Начать или продолжить", callback_data="start_course")],
                    [InlineKeyboardButton("⚡ Быстрый тест", callback_data="check_theory")],
                    [InlineKeyboardButton("👤 Ментор", url=MENTOR_URL)],
                    [
                        InlineKeyboardButton("📚 Группа курса", url=f"https://t.me/{group_slug}"),
                        InlineKeyboardButton("🌐 Сайт", url=SITE_URL),
                    ],
                ]
            )
            keyboard = InlineKeyboardMarkup(keyboard_rows)
            message = await self.bot.send_message(
                chat_id=CHAT_ID,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            try:
                await self.bot.pin_chat_message(chat_id=CHAT_ID, message_id=message.message_id)
            except TelegramError as e:
                logger.warning("Не удалось закрепить сообщение: %s", e)

            logger.info("Анонс урока %s (%s)", self.current_index + 1, ann["lesson_id"])
            self.current_index += 1
            self.save_index(self.current_index)

        except Exception as e:
            logger.error("Ошибка публикации анонса: %s", e)

    # ── Тексты напоминаний (выбираются случайно) ──────────────────────────────
    _REMINDER_DM_TEXTS = [
        (
            "👋 <b>{name}</b>, ты не заходил(а) в курс уже {days} дн.\n\n"
            "Всё ок — просто нажми кнопку ниже, и урок придёт прямо сюда. "
            "Ты на <b>{done}/{total}</b> уроке — осталось совсем немного!"
        ),
        (
            "⚡ <b>{name}</b>, курс скучает.\n\n"
            "Ты не открывал(а) уроки {days} дн. "
            "Один урок занимает 3–5 минут — самое время вернуться!"
        ),
        (
            "🔥 <b>{name}</b>, стрик можно возобновить!\n\n"
            "Прошло {days} дн. без урока. Возвращайся — ты уже прошёл(а) <b>{done}</b> из <b>{total}</b> уроков."
        ),
        (
            "📚 <b>{name}</b>, твой прогресс ждёт тебя.\n\n"
            "Не теряй набранный темп — {days} дн. простоя легко закрыть одним уроком сегодня."
        ),
        (
            "💡 <b>{name}</b>, маленький шаг лучше долгого перерыва.\n\n"
            "Ты уже прошёл(а) {done}/{total} уроков. Следующий урок — один клик."
        ),
    ]

    _REMINDER_GROUP_TEXTS = [
        "👀 <b>{mention}</b>, ты давно не появлялся(ась) в курсе — {days} дн. Возвращайся, ждём! 🔥",
        "⚡ <b>{mention}</b>, {days} дней без урока — это много. Один урок сегодня исправит ситуацию!",
        "📚 <b>{mention}</b>, курс не забыл тебя! Возвращайся — твой прогресс на месте.",
        "🚀 <b>{mention}</b>, {days} дней перерыва — но никогда не поздно продолжить. Жми «▶️ Начать»!",
        "💪 <b>{mention}</b>, группа двигается вперёд — присоединяйся! Уже {days} дн. не было уроков.",
    ]

    async def send_reminders(self) -> None:
        """Найти неактивных учеников, отправить DM + упомянуть в группе."""
        if not self.bot or REMINDER_INACTIVE_DAYS <= 0:
            return

        from user_progress import progress_manager
        import random as _random

        inactive = progress_manager.get_inactive_users(inactive_days=REMINDER_INACTIVE_DAYS)
        if not inactive:
            logger.info("Напоминания: нет неактивных пользователей (порог %d дн.)", REMINDER_INACTIVE_DAYS)
            return

        logger.info("Напоминания: найдено %d неактивных пользователей", len(inactive))
        bot_un = await resolve_bot_username(self.bot)

        for u in inactive:
            uid = u["user_id"]
            name = html.escape(u["display_name"] or "Привет")
            username = u.get("username", "")
            days = u["inactive_days"]
            done = u["completed_count"]
            total = u["total_lessons"]

            # ── DM напоминание ────────────────────────────────────────────
            tpl = _random.choice(self._REMINDER_DM_TEXTS)
            dm_text = tpl.format(name=name, days=days, done=done, total=total)

            keyboard_rows = []
            if bot_un:
                keyboard_rows.append(
                    [InlineKeyboardButton("▶️ Продолжить курс", url=bot_deeplink_course(bot_un))]
                )
            keyboard = InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None

            try:
                await self.bot.send_message(
                    chat_id=uid,
                    text=dm_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                logger.info("Напоминание DM → user_id=%s (%s дн. неактивности)", uid, days)
                progress_manager.mark_reminder_sent(uid)
            except Exception as e:
                logger.warning("Напоминание DM user_id=%s: %s", uid, e)
                # Если Forbidden — пользователь заблокировал бота, не логируем как ошибку
                progress_manager.mark_reminder_sent(uid)  # всё равно отмечаем

            # ── Упоминание в группе (только если есть CHAT_ID) ───────────────
            if CHAT_ID:
                if username:
                    # @username — всегда работает
                    mention = f"@{html.escape(username)}"
                else:
                    # Inline mention по user_id (работает если пользователь в группе)
                    mention = f'<a href="tg://user?id={uid}">{name}</a>'

                gtpl = _random.choice(self._REMINDER_GROUP_TEXTS)
                group_text = gtpl.format(mention=mention, days=days)

                try:
                    await self.bot.send_message(
                        chat_id=CHAT_ID,
                        text=group_text,
                        parse_mode="HTML",
                    )
                    logger.info("Напоминание в группу → %s", mention)
                except Exception as e:
                    logger.warning("Напоминание в группу user_id=%s: %s", uid, e)

            # Небольшая пауза между пользователями — не триггерим flood limit
            await asyncio.sleep(0.5)

    def setup_scheduler(self) -> None:
        if not COURSE_SCHEDULER_ENABLED:
            logger.info("Планировщик отключён (COURSE_SCHEDULER_ENABLED=0)")
            return
        if not BOT_TOKEN or not CHAT_ID:
            logger.error("BOT_TOKEN или CHAT_ID не заданы")
            return

        self.scheduler.add_job(
            self.post_lesson,
            "date",
            run_date=datetime.now() + timedelta(seconds=5),
            id="first_lesson",
        )
        self.scheduler.add_job(
            self.post_lesson,
            IntervalTrigger(days=PERIOD_DAYS),
            id="recurring_lessons",
        )

        # Напоминания неактивным — каждый день в REMINDER_HOUR:00
        if REMINDER_INACTIVE_DAYS > 0:
            self.scheduler.add_job(
                self.send_reminders,
                "cron",
                hour=REMINDER_HOUR,
                minute=0,
                id="daily_reminders",
            )
            logger.info(
                "Напоминания: неактивность >%d дн., каждый день в %02d:00",
                REMINDER_INACTIVE_DAYS,
                REMINDER_HOUR,
            )
        logger.info("Планировщик: период %s дн., TZ=%s", PERIOD_DAYS, TZ)

    async def run_forever(self) -> None:
        self.setup_scheduler()
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Планировщик запущен")
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Остановка планировщика…")
            self.scheduler.shutdown()


scheduler = CourseScheduler()


async def run_forever():
    await scheduler.run_forever()
