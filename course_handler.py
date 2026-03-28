"""
Курс: уроки в ЛС, короткий анонс в группу, прогресс в user_progress.
Inline-кнопки под уроком не удаляются — новые шаги идут новыми сообщениями.
"""

import html
import logging
import os
import re
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram.error import TelegramError, Forbidden

from permissions import is_admin_identity
from curriculum import (
    LESSON_ORDER,
    get_lesson,
    lesson_id_for_scheduler_index,
    total_lessons,
)
from user_progress import progress_manager

load_dotenv()

try:
    from config import TELEGRAM_GROUP_USERNAME, TELEGRAM_TOKEN  # type: ignore
except Exception:
    raw_group_username = os.getenv("TELEGRAM_GROUP_USERNAME", "@learncoding_team") or "@learncoding_team"
    raw_group_username = raw_group_username.strip() or "@learncoding_team"
    if not raw_group_username.startswith("@"):
        raw_group_username = f"@{raw_group_username}"
    TELEGRAM_GROUP_USERNAME = raw_group_username
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")

logger = logging.getLogger(__name__)

BOT_TOKEN = TELEGRAM_TOKEN if "TELEGRAM_TOKEN" in locals() else (os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN"))
CHAT_ID = os.getenv("CHAT_ID")

MENTOR_TG_URL = "https://t.me/vadzimbelarus"
MENTOR_SITE_URL = "https://vadzim.by/"


def get_mentor_forward_chat_id() -> Optional[int]:
    """Куда пересылать запросы «на ментора» (env > создатель > первый админ)."""
    raw = os.getenv("MENTOR_FORWARD_CHAT_ID", "").strip()
    if raw.isdigit():
        return int(raw)
    try:
        from config import CREATOR_USER_ID, ADMIN_USER_IDS  # type: ignore

        if CREATOR_USER_ID is not None:
            return int(CREATOR_USER_ID)
        if ADMIN_USER_IDS:
            return int(ADMIN_USER_IDS[0])
    except Exception:
        pass
    return None


def build_lesson_keyboard(lesson_id: str, include_next: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("✅ Я сделал", callback_data=f"hw_done_{lesson_id}"),
            InlineKeyboardButton("💬 Отправить код", callback_data=f"codehelp_{lesson_id}"),
        ],
        [InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{lesson_id}")],
        [InlineKeyboardButton("⚡ Быстрый тест", callback_data=f"theoryquiz_{lesson_id}")],
        [
            InlineKeyboardButton("👤 Ментор", callback_data=f"mentor_{lesson_id}"),
            InlineKeyboardButton("🌐 Сайт ментора", url=MENTOR_SITE_URL),
        ],
        [
            InlineKeyboardButton("📚 Группа курса", url=f"https://t.me/{TELEGRAM_GROUP_USERNAME.lstrip('@')}"),
        ],
    ]
    if include_next:
        rows.insert(0, [InlineKeyboardButton("📖 Следующий урок", callback_data="cnext")])
    return InlineKeyboardMarkup(rows)


_lesson_keyboard = build_lesson_keyboard


def _quiz_callback_data(lesson_id: str, q_idx: int, choice: int) -> str:
    return f"quiz_{lesson_id}*{q_idx}*{choice}"


def _quiz_keyboard(lesson_id: str, q_idx: int) -> Optional[InlineKeyboardMarkup]:
    try:
        lesson = get_lesson(lesson_id)
    except KeyError:
        return None
    quiz_list = lesson.get("quiz") or []
    if q_idx < 0 or q_idx >= len(quiz_list):
        return None
    q = quiz_list[q_idx]
    opts = q.get("options") or []
    rows = []
    for i, label in enumerate(opts):
        cb = _quiz_callback_data(lesson_id, q_idx, i)
        if len(cb) > 64:
            logger.error("quiz callback too long: %s", cb)
            continue
        rows.append([InlineKeyboardButton(str(label), callback_data=cb)])
    return InlineKeyboardMarkup(rows) if rows else None


async def send_micro_quiz(bot, user_id: int, lesson_id: str, question_idx: int = 0) -> bool:
    """
    Одно сообщение с одним вопросом и 2–3 кнопками. Без хранения состояния.
    """
    try:
        lesson = get_lesson(lesson_id)
    except KeyError:
        lesson_id = LESSON_ORDER[0]
        lesson = get_lesson(lesson_id)
    quiz_list = lesson.get("quiz") or []
    if not quiz_list or question_idx >= len(quiz_list):
        try:
            await bot.send_message(
                chat_id=user_id,
                text="Для этого блока тест ещё не настроен — переходи к практике в уроке.",
            )
        except (TelegramError, Forbidden):
            return False
        return False
    q = quiz_list[question_idx]
    kb = _quiz_keyboard(lesson_id, question_idx)
    if not kb:
        return False
    text = (
        f"⚡ <b>Быстрый тест</b> ({question_idx + 1}/{len(quiz_list)})\n"
        f"<code>{lesson_id}</code>\n\n"
        f"❓ {q['q']}"
    )
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
        )
        return True
    except Forbidden:
        logger.warning("send_micro_quiz: user %s has not started bot", user_id)
        return False
    except TelegramError as e:
        logger.warning("send_micro_quiz: %s", e)
        return False


