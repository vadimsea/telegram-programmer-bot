"""
Курс: уроки в ЛС, короткий анонс в группу, прогресс в user_progress.
Inline-кнопки под уроком не удаляются — новые шаги идут новыми сообщениями.
"""

import html
import logging
import os
import re
from datetime import datetime
from typing import Literal, Optional

from dotenv import load_dotenv
from telegram import Bot, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatType
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram.error import BadRequest, TelegramError, Forbidden

from permissions import is_admin_identity
from curriculum import (
    LESSON_ORDER,
    get_lesson,
    lesson_id_for_scheduler_index,
    total_lessons,
)
from user_progress import get_lesson_cooldown_seconds, progress_manager

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

_CHAT_ID_RAW = os.getenv("CHAT_ID")


def _parse_course_group_chat_id(raw: Optional[str]) -> Optional[int]:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        logger.warning("CHAT_ID не является числом (%r) — задай id группы как -100…", raw)
        return None


# int для сравнения с update.effective_chat.id (обязательно для кнопок в группе)
COURSE_GROUP_CHAT_ID: Optional[int] = _parse_course_group_chat_id(_CHAT_ID_RAW)
# для send_message / pin (строка с числом)
CHAT_ID: Optional[str] = str(COURSE_GROUP_CHAT_ID) if COURSE_GROUP_CHAT_ID is not None else None

# Deep link для курса из группы: открывает ЛС с ботом и /start course (см. main.start)
_COURSE_START_PAYLOAD = "course"


