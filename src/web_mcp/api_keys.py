"""API key registry — manages named API keys with auto-incrementing user IDs."""

from __future__ import annotations

import os
import secrets
from contextvars import ContextVar
from typing import Any

from web_mcp.admin.storage import ConfigStorage

_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


class ApiKeyEntry:
    """Represents a single API key with its metadata."""

    def __init__(self, key: str, name: str, uid: int):
        self.key = key
        self.name = name
        self.uid = uid

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "uid": self.uid}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApiKeyEntry:
        return cls(key=data["key"], name=data["name"], uid=data["uid"])


class ApiKeyRegistry:
    """Manages API keys stored in the admin config JSON file.

    The initial token from WEB_MCP_AUTH_TOKEN is treated as uid 0.
    Newly created keys start from uid 1 and increment.
    """

    def __init__(self, storage: ConfigStorage | None = None):
        self._storage = storage or ConfigStorage()
        self._bootstrap_token: str | None = os.environ.get("WEB_MCP_AUTH_TOKEN")

    def _get_raw_keys(self) -> list[dict[str, Any]]:
        return self._storage.get_api_keys()

    def _save_keys(self, keys: list[dict[str, Any]]) -> None:
        self._storage.set_api_keys(keys)

    def _next_uid(self) -> int:
        existing = self._get_raw_keys()
        if not existing:
            return 1
        return max(k["uid"] for k in existing) + 1

    def get_all(self) -> list[ApiKeyEntry]:
        entries = []
        for raw in self._get_raw_keys():
            entries.append(ApiKeyEntry.from_dict(raw))
        if self._bootstrap_token:
            bootstrap_exists = any(e.key == self._bootstrap_token for e in entries)
            if not bootstrap_exists:
                entries.insert(0, ApiKeyEntry(key=self._bootstrap_token, name="bootstrap", uid=0))
        return entries

    def get_by_key(self, token: str) -> ApiKeyEntry | None:
        if self._bootstrap_token and token == self._bootstrap_token:
            return ApiKeyEntry(key=self._bootstrap_token, name="bootstrap", uid=0)
        for raw in self._get_raw_keys():
            if raw["key"] == token:
                return ApiKeyEntry.from_dict(raw)
        return None

    def create(self, name: str) -> ApiKeyEntry:
        new_key = f"sk-{secrets.token_hex(24)}"
        uid = self._next_uid()
        entry = ApiKeyEntry(key=new_key, name=name, uid=uid)
        raw_keys = self._get_raw_keys()
        raw_keys.append(entry.to_dict())
        self._save_keys(raw_keys)
        return entry

    def delete(self, key: str) -> bool:
        if self._bootstrap_token and key == self._bootstrap_token:
            return False
        raw_keys = self._get_raw_keys()
        new_keys = [k for k in raw_keys if k["key"] != key]
        if len(new_keys) == len(raw_keys):
            return False
        self._save_keys(new_keys)
        return True

    def update_name(self, key: str, new_name: str) -> bool:
        if self._bootstrap_token and key == self._bootstrap_token:
            return False
        raw_keys = self._get_raw_keys()
        for k in raw_keys:
            if k["key"] == key:
                k["name"] = new_name
                self._save_keys(raw_keys)
                return True
        return False


def get_current_user_id() -> str | None:
    """Get the current user ID from the authenticated API key.

    Returns the API key's uid as a string, or None if not authenticated.
    """
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        token = get_access_token()
        if token is not None:
            return token.client_id
    except ImportError:
        pass
    return None


def set_current_user_id(user_id: str | None) -> None:
    """Deprecated: user ID is now derived from the authenticated API key."""
    pass