class CourseHandler:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

    def _lesson_message(self, lesson_id: str) -> str:
        L = get_lesson(lesson_id)
        badge = L.get("progress_badge")
        opening = L.get("opening")
        head = f"📌 <b>{L['title']}</b> <code>({lesson_id})</code>"
        if badge:
            head = f"📍 <b>{badge}</b>\n{head}"
        blocks = [head]
        if opening:
            blocks.append(opening)
        blocks.append(L["hook"])
        body = (
            "\n\n".join(blocks)
            + f"\n\n📖 <b>Теория</b>\n{L['theory']}\n\n"
            f"⚡ <b>Нюанс</b>\n{L['nuance']}\n\n"
            f"🛠 <b>Задание</b>\n{L['task']}\n\n"
            "Снизу кнопки: тест ⚡, потом практика; ИИ проверит код; ментор — если совсем стоп."
        )
        if lesson_id == LESSON_ORDER[-1]:
            body += (
                "\n\n🌐 Этот урок плотнее остальных — если захочешь системности, загляни на "
                f'<a href="{html.escape(MENTOR_SITE_URL)}">vadzim.by</a> — там база автора курса.'
            )
        return body

    async def send_lesson_dm(self, user_id: int, lesson_id: str) -> bool:
        if not self.bot:
            return False
        try:
            text = self._lesson_message(lesson_id)
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=build_lesson_keyboard(lesson_id),
                parse_mode="HTML",
            )
            return True
        except Forbidden:
            logger.warning("User %s has not started the bot", user_id)
            return False
        except TelegramError as e:
            logger.error("send_lesson_dm: %s", e)
            return False

    async def announce_group(self, display_name: str, lesson_id: str, kind: str) -> None:
        if not self.bot or not CHAT_ID:
            return
        L = get_lesson(lesson_id)
        safe = html.escape(display_name or "Участник")
        if kind == "opened":
            text = (
                f"🔥 {safe} забрал урок в личку: <b>{html.escape(L['title'])}</b>.\n"
                f"Кто ещё в деле — жми «Начать обучение» выше."
            )
        elif kind == "done":
            text = (
                f"✅ {safe} закрыл(а) <b>{html.escape(L['title'])}</b> — красота.\n"
                f"Следующий урок уже жмёт в боте."
            )
        else:
            text = f"{safe} двигается по курсу: {html.escape(L['title'])} ⚡"
        try:
            await self.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
        except TelegramError as e:
            logger.warning("announce_group: %s", e)

    async def send_welcome_message(self, chat_id: str) -> bool:
        if not self.bot:
            return False
        try:
            welcome_text = (
                "🎉 <b>Курс по фронтенду</b>\n\n"
                "Уроки приходят <b>в личку боту</b> — нажми кнопку ниже и открой диалог с ботом, если ещё не открывал.\n\n"
                "📊 /progress — прогресс (в группе или в ЛС)\n"
                "📖 /next — следующий урок (когда предыдущий закрыт)\n\n"
                "<b>Начнём?</b>"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🎓 Начать обучение", callback_data="start_course")],
                    [
                        InlineKeyboardButton("👤 Написать ментору", url=MENTOR_TG_URL),
                        InlineKeyboardButton("🌐 Сайт ментора", url=MENTOR_SITE_URL),
                    ],
                ]
            )
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            try:
                await self.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            except TelegramError:
                pass
            return True
        except Exception as e:
            logger.error("send_welcome_message: %s", e)
            return False


