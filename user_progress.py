"""
Прогресс курса: cursor + active_lesson_id + completed_lesson_ids.
Совместимость: старые поля current_lesson / completed_lessons мигрируют при чтении.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional, Any, Tuple, Union
from threading import RLock

logger = logging.getLogger(__name__)


def _lesson_cooldown_seconds() -> int:
    raw = (os.getenv("LESSON_COOLDOWN_SECONDS") or "20").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 20
    return max(5, min(n, 120))


def get_lesson_cooldown_seconds() -> int:
    """Пауза между успешными выдачами урока (сек.), для текстов и env LESSON_COOLDOWN_SECONDS."""
    return _lesson_cooldown_seconds()


class UserProgressManager:
    def __init__(self, progress_file: str = "user_progress.json"):
        self.progress_file = progress_file
        self.progress_data = self.load_progress()
        # re-entrant lock: get_user_progress() может вызывать save_progress() в том же потоке
        self.lock = RLock()
        self.last_activity = {}
        self.rate_limit = {}
        # Микро-квиз без БД: счёт ответов до завершения (ключ "user_id:lesson_id")
        self._quiz_sessions: Dict[str, Dict[str, Any]] = {}
        # re-entrant, чтобы исключить блокировки при вложенных вызовах квиз-сессий
        self._quiz_lock = RLock()
        # Анти-спам quiz_soft в группу: последний пост по user_id:lesson_id
        self._quiz_soft_group_last: Dict[str, datetime] = {}

    def load_progress(self) -> Dict:
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                    if not raw:
                        return {}
                    return json.loads(raw)
        except Exception as e:
            logger.error(f"Ошибка загрузки прогресса: {e}")
        return {}

    def save_progress(self) -> None:
        try:
            with self.lock:
                with open(self.progress_file, "w", encoding="utf-8") as f:
                    json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")

    def _migrate_record(self, uid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if "curriculum_cursor" in data and "completed_lesson_ids" in data:
            if "expects_mentor_for" not in data:
                data["expects_mentor_for"] = None
                self.progress_data[uid] = data
                self.save_progress()
            return data
        old_idx = int(data.get("current_lesson", 0) or 0)
        old_done = data.get("completed_lessons") or []
        data["curriculum_cursor"] = old_idx
        data["completed_lesson_ids"] = []
        data["active_lesson_id"] = None
        data["expects_code_for"] = None
        data["expects_mentor_for"] = None
        data["total_lessons_requested"] = data.get("total_lessons_requested", 0)
        if old_done:
            data["curriculum_cursor"] = max(old_idx, len(old_done))
        self.progress_data[uid] = data
        self.save_progress()
        return data

    def get_user_progress(self, user_id: int) -> Dict[str, Any]:
        with self.lock:
            key = str(user_id)
            if key not in self.progress_data:
                now = datetime.now().isoformat()
                self.progress_data[key] = {
                    "curriculum_cursor": 0,
                    "completed_lesson_ids": [],
                    "active_lesson_id": None,
                    "expects_code_for": None,
                    "expects_mentor_for": None,
                    "started_at": now,
                    "last_activity": now,
                    "total_lessons_requested": 0,
                    "last_lesson_time": None,
                }
                self.save_progress()
            return self._migrate_record(key, self.progress_data[key])

    def is_lesson_request_cooldown(self, user_id: int) -> bool:
        """
        Анти-дребезг только после успешной выдачи урока (см. mark_lesson_request_done).
        Не ставит метку на «провале» — можно сразу повторить после открытия бота / исправления ошибки.
        """
        k = f"{user_id}_lesson"
        last = self.rate_limit.get(k)
        if last is None:
            return False
        return datetime.now() - last < timedelta(seconds=_lesson_cooldown_seconds())

    def mark_lesson_request_done(self, user_id: int) -> None:
        """Вызов после успешной отправки урока в ЛС (новый урок или повтор текущего)."""
        self.rate_limit[f"{user_id}_lesson"] = datetime.now()

    def is_rate_limited(self, user_id: int, action: str = "command") -> bool:
        now = datetime.now()
        k = f"{user_id}_{action}"
        if k not in self.rate_limit:
            self.rate_limit[k] = now
            return False
        if action == "command":
            if now - self.rate_limit[k] < timedelta(seconds=5):
                return True
        self.rate_limit[k] = now
        return False

    def get_active_lesson_id(self, user_id: int) -> Optional[str]:
        return self.get_user_progress(user_id).get("active_lesson_id")

    def update_user_identity(
        self,
        user_id: int,
        display_name: Optional[str] = None,
        username: Optional[str] = None,
    ) -> None:
        """Сохранить имя и @username при каждом взаимодействии — нужно для напоминаний."""
        data = self.get_user_progress(user_id)
        changed = False
        if display_name:
            data["display_name"] = display_name
            changed = True
        if username:
            data["username"] = username
            changed = True
        if changed:
            self.save_progress()

    def set_active_lesson(self, user_id: int, lesson_id: str) -> None:
        data = self.get_user_progress(user_id)
        data["active_lesson_id"] = lesson_id
        data["expects_code_for"] = None
        data["expects_mentor_for"] = None
        data["last_activity"] = datetime.now().isoformat()
        data["total_lessons_requested"] = data.get("total_lessons_requested", 0) + 1
        data["last_lesson_time"] = data["last_activity"]
        self.save_progress()

    def set_expects_code(self, user_id: int, lesson_id: str) -> None:
        data = self.get_user_progress(user_id)
        data["expects_code_for"] = lesson_id
        data["expects_mentor_for"] = None
        data["last_activity"] = datetime.now().isoformat()
        self.save_progress()

    def clear_expects_code(self, user_id: int) -> None:
        data = self.get_user_progress(user_id)
        data["expects_code_for"] = None
        self.save_progress()

    def set_expects_mentor(self, user_id: int, lesson_id: str) -> None:
        data = self.get_user_progress(user_id)
        data["expects_mentor_for"] = lesson_id
        data["expects_code_for"] = None
        data["last_activity"] = datetime.now().isoformat()
        self.save_progress()

    def clear_expects_mentor(self, user_id: int) -> None:
        data = self.get_user_progress(user_id)
        data["expects_mentor_for"] = None
        self.save_progress()

    def is_expecting_mentor(self, user_id: int) -> bool:
        return bool(self.get_user_progress(user_id).get("expects_mentor_for"))

    def get_expects_mentor_lesson_id(self, user_id: int) -> Optional[str]:
        return self.get_user_progress(user_id).get("expects_mentor_for")

    def is_expecting_code(self, user_id: int) -> bool:
        return bool(self.get_user_progress(user_id).get("expects_code_for"))

    def get_expected_code_lesson_id(self, user_id: int) -> Optional[str]:
        return self.get_user_progress(user_id).get("expects_code_for")

    def can_open_next_lesson(self, user_id: int, total: int) -> bool:
        """Можно выдать новый урок (нет незакрытого active)."""
        data = self.get_user_progress(user_id)
        return data.get("active_lesson_id") is None and data["curriculum_cursor"] < total

    def can_go_next(self, user_id: int, total: int) -> bool:
        """Синоним: есть слот для следующего урока и нет активного ДЗ."""
        return self.can_open_next_lesson(user_id, total)

    def complete_lesson(self, user_id: int, lesson_id: str) -> bool:
        """
        Закрыть урок: только если lesson_id совпадает с active.
        Увеличивает cursor, снимает active. Обновляет streak.
        """
        data = self.get_user_progress(user_id)
        active = data.get("active_lesson_id")
        if active != lesson_id:
            return False
        done: List[str] = list(data.get("completed_lesson_ids") or [])
        if lesson_id not in done:
            done.append(lesson_id)
        data["completed_lesson_ids"] = done
        data["curriculum_cursor"] = int(data.get("curriculum_cursor", 0)) + 1
        data["active_lesson_id"] = None
        data["expects_code_for"] = None
        data["expects_mentor_for"] = None
        data["last_activity"] = datetime.now().isoformat()
        self._update_streak(data)
        self.save_progress()
        return True

    def _update_streak(self, data: Dict[str, Any]) -> None:
        """Обновить streak_days на основе даты последнего завершённого урока."""
        today = datetime.now().date()
        today_str = today.isoformat()
        last_str = data.get("last_completed_date")
        streak = int(data.get("streak_days", 0))

        if last_str == today_str:
            # Уже засчитан сегодня — не изменяем
            pass
        elif last_str == (today - timedelta(days=1)).isoformat():
            # Вчера был урок — продолжаем серию
            streak += 1
        else:
            # Пропуск или первый раз — сбрасываем
            streak = 1

        data["streak_days"] = streak
        data["last_completed_date"] = today_str
        data["streak_updated_at"] = datetime.now().isoformat()

    def get_streak(self, user_id: int) -> int:
        """Текущий стрик пользователя в днях."""
        data = self.get_user_progress(user_id)
        # Если последний урок был давно — стрик сброшен
        last_str = data.get("last_completed_date")
        if not last_str:
            return 0
        try:
            last_date = datetime.fromisoformat(last_str).date()
        except (ValueError, TypeError):
            return 0
        today = datetime.now().date()
        if (today - last_date).days > 1:
            return 0
        return int(data.get("streak_days", 0))

    def is_streak_milestone(self, streak: int) -> Optional[str]:
        """Вернуть уровень стрика если это веха, иначе None."""
        if streak == 3:
            return "fire"
        if streak == 7:
            return "week"
        if streak == 14:
            return "twoweeks"
        if streak == 21:
            return "threeweeks"
        if streak == 30:
            return "month"
        if streak > 30 and streak % 10 == 0:
            return "epic"
        return None

    def set_pending_homework(self, user_id: int, lesson_id: str) -> None:
        """Явно назначить активный урок (уже открыт) — для согласованности API."""
        self.set_active_lesson(user_id, lesson_id)

    def get_cursor(self, user_id: int) -> int:
        return int(self.get_user_progress(user_id).get("curriculum_cursor", 0))

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        data = self.get_user_progress(user_id)
        from curriculum import LESSON_ORDER, total_lessons

        total = total_lessons()
        done_n = len(data.get("completed_lesson_ids") or [])
        cur = int(data.get("curriculum_cursor", 0))
        active = data.get("active_lesson_id")
        pct = int(round(100 * done_n / total)) if total else 0
        return {
            "completed_count": done_n,
            "total_lessons": total,
            "percent": pct,
            "cursor": cur,
            "active_lesson_id": active,
            "started_at": data.get("started_at", ""),
            "last_activity": data.get("last_activity", ""),
            "total_lessons_requested": data.get("total_lessons_requested", 0),
            "last_lesson_time": data.get("last_lesson_time"),
        }

    def reset_user_progress(self, user_id: int) -> None:
        with self.lock:
            now = datetime.now().isoformat()
            self.progress_data[str(user_id)] = {
                "curriculum_cursor": 0,
                "completed_lesson_ids": [],
                "active_lesson_id": None,
                "expects_code_for": None,
                "expects_mentor_for": None,
                "started_at": now,
                "last_activity": now,
                "total_lessons_requested": 0,
                "last_lesson_time": None,
            }
            self.save_progress()

    def get_inactive_users(self, inactive_days: int = 3) -> List[Dict]:
        """
        Вернуть пользователей, которые:
        - были активны хотя бы раз (есть started_at)
        - не завершили курс
        - не выходили в бот больше inactive_days дней
        - последнее напоминание было >inactive_days дней назад (или не было)
        """
        cutoff = datetime.now() - timedelta(days=inactive_days)
        results = []
        for uid, data in self.progress_data.items():
            # Пропускаем тех, кто прошёл весь курс
            from curriculum import total_lessons as _total
            total = _total()
            done_n = len(data.get("completed_lesson_ids") or [])
            if done_n >= total:
                continue
            # Проверяем последнюю активность
            last_str = data.get("last_activity")
            if not last_str:
                continue
            try:
                last_dt = datetime.fromisoformat(last_str)
            except (ValueError, TypeError):
                continue
            if last_dt >= cutoff:
                continue  # ещё активен
            # Проверяем: не слали напоминание недавно
            last_remind_str = data.get("last_reminder_at")
            if last_remind_str:
                try:
                    last_remind_dt = datetime.fromisoformat(last_remind_str)
                    if last_remind_dt >= cutoff:
                        continue  # уже напомнили недавно
                except (ValueError, TypeError):
                    pass
            results.append({
                "user_id": int(uid),
                "display_name": data.get("display_name", ""),
                "username": data.get("username", ""),
                "last_activity": last_dt,
                "inactive_days": (datetime.now() - last_dt).days,
                "completed_count": done_n,
                "total_lessons": total,
                "active_lesson_id": data.get("active_lesson_id"),
                "cursor": int(data.get("curriculum_cursor", 0)),
            })
        return results

    def mark_reminder_sent(self, user_id: int) -> None:
        """Отметить что напоминание отправлено — предотвращает спам."""
        data = self.get_user_progress(user_id)
        data["last_reminder_at"] = datetime.now().isoformat()
        self.save_progress()

    def get_all_users(self) -> List[Dict]:
        users = []
        for uid, data in self.progress_data.items():
            users.append(
                {
                    "user_id": int(uid),
                    "curriculum_cursor": data.get("curriculum_cursor", 0),
                    "completed_count": len(data.get("completed_lesson_ids") or []),
                    "started_at": data.get("started_at"),
                    "last_activity": data.get("last_activity"),
                    "total_lessons_requested": data.get("total_lessons_requested", 0),
                }
            )
        return users

    def get_group_stats(self) -> Dict:
        total_users = len(self.progress_data)
        active_users = 0
        total_lessons = 0
        for _, data in self.progress_data.items():
            total_lessons += int(data.get("total_lessons_requested", 0) or 0)
            try:
                last_activity = datetime.fromisoformat(data["last_activity"])
                if datetime.now() - last_activity < timedelta(days=7):
                    active_users += 1
            except (ValueError, KeyError, TypeError):
                pass
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_lessons_requested": total_lessons,
            "average_lessons_per_user": total_lessons / total_users if total_users > 0 else 0,
        }

    # --- Обратная совместимость для старого course_handler API ---
    def update_user_progress(self, user_id: int, lesson_index: int, completed: bool = False) -> None:
        """Устаревший вызов: не используется в новом потоке курса."""
        data = self.get_user_progress(user_id)
        data["last_activity"] = datetime.now().isoformat()
        self.save_progress()

    def get_next_lesson(self, user_id: int) -> int:
        """Устаревший: возвращает cursor как int для совместимости тестов."""
        return self.get_cursor(user_id)

    def quiz_session_start(self, user_id: int, lesson_id: str, total_questions: int) -> None:
        """Сбросить счётчики перед первым вопросом (или повтором квиза)."""
        key = f"{user_id}:{lesson_id}"
        with self._quiz_lock:
            self._quiz_sessions[key] = {
                "scores": [],
                "total": max(0, int(total_questions)),
            }

    def quiz_session_clear(self, user_id: int, lesson_id: str) -> None:
        with self._quiz_lock:
            self._quiz_sessions.pop(f"{user_id}:{lesson_id}", None)

    def quiz_session_resume_next_index(self, user_id: int, lesson_id: str) -> Optional[int]:
        """
        Если квиз по этому уроку уже начат и не закончен — индекс следующего вопроса (len(scores)).
        Иначе None (начинать с 0). «Зависшая» завершённая сессия (scores полные) — удаляется.
        """
        key = f"{user_id}:{lesson_id}"
        with self._quiz_lock:
            sess = self._quiz_sessions.get(key)
            if not sess or sess["total"] <= 0:
                return None
            scores = sess["scores"]
            total = int(sess["total"])
            n = len(scores)
            if n >= total:
                self._quiz_sessions.pop(key, None)
                return None
            if n == 0:
                return None
            return n

    def quiz_session_in_progress(self, user_id: int, lesson_id: str) -> bool:
        """Квиз начат и ещё не завершён (в т.ч. на первом вопросе, 0 ответов)."""
        key = f"{user_id}:{lesson_id}"
        with self._quiz_lock:
            sess = self._quiz_sessions.get(key)
            if not sess or sess["total"] <= 0:
                return False
            return len(sess["scores"]) < int(sess["total"])

    QUIZ_SOFT_GROUP_COOLDOWN = timedelta(seconds=180)

    def should_post_quiz_soft_to_group(self, user_id: int, lesson_id: str) -> bool:
        """True — можно постить «почти прошёл» в группу; выставляет время последнего поста."""
        key = f"{user_id}:{lesson_id}"
        now = datetime.now()
        with self._quiz_lock:
            last = self._quiz_soft_group_last.get(key)
            if last is not None and (now - last) < self.QUIZ_SOFT_GROUP_COOLDOWN:
                return False
            self._quiz_soft_group_last[key] = now
            return True

    def quiz_session_append_score(
        self, user_id: int, lesson_id: str, question_idx: int, is_correct: bool
    ) -> Union[Literal["mismatch"], Tuple[int, int], None]:
        """
        Записать ответ на вопрос question_idx (по порядку 0..n-1).
        Возвращает (correct_answers, total_questions), если квиз только что завершён;
        None — если ещё есть вопросы;
        "mismatch" — рассинхрон (старая кнопка и т.п.).
        """
        key = f"{user_id}:{lesson_id}"
        with self._quiz_lock:
            sess = self._quiz_sessions.get(key)
            if not sess or sess["total"] <= 0:
                return "mismatch"
            if question_idx != len(sess["scores"]):
                return "mismatch"
            sess["scores"].append(bool(is_correct))
            total = sess["total"]
            if len(sess["scores"]) < total:
                return None
            correct = sum(1 for x in sess["scores"] if x)
            return (correct, total)


progress_manager = UserProgressManager()
