"""JSON file-backed config storage with in-memory cache."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigStorage:
    """Persist admin configuration to a JSON file."""

    DEFAULT_CONFIG_PATH = "/data/mcp-admin-config.json"

    def __init__(self, config_path: str | Path | None = None):
        self._config_path = Path(
            config_path or os.environ.get("WEB_MCP_ADMIN_CONFIG_FILE", self.DEFAULT_CONFIG_PATH)
        )
        self._cache: dict[str, Any] = {"version": 1, "paths": {}}
        self._load()

    def _load(self) -> None:
        """Load config from disk into cache."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {"version": 1, "paths": {}}

    def save(self) -> None:
        """Persist cache to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w") as f:
            json.dump(self._cache, f, indent=2)

    def get_paths(self) -> dict[str, Any]:
        """Return all path configurations."""
        return self._cache.get("paths", {})

    def get_path_config(self, path: str) -> dict[str, Any] | None:
        """Return config for a specific path, or None."""
        return self._cache.get("paths", {}).get(path)

    def set_path_config(self, path: str, config: dict[str, Any]) -> None:
        """Save config for a path and persist to disk."""
        self._cache.setdefault("paths", {})[path] = config
        self.save()

    def delete_path_config(self, path: str) -> bool:
        """Delete config for a path. Returns True if it existed."""
        paths = self._cache.get("paths", {})
        if path in paths:
            del paths[path]
            self.save()
            return True
        return False

    def get_all_tool_names(self) -> list[str]:
        """Return the list of all available tool names."""
        from web_mcp.server import TOOL_REGISTRY

        return list(TOOL_REGISTRY.keys())