course_handler = CourseHandler()


def _display_name(user) -> str:
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return "Участник"


async def _open_lesson_for_user(user_id: int, display_name: str, lesson_id: str) -> tuple[bool, str]:
    progress_manager.set_active_lesson(user_id, lesson_id)
    ok = await course_handler.send_lesson_dm(user_id, lesson_id)
    if not ok:
        return False, "Сначала открой диалог с ботом: напиши ему /start в личку, потом снова нажми кнопку в группе."
    await course_handler.announce_group(display_name, lesson_id, "opened")
    return True, ""


async def deliver_next_lesson(user_id: int, display_name: str) -> tuple[bool, str]:
    total = total_lessons()
    if not progress_manager.can_open_next_lesson(user_id, total):
        active = progress_manager.get_active_lesson_id(user_id)
        if active:
            return False, "Сначала закрой текущий урок: «✅ Я сделал» или пришли код на проверку."
        return False, "Ты уже прошёл все уроки этого блока 🎉"
    cur = progress_manager.get_cursor(user_id)
    lesson_id = LESSON_ORDER[cur]
    ok, err = await _open_lesson_for_user(user_id, display_name, lesson_id)
    return ok, err


async def _finalize_lesson(user_id: int, display_name: str, lesson_id: str) -> None:
    progress_manager.complete_lesson(user_id, lesson_id)
    await course_handler.announce_group(display_name, lesson_id, "done")
    if course_handler.bot:
        try:
            win = get_lesson(lesson_id).get("win_message", "").strip()
            if win:
                await course_handler.bot.send_message(
                    chat_id=user_id,
                    text=win,
                    parse_mode="HTML",
                )
        except KeyError:
            pass
        done_n = len(progress_manager.get_user_progress(user_id).get("completed_lesson_ids") or [])
        if done_n == 3:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text=(
                    "🔥 Три урока позади — отличный темп.\n"
                    f'Если хочешь смотреть, кто стоит за курсом: <a href="{html.escape(MENTOR_SITE_URL)}">vadzim.by</a> — '
                    "там материалы и контакты без лишнего шума."
                ),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        if done_n == 5:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text=(
                    "🎯 Уже пять уроков — ты в потоке.\n"
                    "На сайте ментора иногда появляются доп. форматы и апдейты — "
                    f'<a href="{html.escape(MENTOR_SITE_URL)}">загляни, когда будет минутка</a>.'
                ),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        total = total_lessons()
        if progress_manager.can_open_next_lesson(user_id, total):
            await course_handler.bot.send_message(
                chat_id=user_id,
                text="🎉 Урок засчитан. Готов к следующему?",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Следующий урок", callback_data="cnext")]]),
                parse_mode="HTML",
            )
        else:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text="🏁 Этот блок завершён. Скоро добавим новые уроки — следи за группой.",
                parse_mode="HTML",
            )


