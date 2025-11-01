"""Utilities for checking administrative access."""

from __future__ import annotations

from typing import Optional, Set

from config import ADMIN_USER_IDS, CREATOR_USER_ID, CREATOR_USERNAME


def _normalize_username(value: Optional[str]) -> Optional[str]:
    """Normalize a Telegram username for comparison."""
    if not value:
        return None
    return value.lstrip('@').lower()


_ALLOWED_ADMIN_USERNAMES: Set[str] = set()
_creator_username = _normalize_username(CREATOR_USERNAME)
if _creator_username:
    _ALLOWED_ADMIN_USERNAMES.add(_creator_username)

_ALLOWED_ADMIN_IDS: Set[int] = set(ADMIN_USER_IDS)
if CREATOR_USER_ID is not None:
    _ALLOWED_ADMIN_IDS.add(CREATOR_USER_ID)


def is_admin_identity(user_id: Optional[int], username: Optional[str]) -> bool:
    """Return True if the provided identity belongs to a configured admin."""
    if user_id is not None and user_id in _ALLOWED_ADMIN_IDS:
        return True

    normalized = _normalize_username(username)
    if normalized and normalized in _ALLOWED_ADMIN_USERNAMES:
        return True

    return False
