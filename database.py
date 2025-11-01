"""Persistent user database helper with optional Google Sheets backend."""

from __future__ import annotations

import atexit
import base64
import json
import logging
import os
import re
from datetime import datetime, timedelta
from threading import RLock
from typing import Dict, List, Optional

try:
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    gspread = None
    Credentials = None

DEFAULT_DB_FILE = "users.json"
ENV_DB_FILE_VAR = "USER_DB_FILE"

ENV_SHEETS_CREDENTIALS = "GOOGLE_SHEETS_CREDENTIALS"
ENV_SHEETS_SPREADSHEET = "GOOGLE_SHEETS_SPREADSHEET"
ENV_SHEETS_WORKSHEET = "GOOGLE_SHEETS_WORKSHEET"

SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
SHEET_HEADERS = [
    "user_id",
    "username",
    "first_name",
    "preferred_language",
    "skill_level",
    "total_questions",
    "favorite_topics",
    "created_at",
    "last_active",
]

logger = logging.getLogger(__name__)


def _extract_spreadsheet_key(reference: str) -> str:
    """Return the spreadsheet key from a URL or raw key/name."""
    reference = reference.strip()
    url_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", reference)
    if url_match:
        return url_match.group(1)
    return reference


def _decode_credentials(raw_value: str) -> Dict:
    """Decode a service account JSON from base64 or direct JSON string."""
    value = raw_value.strip()
    if value.startswith("{"):
        return json.loads(value)
    try:
        decoded = base64.b64decode(value)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid GOOGLE_SHEETS_CREDENTIALS payload") from exc