async def course_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != CHAT_ID:
        await update.message.reply_text(f"Команда только в группе {TELEGRAM_GROUP_USERNAME}")
        return
    success = await course_handler.send_welcome_message(chat_id)
    if success:
        await update.message.reply_text("✅ Приветствие в группе. Закрепи при необходимости.")
    else:
        await update.message.reply_text("❌ Ошибка отправки.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = (query.data or "").strip()
    if data.startswith(("admin_", "feedback_")):
        return

    bot = context.bot
    user = query.from_user
    user_id = user.id
    name = _display_name(user)
    chat = update.effective_chat

    # --- Личка: уроковые колбэки ---
    if chat.type == ChatType.PRIVATE:
        if not data.startswith("quiz_"):
            await query.answer()
        if data == "cnext":
            if progress_manager.is_rate_limited(user_id, "lesson"):
                await query.message.reply_text("⏰ Подожди минуту между уроками.")
                return
            ok, err = await deliver_next_lesson(user_id, name)
            if not ok:
                await query.message.reply_text(err)
            return

        if data.startswith("hw_done_"):
            lesson_id = data[8:]
            if lesson_id != progress_manager.get_active_lesson_id(user_id):
                await query.message.reply_text("Это не активный урок. Открой актуальный из /next.")
                return
            await _finalize_lesson(user_id, name, lesson_id)
            return

        if data.startswith("hint_"):
            lesson_id = data[5:]
            if lesson_id != progress_manager.get_active_lesson_id(user_id):
                await query.message.reply_text("Сначала открой урок через группу или /next.")
                return
            progress_manager.clear_expects_mentor(user_id)
            hint = get_lesson(lesson_id).get("hint", "Подумай ещё раз над формулировкой задания.")
            await query.message.reply_text(f"💡 {hint}", reply_markup=build_lesson_keyboard(lesson_id))
            return

        if data.startswith("codehelp_"):
            lesson_id = data[9:]
            if lesson_id != progress_manager.get_active_lesson_id(user_id):
                await query.message.reply_text("Нет активного урока для кода.")
                return
            progress_manager.clear_expects_mentor(user_id)
            progress_manager.set_expects_code(user_id, lesson_id)
            await query.message.reply_text(
                "📎 Пришли HTML одним сообщением (можно в блоке ```html ... ```). Проверю по чеклисту урока.",
                reply_markup=build_lesson_keyboard(lesson_id),
            )
            return

        if data.startswith("theoryquiz_"):
            lesson_id = data[12:]
            await send_micro_quiz(bot, user_id, lesson_id, 0)
            return

        if data.startswith("quiz_"):
            rest = data[5:]
            parts = rest.split("*")
            if len(parts) != 3:
                await query.answer()
                await query.message.reply_text("Кнопка теста устарела — нажми «⚡ Быстрый тест» снова.")
                return
            lid, qis, cis = parts[0], parts[1], parts[2]
            try:
                qi = int(qis)
                ci = int(cis)
            except ValueError:
                await query.answer()
                return
            try:
                lesson = get_lesson(lid)
            except KeyError:
                await query.answer("Урок не найден.", show_alert=True)
                return
            quiz_list = lesson.get("quiz") or []
            if qi < 0 or qi >= len(quiz_list):
                await query.answer("Вопрос устарел.", show_alert=True)
                return
            q = quiz_list[qi]
            correct = int(q.get("correct", 0))
            if ci == correct:
                await query.answer("✅ Верно!", show_alert=True)
                if qi + 1 < len(quiz_list):
                    await send_micro_quiz(bot, user_id, lid, qi + 1)
                else:
                    active = progress_manager.get_active_lesson_id(user_id)
                    kb = build_lesson_keyboard(active) if active else build_lesson_keyboard(lid)
                    qdone = (lesson.get("quiz_done_line") or "").strip()
                    if not qdone:
                        qdone = (
                            "🎯 Тест пройден. Ты уже в теме — осталось руками: "
                            "«✅ Я сделал» или «💬 Отправить код»."
                        )
                    await query.message.reply_text(qdone, reply_markup=kb)
            else:
                hint = (q.get("wrong_hint") or "Загляни в теорию урока.").strip()
                if len(hint) > 180:
                    hint = hint[:177] + "…"
                await query.answer(f"❌ Почти — {hint}", show_alert=True)
            return

        if data.startswith("mentor_"):
            lesson_id = data[7:]
            if lesson_id != progress_manager.get_active_lesson_id(user_id):
                await query.message.reply_text("Сначала открой актуальный урок через группу или /next.")
                return
            progress_manager.set_expects_mentor(user_id, lesson_id)
            await query.message.reply_text(
                "👤 <b>Опиши, что не получается</b> (одним сообщением):\n"
                "• что уже сделал\n"
                "• где затык / ошибка\n"
                "• приложи код или скрин текстом\n\n"
                "Сначала бот и ИИ закрывают большую часть вопросов — это сообщение уйдёт ментору целиком.\n"
                "Отменить режим: нажми «💡 Подсказка» или «💬 Отправить код».",
                reply_markup=build_lesson_keyboard(lesson_id),
                parse_mode="HTML",
            )
            return

        await query.message.reply_text("Неизвестная команда курса.")
        return

    # --- Группа ---
    if str(chat.id) != CHAT_ID:
        await query.answer()
        await query.edit_message_text(f"Курс привязан к группе {TELEGRAM_GROUP_USERNAME}")
        return

    if data == "start_course":
        if progress_manager.is_rate_limited(user_id, "lesson"):
            await query.answer("Слишком часто — подожди минуту.", show_alert=True)
            return
        # первый урок или следующий, если нет активного
        active = progress_manager.get_active_lesson_id(user_id)
        if active:
            await query.answer("У тебя уже открыт урок — загляни в личку боту.", show_alert=True)
            return
        ok, err = await deliver_next_lesson(user_id, name)
        if ok:
            await query.answer("Урок отправлен в личку!")
        else:
            await query.answer(err[:180], show_alert=True)
        return

    if data.startswith("check_theory_"):
        try:
            idx = int(data.split("_")[2])
        except (IndexError, ValueError):
            idx = 0
        lid = lesson_id_for_scheduler_index(idx)
        ok = await send_micro_quiz(bot, user_id, lid, 0)
        if ok:
            await query.answer("Тест отправлен в личку!")
        else:
            await query.answer("Сначала /start боту в личке, затем снова нажми кнопку.", show_alert=True)
        return

    if data.startswith("next_lesson_"):
        await query.answer("Уроки в личке у бота — жми «Начать обучение».", show_alert=True)
        return

    await query.answer()


async def handle_course_mentor_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Одно сообщение пользователя пересылается ментору + мета; режим сбрасывается."""
    user_id = update.effective_user.id
    if not progress_manager.is_expecting_mentor(user_id):
        return
    lesson_id = progress_manager.get_expects_mentor_lesson_id(user_id) or "—"
    mentor_chat = get_mentor_forward_chat_id()
    msg = update.message
    if not msg:
        return

    uname = update.effective_user.username
    uname_s = f"@{uname}" if uname else "нет username"
    first = update.effective_user.first_name or "—"

    if not mentor_chat:
        progress_manager.clear_expects_mentor(user_id)
        await msg.reply_text(
            f"Пересылка к ментору не настроена на сервере. Напиши напрямую: {MENTOR_TG_URL}",
            reply_markup=build_lesson_keyboard(progress_manager.get_active_lesson_id(user_id) or lesson_id)
            if progress_manager.get_active_lesson_id(user_id)
            else None,
        )
        return

    try:
        await context.bot.forward_message(
            chat_id=mentor_chat,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
        )
        meta = (
            "📩 <b>Запрос с курса (бот)</b>\n"
            f"user_id: <code>{user_id}</code>\n"
            f"username: {html.escape(uname_s)}\n"
            f"имя: {html.escape(first)}\n"
            f"lesson_id: <code>{html.escape(str(lesson_id))}</code>"
        )
        await context.bot.send_message(chat_id=mentor_chat, text=meta, parse_mode="HTML")
    except TelegramError as e:
        logger.warning("handle_course_mentor_message: %s", e)
        await msg.reply_text(
            "Не удалось доставить ментору. Попробуй позже или напиши напрямую: " + MENTOR_TG_URL,
            reply_markup=build_lesson_keyboard(progress_manager.get_active_lesson_id(user_id) or lesson_id)
            if progress_manager.get_active_lesson_id(user_id)
            else None,
        )
        progress_manager.clear_expects_mentor(user_id)
        return

    progress_manager.clear_expects_mentor(user_id)
    active = progress_manager.get_active_lesson_id(user_id)
    kb = build_lesson_keyboard(active) if active else None
    await msg.reply_text(
        "✅ Отправил ментору. Обычно отвечают, когда освободятся.\n"
        "Пока можешь уточнить у ИИ в свободной форме — это не мешает.",
        reply_markup=kb,
    )


async def handle_course_code_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lesson_id = progress_manager.get_expected_code_lesson_id(user_id)
    if not lesson_id or lesson_id != progress_manager.get_active_lesson_id(user_id):
        return

    text = update.message.text or ""
    code = text
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()

    if len(code.strip()) < 10:
        await update.message.reply_text("Слишком мало кода — вставь разметку целиком.", reply_markup=build_lesson_keyboard(lesson_id))
        return

    from enhanced_ai_handler import enhanced_ai_handler

    L = get_lesson(lesson_id)
    review = await enhanced_ai_handler.review_submission(
        lesson_id,
        L["task"],
        list(L.get("checklist", [])),
        code,
    )
    status = review["status"]
    fb = review["feedback"]

    if status == "OK":
        progress_manager.clear_expects_code(user_id)
        await update.message.reply_text(
            f"✅ Зачёт.\n{fb}",
            reply_markup=build_lesson_keyboard(lesson_id),
        )
        await _finalize_lesson(user_id, _display_name(update.effective_user), lesson_id)
    else:
        # Режим «жду код» остаётся — можно сразу прислать правку без повторного нажатия кнопки.
        await update.message.reply_text(
            f"💬 Пока без зачёта — ничего страшного, так у всех.\n{fb}",
            reply_markup=build_lesson_keyboard(lesson_id),
        )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats = progress_manager.get_user_stats(user_id)
    active = stats.get("active_lesson_id") or "—"
    text = (
        f"📊 <b>Прогресс</b>\n"
        f"✅ Уроков закрыто: {stats['completed_count']} / {stats['total_lessons']} ({stats['percent']}%)\n"
        f"📌 Активный урок: <code>{active}</code>\n"
        f"📅 Старт: {stats['started_at'][:10]}\n\n"
        f"/next — следующий урок (если нет открытого)\n"
        f"/reset — сброс"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    progress_manager.reset_user_progress(update.effective_user.id)
    await update.message.reply_text("🔄 Прогресс сброшен. Начни с кнопки в группе или /next в личке.")


async def next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if progress_manager.is_rate_limited(user_id, "lesson"):
        await update.message.reply_text("⏰ Подожди минуту.")
        return
    name = _display_name(update.effective_user)
    ok, err = await deliver_next_lesson(user_id, name)
    if ok:
        await update.message.reply_text("✅ Урок отправлен выше ↑")
    else:
        await update.message.reply_text(err)


async def send_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_identity(update.effective_user.id, getattr(update.effective_user, "username", None)):
        await update.message.reply_text("Только для админа.")
        return
    if str(update.effective_chat.id) != CHAT_ID:
        await update.message.reply_text(f"Только в группе {TELEGRAM_GROUP_USERNAME}")
        return
    ok = await course_handler.send_welcome_message(str(update.effective_chat.id))
    await update.message.reply_text("✅ Отправлено" if ok else "❌ Ошибка")


async def groupstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_identity(update.effective_user.id, getattr(update.effective_user, "username", None)):
        await update.message.reply_text("Только для админа.")
        return
    gs = progress_manager.get_group_stats()
    tu = max(gs["total_users"], 1)
    text = (
        f"📊 <b>Статистика курса</b>\n"
        f"👥 Пользователей: {gs['total_users']}\n"
        f"🟢 Активных 7д: {gs['active_users']}\n"
        f"📚 Запросов уроков: {gs['total_lessons_requested']}\n"
        f"📈 В среднем: {gs['average_lessons_per_user']:.1f}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def send_welcome_to_group():
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("BOT_TOKEN или CHAT_ID не заданы")
        return False
    return await course_handler.send_welcome_message(CHAT_ID)


def setup_course_handlers(application: Application):
    application.add_handler(CommandHandler("course", course_start_command))
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("next", next_command))
    application.add_handler(CommandHandler("groupstats", groupstats_command))
    application.add_handler(CommandHandler("sendbutton", send_button_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    logger.info("Обработчики курса (ЛС + группа) настроены")