async def resolve_bot_username(bot: Optional[Bot]) -> str:
    """username бота для t.me/... ссылки; get_me при необходимости."""
    if not bot:
        return (os.getenv("TELEGRAM_BOT_USERNAME") or os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
    u = (getattr(bot, "username", None) or "").strip()
    if u:
        return u
    try:
        me = await bot.get_me()
        return (me.username or "").strip()
    except TelegramError:
        pass
    return (os.getenv("TELEGRAM_BOT_USERNAME") or os.getenv("BOT_USERNAME") or "").strip().lstrip("@")


def bot_deeplink_course(username: str) -> str:
    un = (username or "").strip().lstrip("@")
    return f"https://t.me/{un}?start={_COURSE_START_PAYLOAD}"


def bot_deeplink_open_chat(username: str) -> str:
    """Просто открыть ЛС с ботом (без /start) — урок/квиз уже отправлены, помощник не дублирует курс."""
    un = (username or "").strip().lstrip("@")
    return f"https://t.me/{un}"


def is_course_target_group(chat_id: int) -> bool:
    return COURSE_GROUP_CHAT_ID is not None and int(chat_id) == COURSE_GROUP_CHAT_ID


async def _safe_callback_answer_url(query: CallbackQuery, url: str, *, fallback_alert: str) -> None:
    """answer(url=…) иногда отклоняется API — не оставляем крутилку без ответа."""
    try:
        await query.answer(url=url)
    except (BadRequest, TelegramError) as e:
        logger.warning("callback answer(url=%r…): %s", url[:40], e)
        try:
            await query.answer(fallback_alert[:190], show_alert=True)
        except TelegramError as e2:
            logger.warning("callback answer fallback: %s", e2)


# Доля верных ответов для зачёта квиза (соц. пост + переход к следующему уроку)
QUIZ_PASS_RATIO = 0.7

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
    """Основной путь — практика (код); квиз — быстрая проверка; «Я сделал» — fallback."""
    rows = [
        [
            InlineKeyboardButton("💬 Отправить код", callback_data=f"codehelp_{lesson_id}"),
            InlineKeyboardButton("✅ Я сделал", callback_data=f"hw_done_{lesson_id}"),
        ],
        [InlineKeyboardButton("⚡ Быстрый тест", callback_data=f"theoryquiz_{lesson_id}")],
        [InlineKeyboardButton("💡 Подсказка", callback_data=f"hint_{lesson_id}")],
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


def build_lesson_step1_keyboard(lesson_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📖 Теория и задание", callback_data=f"{LESSON_BODY_PREFIX}{lesson_id}")]]
    )


_lesson_keyboard = build_lesson_keyboard

# callback_data: quiz_{lesson_id}*{q_idx}*{choice} — разделитель только «*»
QUIZ_PREFIX = "quiz_"
THEORYQUIZ_PREFIX = "theoryquiz_"
LESSON_BODY_PREFIX = "lesson_body_"


def _quiz_callback_data(lesson_id: str, q_idx: int, choice: int) -> str:
    return f"{QUIZ_PREFIX}{lesson_id}*{q_idx}*{choice}"


def _parse_quiz_callback_data(data: str) -> Optional[tuple[str, int, int]]:
    """Разбор quiz_{lesson_id}*{q}*{choice}. lesson_id не содержит '*'."""
    if not data.startswith(QUIZ_PREFIX):
        return None
    rest = data[len(QUIZ_PREFIX) :]
    parts = rest.split("*")
    if len(parts) != 3:
        logger.warning("quiz parse: expected 3 segments, got %s parts, data=%r", len(parts), data)
        return None
    lid, q_s, c_s = parts[0], parts[1], parts[2]
    try:
        return lid, int(q_s), int(c_s)
    except ValueError:
        logger.warning("quiz parse: bad int in %r", data)
        return None


def _quiz_keyboard(lesson_id: str, q_idx: int) -> Optional[InlineKeyboardMarkup]:
    lesson = get_lesson(lesson_id)
    quiz_list = lesson.get("quiz") or []
    if q_idx < 0 or q_idx >= len(quiz_list):
        logger.warning("_quiz_keyboard: q_idx %s out of range for %s", q_idx, lesson_id)
        return None
    q = quiz_list[q_idx]
    opts = q.get("options") or []
    rows = []
    for i, label in enumerate(opts):
        cb = _quiz_callback_data(lesson_id, q_idx, i)
        if len(cb) > 64:
            logger.error("quiz callback too long (%s bytes): %s", len(cb), cb)
            continue
        rows.append([InlineKeyboardButton(str(label), callback_data=cb)])
    if not rows:
        logger.error("_quiz_keyboard: no rows for %s q=%s", lesson_id, q_idx)
    return InlineKeyboardMarkup(rows) if rows else None


def resolve_group_quiz_lesson(user_id: int) -> Optional[str]:
    """Урок для квиза из группы: активный или следующий по curriculum_cursor."""
    active = progress_manager.get_active_lesson_id(user_id)
    if active:
        return active
    total = total_lessons()
    if not progress_manager.can_open_next_lesson(user_id, total):
        return None
    cur = progress_manager.get_cursor(user_id)
    if cur < 0 or cur >= len(LESSON_ORDER):
        return None
    return LESSON_ORDER[cur]


async def _notify_quiz_resume_if_needed(bot, user_id: int, lesson_id: str) -> None:
    if not progress_manager.quiz_session_in_progress(user_id, lesson_id):
        return
    try:
        await bot.send_message(
            chat_id=user_id,
            text="Ты уже проходишь тест 👇",
            parse_mode="HTML",
        )
    except (Forbidden, TelegramError):
        pass


async def send_micro_quiz(bot, user_id: int, lesson_id: str, question_idx: int = 0) -> bool:
    """
    Одно сообщение с одним вопросом и 2–3 кнопками. Без хранения состояния.
    """
    print("send_micro_quiz step:", lesson_id, question_idx, flush=True)
    logger.info("send_micro_quiz: lesson_id=%s question_idx=%s", lesson_id, question_idx)

    try:
        lesson = get_lesson(lesson_id)
    except KeyError:
        logger.error("send_micro_quiz: lesson not found: %s", lesson_id)
        await bot.send_message(
            chat_id=user_id,
            text="Не нашёл урок для теста. Открой урок из группы или /next и снова нажми «⚡ Быстрый тест».",
        )
        return False

    quiz_list = lesson.get("quiz") or []
    if not quiz_list or question_idx >= len(quiz_list):
        await bot.send_message(
            chat_id=user_id,
            text="Для этого урока тест ещё не настроен — переходи к практике.",
        )
        return False

    # Запрос «вопрос 0» с группы/кнопки урока не должен сбрасывать уже идущий квиз — иначе снова 1/2.
    effective_idx = question_idx
    if question_idx == 0:
        resume_at = progress_manager.quiz_session_resume_next_index(user_id, lesson_id)
        if resume_at is not None:
            effective_idx = resume_at
        elif progress_manager.quiz_session_in_progress(user_id, lesson_id):
            effective_idx = 0
        else:
            progress_manager.quiz_session_start(user_id, lesson_id, len(quiz_list))

    q = quiz_list[effective_idx]
    kb = _quiz_keyboard(lesson_id, effective_idx)
    if not kb:
        logger.error("send_micro_quiz: keyboard is None for %s idx=%s", lesson_id, effective_idx)
        await bot.send_message(
            chat_id=user_id,
            text="Не удалось собрать кнопки теста (проверь длину callback). Напиши в группу.",
        )
        return False

    q_text = html.escape(str(q.get("q", "")), quote=False)
    lid_esc = html.escape(lesson_id, quote=False)
    text = (
        f"⚡ <b>Быстрый тест</b> ({effective_idx + 1}/{len(quiz_list)})\n"
        f"<code>{lid_esc}</code>\n\n"
        f"❓ {q_text}"
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
        logger.exception("send_micro_quiz: TelegramError")
        try:
            await bot.send_message(
                chat_id=user_id,
                text="Ошибка при отправке вопроса теста. Попробуй «⚡ Быстрый тест» ещё раз или /next.",
            )
        except TelegramError as e2:
            logger.warning("send_micro_quiz: fallback notify failed: %s", e2)
        return False


async def _handle_quiz_callback(query: CallbackQuery, bot: Bot, user_id: int, data: str, user: User) -> None:
    """Ответ в микро-квизе: считаем верные/всего, после последнего вопроса — 70% и соц. пост в группу."""
    try:
        await query.answer()
    except TelegramError as e:
        logger.warning("_handle_quiz_callback: query.answer failed: %s", e)

    parsed = _parse_quiz_callback_data(data)
    if not parsed:
        print("quiz step: parse FAILED", data, flush=True)
        logger.warning("quiz step: parse failed data=%r", data)
        if query.message:
            await query.message.reply_text("Кнопка теста устарела — нажми «⚡ Быстрый тест» снова.")
        return

    lid, qi, ci = parsed
    print("quiz step:", lid, qi, ci, flush=True)
    logger.info("quiz step: lesson_id=%s q_idx=%s choice=%s", lid, qi, ci)

    try:
        lesson = get_lesson(lid)
    except KeyError:
        logger.error("_handle_quiz_callback: unknown lesson %s", lid)
        if query.message:
            await query.message.reply_text("Урок не найден. Начни тест с кнопки урока.")
        return

    quiz_list = lesson.get("quiz") or []
    if qi < 0 or qi >= len(quiz_list):
        logger.warning("_handle_quiz_callback: bad q_idx %s for %s", qi, lid)
        if query.message:
            await query.message.reply_text("Этот вопрос уже неактуален — запусти «⚡ Быстрый тест» заново.")
        return

    q = quiz_list[qi]
    try:
        correct = int(q.get("correct", 0))
    except (TypeError, ValueError):
        logger.error("_handle_quiz_callback: bad correct in lesson %s q %s", lid, qi)
        if query.message:
            await query.message.reply_text("Ошибка настройки теста. Пропусти и займись практикой.")
        return

    if not query.message:
        logger.warning("_handle_quiz_callback: no message on query")
        return

    is_correct = ci == correct
    result = progress_manager.quiz_session_append_score(user_id, lid, qi, is_correct)
    if result == "mismatch":
        if qi == 0:
            progress_manager.quiz_session_start(user_id, lid, len(quiz_list))
            result = progress_manager.quiz_session_append_score(user_id, lid, qi, is_correct)
        if result == "mismatch":
            await query.message.reply_text("Тест сбился — нажми «⚡ Быстрый тест» с начала.")
            return

    display_name = _display_name(user)
    next_idx = qi + 1
    total_q = len(quiz_list)

    if result is None:
        if is_correct:
            await query.message.reply_text("✅ Верно!")
        else:
            hint = (q.get("wrong_hint") or "Загляни в теорию урока.").strip()
            if len(hint) > 180:
                hint = hint[:177] + "…"
            await query.message.reply_text(f"❌ Почти — {hint}")
        if next_idx < total_q:
            print("quiz step: next question", lid, next_idx, flush=True)
            logger.info("quiz step: sending next question %s idx=%s", lid, next_idx)
            ok = await send_micro_quiz(bot, user_id, lid, next_idx)
            if not ok:
                logger.error("send_micro_quiz failed %s -> idx %s", lid, next_idx)
                progress_manager.quiz_session_clear(user_id, lid)
                await query.message.reply_text(
                    "Не получилось отправить следующий вопрос. Нажми «⚡ Быстрый тест» ещё раз.",
                )
        return

    correct_n, total_n = result
    progress_manager.quiz_session_clear(user_id, lid)

    passed = total_n > 0 and (correct_n / total_n) >= QUIZ_PASS_RATIO
    print("quiz step: completed", lid, "correct", correct_n, "/", total_n, "passed", passed, flush=True)
    logger.info("quiz completed lesson=%s score=%s/%s passed=%s", lid, correct_n, total_n, passed)

    if passed:
        active = progress_manager.get_active_lesson_id(user_id)
        if active == lid:
            await _finalize_lesson(
                user_id,
                display_name,
                lid,
                announce_done=False,
                auto_open_next=True,
                from_user=user,
            )
        else:
            qdone = (lesson.get("quiz_done_line") or "").strip()
            if not qdone:
                qdone = "🎯 Тест сдан! Продолжай по активному уроку или открой нужный через /next."
            kb = build_lesson_keyboard(active) if active else build_lesson_keyboard(lid)
            await query.message.reply_text(qdone, reply_markup=kb)
    else:
        await announce_group_result(user, lid, "quiz_soft")
        await query.message.reply_text("Давай попробуем ещё раз 👇")
        progress_manager.quiz_session_start(user_id, lid, len(quiz_list))
        ok_retry = await send_micro_quiz(bot, user_id, lid, 0)
        if not ok_retry:
            progress_manager.quiz_session_clear(user_id, lid)
            await query.message.reply_text(
                "Не вышло запустить тест снова. Нажми «⚡ Быстрый тест» на уроке.",
            )


class CourseHandler:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

    def _lesson_message_part1(self, lesson_id: str) -> str:
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
        return (
            "\n\n".join(blocks)
            + "\n\n👆 <b>Шаг 1.</b> Разберись с вопросом и тезисом выше.\n"
            "👇 <b>Шаг 2.</b> Нажми кнопку — пришлю теорию и задание."
        )

    def _lesson_message_part2(self, lesson_id: str) -> str:
        L = get_lesson(lesson_id)
        body = (
            f"📖 <b>Теория</b>\n{L['theory']}\n\n"
            f"⚡ <b>Нюанс</b>\n{L['nuance']}\n\n"
            f"🛠 <b>Задание</b>\n{L['task']}\n\n"
            "Снизу: <b>практика</b> (код) и быстрый тест; «✅ Я сделал» — если уже готово."
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
            text = self._lesson_message_part1(lesson_id)
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=build_lesson_step1_keyboard(lesson_id),
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
                f"🔥 {safe} начал(а) урок: <b>{html.escape(L['title'])}</b>.\n"
                f"Кто ещё в деле — жми «Начать или продолжить» в закрепе."
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
                "Уроки приходят <b>в личку боту</b>. Если бот ещё не открыт — сначала жми <b>«Открыть бота»</b>, "
                "в ЛС нажми Start — урок придёт сам. Потом всё можно продолжать кнопкой «Начать или продолжить».\n\n"
                "📊 /progress — прогресс (в группе или в ЛС)\n"
                "📖 /next — следующий урок (когда предыдущий закрыт)\n\n"
                "<b>Начнём?</b>"
            )
            rows = []
            un_w = await resolve_bot_username(self.bot)
            if un_w:
                rows.append(
                    [InlineKeyboardButton("💬 Открыть бота (урок в личке)", url=bot_deeplink_course(un_w))]
                )
            rows.append([InlineKeyboardButton("▶️ Начать или продолжить", callback_data="start_course")])
            rows.append(
                [
                    InlineKeyboardButton("👤 Написать ментору", url=MENTOR_TG_URL),
                    InlineKeyboardButton("🌐 Сайт ментора", url=MENTOR_SITE_URL),
                ]
            )
            keyboard = InlineKeyboardMarkup(rows)
            message = await self.bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            try:
                await self.bot.pin_chat_message(chat_id=chat_id, message_id=message.message_id)
            except TelegramError as e:
                logger.warning("pin_chat_message: %s", e)
            return True
        except Exception as e:
            logger.error("send_welcome_message: %s", e)
            return False


course_handler = CourseHandler()


def format_social_name(user: User) -> str:
    """Имя для поста в группу: @username или имя."""
    un = getattr(user, "username", None)
    if un and str(un).strip():
        return f"@{html.escape(str(un).strip())}"
    fn = getattr(user, "first_name", None)
    if fn and str(fn).strip():
        return html.escape(str(fn).strip())
    return "Участник"


def _quiz_group_context(lesson_id: str) -> tuple[str, str, str]:
    """title_html, badge_html (или ''), lid_esc для поста в группу."""
    try:
        L = get_lesson(lesson_id)
    except KeyError:
        return html.escape(lesson_id), "", html.escape(lesson_id)
    title = html.escape(str(L.get("title", lesson_id)))
    badge_raw = (L.get("progress_badge") or "").strip()
    badge_html = f"<b>{html.escape(badge_raw)}</b>" if badge_raw else ""
    lid_esc = html.escape(lesson_id)
    return title, badge_html, lid_esc


async def announce_group_result(
    user: User,
    lesson_id: str,
    outcome: Literal["lesson_closed", "quiz_soft"],
) -> None:
    """
    Один пост в группу по итогу квиза.
    lesson_closed — только после реального _finalize_lesson (урок закрыт).
    quiz_soft — мягкий текст, урок ещё не закрыт (набрал < 70%).
    """
    if not course_handler.bot or not CHAT_ID:
        logger.warning("announce_group_result: пропуск — нет бота или CHAT_ID")
        return
    name = format_social_name(user)
    title_html, badge_html, lid_esc = _quiz_group_context(lesson_id)
    if outcome == "lesson_closed":
        progress_line = (
            f"📍 {badge_html} · <i>{title_html}</i> 🚀"
            if badge_html
            else f"📌 <i>{title_html}</i> 🚀"
        )
        text = (
            f"🔥 {name} закрыл(а) урок <code>{lid_esc}</code> 💪\n"
            f"{progress_line}\n\n"
            f"Ещё один шаг к фронтенду 💻"
        )
    else:
        if not progress_manager.should_post_quiz_soft_to_group(user.id, lesson_id):
            return
        progress_line = (
            f"📍 {badge_html} · <i>{title_html}</i>"
            if badge_html
            else f"📌 <i>{title_html}</i>"
        )
        text = (
            f"😅 {name} почти закрыл(а) <code>{lid_esc}</code> 🤏\n"
            f"{progress_line}\n\n"
            f"ещё чуть-чуть — и получится ✨"
        )
    try:
        await course_handler.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.warning("announce_group_result: %s", e)


async def announce_group_merged_close_next(user: User, closed_id: str, opened_id: str) -> None:
    """Один пост в группу: закрыл урок + открыл следующий (без дубля «opened»)."""
    if not course_handler.bot or not CHAT_ID:
        return
    name = format_social_name(user)
    ct, cb, ce = _quiz_group_context(closed_id)
    ot, ob, oe = _quiz_group_context(opened_id)
    progress_closed = f"📍 {cb} · <i>{ct}</i> 💪" if cb else f"📌 <i>{ct}</i> 💪"
    progress_open = f"📍 {ob} · <i>{ot}</i>" if ob else f"📌 <i>{ot}</i>"
    text = (
        f"🔥 {name} закрыл(а) урок <code>{ce}</code>\n"
        f"{progress_closed}\n\n"
        f"📖 Уже взял(а) следующий: <code>{oe}</code>\n"
        f"{progress_open}\n\n"
        f"Ещё один шаг к фронтенду 💻 🚀"
    )
    try:
        await course_handler.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
    except TelegramError as e:
        logger.warning("announce_group_merged_close_next: %s", e)


def _display_name(user) -> str:
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return "Участник"


async def _answer_open_bot_from_group(query: CallbackQuery, bot: Bot) -> None:
    """Если пользователь не нажал Start у бота — открываем t.me/...?start=course (без запутывания текстом)."""
    un = await resolve_bot_username(bot)
    if un:
        link = bot_deeplink_course(un)
        await _safe_callback_answer_url(
            query,
            link,
            fallback_alert=f"Открой бота вручную: {link}",
        )
        return
    await query.answer(
        "Найди бота «Помощник Программиста» в Telegram и нажми «Запустить», затем снова эту кнопку.",
        show_alert=True,
    )


async def _answer_jump_to_private_bot(query: CallbackQuery, bot: Bot) -> None:
    """После успешной отправки в ЛС — сразу перекинуть в чат с ботом (без ?start=, чтобы не дергать /start course)."""
    un = await resolve_bot_username(bot)
    if un:
        link = bot_deeplink_open_chat(un)
        await _safe_callback_answer_url(
            query,
            link,
            fallback_alert=f"Урок в личке. Открой бота: {link}",
        )
        return
    try:
        await query.answer("Смотри личку с ботом 👆")
    except TelegramError as e:
        logger.warning("_answer_jump_to_private_bot: %s", e)


async def _open_lesson_for_user(
    user_id: int,
    display_name: str,
    lesson_id: str,
    *,
    announce_opened: bool = True,
) -> tuple[bool, str]:
    progress_manager.set_active_lesson(user_id, lesson_id)
    ok = await course_handler.send_lesson_dm(user_id, lesson_id)
    if not ok:
        return False, "Сначала открой чат с ботом (кнопка «Открыть бота» в закрепе или ссылка после кнопки в группе)."
    if announce_opened:
        await course_handler.announce_group(display_name, lesson_id, "opened")
    return True, ""


async def try_deliver_course_to_private(user_id: int, display_name: str) -> tuple[bool, str]:
    """
    Одна точка входа: как «Начать или продолжить» из группы.
    Возвращает (True, '') или (False, код/текст): 'rate', 'forbidden', либо текст ошибки deliver_next_lesson.
    """
    if progress_manager.is_lesson_request_cooldown(user_id):
        return False, "rate"
    active = progress_manager.get_active_lesson_id(user_id)
    if active:
        ok = await course_handler.send_lesson_dm(user_id, active)
        if ok:
            progress_manager.mark_lesson_request_done(user_id)
            return True, ""
        return False, "forbidden"
    ok, err = await deliver_next_lesson(user_id, display_name)
    if ok:
        progress_manager.mark_lesson_request_done(user_id)
        return True, ""
    err_l = (err or "").lower()
    if "открой" in err_l and "бот" in err_l:
        return False, "forbidden"
    return False, err or "error"


async def deliver_next_lesson(
    user_id: int,
    display_name: str,
    *,
    skip_group_open: bool = False,
) -> tuple[bool, str]:
    total = total_lessons()
    if not progress_manager.can_open_next_lesson(user_id, total):
        active = progress_manager.get_active_lesson_id(user_id)
        if active:
            return False, "Сначала закрой текущий урок: «✅ Я сделал» или пришли код на проверку."
        return False, "Ты уже прошёл все уроки этого блока 🎉"
    cur = progress_manager.get_cursor(user_id)
    lesson_id = LESSON_ORDER[cur]
    ok, err = await _open_lesson_for_user(
        user_id,
        display_name,
        lesson_id,
        announce_opened=not skip_group_open,
    )
    return ok, err


async def _finalize_lesson(
    user_id: int,
    display_name: str,
    lesson_id: str,
    *,
    announce_done: bool = True,
    auto_open_next: bool = False,
    from_user: Optional[User] = None,
) -> bool:
    data = progress_manager.get_user_progress(user_id)
    done = list(data.get("completed_lesson_ids") or [])
    if lesson_id in done:
        if course_handler.bot:
            try:
                await course_handler.bot.send_message(
                    chat_id=user_id,
                    text="✅ Этот урок уже засчитан.",
                )
            except TelegramError as e:
                logger.warning("_finalize_lesson already-done DM: %s", e)
        return False

    if not progress_manager.complete_lesson(user_id, lesson_id):
        logger.warning(
            "_finalize_lesson: complete_lesson failed user=%s lesson=%s active=%s",
            user_id,
            lesson_id,
            data.get("active_lesson_id"),
        )
        return False

    if announce_done:
        await course_handler.announce_group(display_name, lesson_id, "done")
    if not course_handler.bot:
        return True

    win = get_lesson(lesson_id).get("win_message", "").strip()
    if win:
        try:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text=win,
                parse_mode="HTML",
            )
        except TelegramError as e:
            logger.warning("_finalize_lesson win_message: %s", e)
    done_n = len(progress_manager.get_user_progress(user_id).get("completed_lesson_ids") or [])
    if done_n == 3:
        try:
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
        except TelegramError as e:
            logger.warning("_finalize_lesson milestone 3: %s", e)
    if done_n == 5:
        try:
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
        except TelegramError as e:
            logger.warning("_finalize_lesson milestone 5: %s", e)
    total = total_lessons()
    can_next = progress_manager.can_open_next_lesson(user_id, total)
    if auto_open_next and can_next:
        if from_user is not None:
            ok, err = await deliver_next_lesson(user_id, display_name, skip_group_open=True)
            if ok:
                opened = progress_manager.get_active_lesson_id(user_id)
                if opened and CHAT_ID:
                    await announce_group_merged_close_next(from_user, lesson_id, opened)
            else:
                try:
                    await course_handler.bot.send_message(chat_id=user_id, text=err)
                except TelegramError as e:
                    logger.warning("_finalize_lesson deliver err DM: %s", e)
                if CHAT_ID:
                    await announce_group_result(from_user, lesson_id, "lesson_closed")
        else:
            ok, err = await deliver_next_lesson(user_id, display_name)
            if not ok:
                try:
                    await course_handler.bot.send_message(chat_id=user_id, text=err)
                except TelegramError as e:
                    logger.warning("_finalize_lesson deliver err DM: %s", e)
    elif from_user is not None and not announce_done and not can_next:
        if CHAT_ID:
            await announce_group_result(from_user, lesson_id, "lesson_closed")
        try:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text="🏁 Этот блок завершён. Скоро добавим новые уроки — следи за группой.",
                parse_mode="HTML",
            )
        except TelegramError as e:
            logger.warning("_finalize_lesson block end: %s", e)
    elif can_next:
        try:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text="🎉 Урок засчитан. Готов к следующему?",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Следующий урок", callback_data="cnext")]]),
                parse_mode="HTML",
            )
        except TelegramError as e:
            logger.warning("_finalize_lesson cnext prompt: %s", e)
    else:
        try:
            await course_handler.bot.send_message(
                chat_id=user_id,
                text="🏁 Этот блок завершён. Скоро добавим новые уроки — следи за группой.",
                parse_mode="HTML",
            )
        except TelegramError as e:
            logger.warning("_finalize_lesson block end: %s", e)
    return True