class UserDatabase:
    """Storage for user statistics with support for Google Sheets or local JSON."""

    def __init__(self, db_file: Optional[str] = None) -> None:
        self._lock = RLock()
        self._use_sheets = False
        self._worksheet = None

        creds_blob = os.getenv(ENV_SHEETS_CREDENTIALS)
        spreadsheet_ref = os.getenv(ENV_SHEETS_SPREADSHEET)
        worksheet_name = os.getenv(ENV_SHEETS_WORKSHEET, "Users")

        want_sheets = db_file is None and bool(creds_blob and spreadsheet_ref)
        logger.info(
            "DB backend bootstrap: want_sheets=%s, have_creds=%s, spreadsheet_set=%s, worksheet=%s",
            want_sheets,
            bool(creds_blob),
            bool(spreadsheet_ref),
            worksheet_name,
        )

        if want_sheets and creds_blob:
            try:
                info = _decode_credentials(creds_blob)
                logger.info("Service account email: %s", info.get("client_email"))
            except Exception as exc:
                logger.error("Failed to decode GOOGLE_SHEETS_CREDENTIALS: %s", exc)

        if db_file is None and self._init_google_sheets_backend():
            self.db_file: Optional[str] = None
            logger.info(
                "User database configured to use Google Sheets (worksheet: %s).",
                self._worksheet.title if self._worksheet else "unknown",
            )
        else:
            path = (db_file or os.getenv(ENV_DB_FILE_VAR) or DEFAULT_DB_FILE).strip() or DEFAULT_DB_FILE
            if os.path.isdir(path):
                path = os.path.join(path, DEFAULT_DB_FILE)
            directory = os.path.dirname(os.path.abspath(path))
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except OSError as exc:
                    logger.error("Failed to create directory for the user DB at %s: %s", directory, exc)
            self.db_file = path

        self.users_data: Dict[str, Dict] = self._load_data()
        atexit.register(self._save_data)

    # ------------------------------------------------------------------ #
    # Backend initialisation
    # ------------------------------------------------------------------ #
    def _init_google_sheets_backend(self) -> bool:
        credentials_blob = os.getenv(ENV_SHEETS_CREDENTIALS)
        spreadsheet_ref = os.getenv(ENV_SHEETS_SPREADSHEET)

        if not credentials_blob or not spreadsheet_ref:
            return False
        if gspread is None or Credentials is None:
            logger.warning(
                "Google Sheets credentials provided but gspread/google-auth are not installed. "
                "Falling back to local JSON storage."
            )
            return False

        try:
            info = _decode_credentials(credentials_blob)
            creds = Credentials.from_service_account_info(info, scopes=SHEETS_SCOPES)
            client = gspread.authorize(creds)

            key_or_name = _extract_spreadsheet_key(spreadsheet_ref)
            try:
                spreadsheet = client.open_by_key(key_or_name)
            except gspread.SpreadsheetNotFound:
                spreadsheet = client.open(key_or_name)

            worksheet_title = os.getenv(ENV_SHEETS_WORKSHEET, "Users")
            try:
                worksheet = spreadsheet.worksheet(worksheet_title)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows="1000", cols="20")
                worksheet.update("A1", [SHEET_HEADERS])

            logger.info("Google Sheets DB initialized successfully")
            logger.info("Using worksheet: %s", worksheet_title)
        except Exception as exc:  # pragma: no cover - relies on external API
            logger.error("Failed to initialise Google Sheets backend: %s", exc)
            return False

        self._worksheet = worksheet
        self._use_sheets = True
        return True

    # ------------------------------------------------------------------ #
    # Data load/save helpers
    # ------------------------------------------------------------------ #
    def _load_data(self) -> Dict[str, Dict]:
        if self._use_sheets and self._worksheet:
            return self._load_from_sheet()
        return self._load_from_file()

    def _load_from_file(self) -> Dict[str, Dict]:
        path = self.db_file
        if not path:
            return {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Error loading database %s: %s", path, exc)
        return {}

    def _load_from_sheet(self) -> Dict[str, Dict]:  # pragma: no cover - external I/O
        assert self._worksheet is not None
        try:
            records = self._worksheet.get_all_records()
        except Exception as exc:
            logger.error("Error reading Google Sheet: %s", exc)
            return {}

        users: Dict[str, Dict] = {}
        for row in records:
            user_id = row.get("user_id")
            if user_id in ("", None):
                continue
            try:
                user_id_int = int(str(user_id).strip())
            except (TypeError, ValueError):
                continue

            topics_cell = row.get("favorite_topics", "")
            if isinstance(topics_cell, str):
                topics = [item.strip() for item in topics_cell.split(";") if item.strip()]
            elif isinstance(topics_cell, list):
                topics = [str(item).strip() for item in topics_cell if str(item).strip()]
            else:
                topics = []

            def _str(value: Optional[str]) -> Optional[str]:
                return value or None

            users[str(user_id_int)] = {
                "user_id": user_id_int,
                "username": _str(row.get("username")),
                "first_name": _str(row.get("first_name")),
                "preferred_language": _str(row.get("preferred_language")),
                "skill_level": row.get("skill_level") or "intermediate",
                "total_questions": int(row.get("total_questions") or 0),
                "favorite_topics": topics,
                "created_at": row.get("created_at") or datetime.now().isoformat(),
                "last_active": row.get("last_active") or datetime.now().isoformat(),
            }
        return users

    def _save_data(self) -> None:
        if self._use_sheets and self._worksheet:
            self._save_to_sheet()
        else:
            self._save_to_file()

    def _save_to_file(self) -> None:
        path = self.db_file
        if not path:
            return
        with self._lock:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(self.users_data, fh, ensure_ascii=False, indent=2)
            except OSError as exc:
                logger.error("Error saving database %s: %s", path, exc)

    def _save_to_sheet(self) -> None:  # pragma: no cover - external I/O
        assert self._worksheet is not None
        with self._lock:
            try:
                rows: List[List] = []
                for user_key in sorted(self.users_data.keys(), key=lambda key: int(key)):
                    record = self.users_data[user_key]
                    rows.append(
                        [
                            record.get("user_id", ""),
                            record.get("username") or "",
                            record.get("first_name") or "",
                            record.get("preferred_language") or "",
                            record.get("skill_level") or "",
                            record.get("total_questions", 0),
                            "; ".join(record.get("favorite_topics", [])),
                            record.get("created_at") or "",
                            record.get("last_active") or "",
                        ]
                    )

                self._worksheet.clear()
                self._worksheet.update("A1", [SHEET_HEADERS] + rows)
            except Exception as exc:
                logger.error("Error saving data to Google Sheet: %s", exc)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_user(self, user_id: int) -> Dict:
        user_key = str(user_id)
        with self._lock:
            if user_key not in self.users_data:
                now_iso = datetime.now().isoformat()
                self.users_data[user_key] = {
                    "user_id": user_id,
                    "username": None,
                    "first_name": None,
                    "preferred_language": None,
                    "skill_level": "intermediate",
                    "total_questions": 0,
                    "favorite_topics": [],
                    "created_at": now_iso,
                    "last_active": now_iso,
                }
                self._save_data()
            return self.users_data[user_key]

    def update_user(self, user_id: int, updates: Dict) -> None:
        with self._lock:
            record = self.get_user(user_id)
            record.update(updates)
            record["last_active"] = datetime.now().isoformat()
            self.users_data[str(user_id)] = record
            self._save_data()

    def increment_questions(self, user_id: int) -> None:
        with self._lock:
            record = self.get_user(user_id)
            record["total_questions"] = record.get("total_questions", 0) + 1
            record["last_active"] = datetime.now().isoformat()
            self.users_data[str(user_id)] = record
            self._save_data()

    def add_topic_interest(self, user_id: int, topic: str) -> None:
        topic = topic.strip()
        if not topic:
            return
        with self._lock:
            record = self.get_user(user_id)
            topics = record.setdefault("favorite_topics", [])
            if topic not in topics:
                topics.append(topic)
                record["favorite_topics"] = topics[-10:]  # keep last 10
                logger.info("User %s added topic interest %s", user_id, topic)
            record["last_active"] = datetime.now().isoformat()
            self.users_data[str(user_id)] = record
            self._save_data()

    def get_user_stats(self, user_id: int) -> Dict:
        record = self.get_user(user_id)
        return {
            "total_questions": record.get("total_questions", 0),
            "favorite_topics": record.get("favorite_topics", []),
            "preferred_language": record.get("preferred_language"),
            "skill_level": record.get("skill_level", "intermediate"),
            "member_since": record.get("created_at", "Unknown"),
        }

    def get_all_users_count(self) -> int:
        with self._lock:
            return len(self.users_data)

    def get_active_users(self, days: int = 7) -> List[Dict]:
        cutoff = datetime.now() - timedelta(days=days)
        active: List[Dict] = []
        with self._lock:
            for record in self.users_data.values():
                last_active_str = record.get("last_active")
                try:
                    last_active = datetime.fromisoformat(last_active_str) if last_active_str else None
                except ValueError:
                    last_active = None
                if last_active and last_active > cutoff:
                    active.append(record)
        return active


user_db = UserDatabase()