async def course_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if COURSE_GROUP_CHAT_ID is None:
        await update.message.reply_text("На сервере не задан CHAT_ID группы курса.")
        return
    if not is_course_target_group(update.effective_chat.id):
        await update.message.reply_text(f"Команда только в группе {TELEGRAM_GROUP_USERNAME}")
        return
    success = await course_handler.send_welcome_message(str(update.effective_chat.id))
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
        if data.startswith(QUIZ_PREFIX):
            await _handle_quiz_callback(query, bot, user_id, data, user)
            return

        try:
            await query.answer()
        except TelegramError as e:
            logger.warning("private callback query.answer: %s", e)

        if data == "cnext":
            if progress_manager.is_lesson_request_cooldown(user_id):
                sec = get_lesson_cooldown_seconds()
                await query.message.reply_text(f"⏰ Подожди ~{sec} сек. между запросами урока (защита от двойного нажатия).")
                return
            ok, err = await deliver_next_lesson(user_id, name)
            if ok:
                progress_manager.mark_lesson_request_done(user_id)
            else:
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

        if data.startswith(LESSON_BODY_PREFIX):
            lesson_id = data[len(LESSON_BODY_PREFIX) :]
            if lesson_id != progress_manager.get_active_lesson_id(user_id):
                await query.message.reply_text(
                    "Это не активный урок. Открой актуальный через группу «Начать или продолжить» или /next."
                )
                return
            try:
                body = course_handler._lesson_message_part2(lesson_id)
            except KeyError:
                await query.message.reply_text("Урок не найден в каталоге.")
                return
            await query.message.reply_text(
                body,
                reply_markup=build_lesson_keyboard(lesson_id),
                parse_mode="HTML",
            )
            return

        if data.startswith(THEORYQUIZ_PREFIX):
            lesson_id = data[len(THEORYQUIZ_PREFIX) :]
            print("theoryquiz start:", lesson_id, flush=True)
            logger.info("theoryquiz: lesson_id=%s", lesson_id)
            await _notify_quiz_resume_if_needed(bot, user_id, lesson_id)
            await send_micro_quiz(bot, user_id, lesson_id, 0)
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
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        if COURSE_GROUP_CHAT_ID is None:
            logger.error(
                "course callback в группе chat_id=%s, но CHAT_ID в окружении не задан — кнопки курса отключены",
                chat.id,
            )
            try:
                await query.answer(
                    "Курс на сервере не привязан к группе (нет CHAT_ID). Обратись к администратору.",
                    show_alert=True,
                )
            except TelegramError as e:
                logger.warning("query.answer (no CHAT_ID): %s", e)
            return
        if not is_course_target_group(chat.id):
            logger.info(
                "course callback из другой группы: chat_id=%s ожидали %s",
                chat.id,
                COURSE_GROUP_CHAT_ID,
            )
            try:
                await query.answer()
            except TelegramError:
                pass
            try:
                await query.edit_message_text(f"Курс привязан к группе {TELEGRAM_GROUP_USERNAME}")
            except TelegramError as e:
                logger.warning("edit_message wrong group: %s", e)
            return

    if data == "start_course":
        try:
            logger.info("start_course: user_id=%s chat_id=%s", user_id, getattr(chat, "id", None))
            ok, hint = await try_deliver_course_to_private(user_id, name)
            if ok:
                await _answer_jump_to_private_bot(query, bot)
                return
            if hint == "rate":
                sec = get_lesson_cooldown_seconds()
                await query.answer(f"Слишком часто — подожди ~{sec} сек.", show_alert=True)
                return
            if hint == "forbidden":
                await _answer_open_bot_from_group(query, bot)
                return
            await query.answer(hint[:200], show_alert=True)
        except Exception as e:
            logger.exception("start_course: непойманная ошибка: %s", e)
            try:
                await query.answer("Сервис временно недоступен. Попробуй через минуту.", show_alert=True)
            except TelegramError as te:
                logger.warning("start_course error answer: %s", te)
        return

    if data == "check_theory" or data.startswith("check_theory_"):
        try:
            logger.info("check_theory: user_id=%s chat_id=%s data=%r", user_id, getattr(chat, "id", None), data)
            if data == "check_theory":
                lid = resolve_group_quiz_lesson(user_id)
            else:
                try:
                    idx = int(data.rsplit("_", 1)[-1])
                except ValueError:
                    idx = 0
                lid = lesson_id_for_scheduler_index(idx)
            if not lid:
                await query.answer(
                    "Ты уже прошёл этот блок или нет шага для теста. Жми «Начать или продолжить».",
                    show_alert=True,
                )
                return
            await _notify_quiz_resume_if_needed(bot, user_id, lid)
            ok = await send_micro_quiz(bot, user_id, lid, 0)
            if ok:
                await _answer_jump_to_private_bot(query, bot)
            else:
                await _answer_open_bot_from_group(query, bot)
        except Exception as e:
            logger.exception("check_theory: ошибка: %s", e)
            try:
                await query.answer("Не удалось отправить тест. Попробуй позже.", show_alert=True)
            except TelegramError as te:
                logger.warning("check_theory answer: %s", te)
        return

    if data.startswith("next_lesson_"):
        await _answer_jump_to_private_bot(query, bot)
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
    if progress_manager.is_lesson_request_cooldown(user_id):
        sec = get_lesson_cooldown_seconds()
        await update.message.reply_text(f"⏰ Подожди ~{sec} сек. между запросами урока.")
        return
    name = _display_name(update.effective_user)
    ok, err = await deliver_next_lesson(user_id, name)
    if ok:
        progress_manager.mark_lesson_request_done(user_id)
        await update.message.reply_text("✅ Урок отправлен выше ↑")
    else:
        await update.message.reply_text(err)


async def send_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin_identity(update.effective_user.id, getattr(update.effective_user, "username", None)):
        await update.message.reply_text("Только для админа.")
        return
    if COURSE_GROUP_CHAT_ID is None or not is_course_target_group(update.effective_chat.id):
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
    if COURSE_GROUP_CHAT_ID is None:
        logger.error(
            "CHAT_ID не задан или невалиден — кнопки «Начать или продолжить» в группе не работают. "
            "Укажи в Render переменную CHAT_ID = id группы (число -100…)."
        )
    else:
        logger.info("Курс: ожидаемая группа chat_id=%s", COURSE_GROUP_CHAT_ID)
    logger.info("Обработчики курса (ЛС + группа) настроены")
