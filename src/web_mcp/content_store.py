import asyncio
import hashlib
import json
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StoredContent:
    content: str | bytes
    content_type: str
    created_at: float
    expires_at: float
    token: str


class ContentStore:
    DEFAULT_TTL: float = 3600.0
    DEFAULT_MAX_SIZE: int = 1000
    DEFAULT_CLEANUP_INTERVAL: float = 300.0

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_SIZE,
        default_ttl: float = DEFAULT_TTL,
        cleanup_interval: float = DEFAULT_CLEANUP_INTERVAL,
        storage_path: str | None = None,
    ):
        self.max_size: int = max_size
        self.default_ttl: float = default_ttl
        self.cleanup_interval: float = cleanup_interval
        self._store: OrderedDict[str, StoredContent] = OrderedDict()
        self._cleanup_task: asyncio.Task | None = None
        self._storage_enabled: bool = False

        if storage_path:
            self.storage_path: Path | None = Path(storage_path)
            try:
                self.storage_path.mkdir(parents=True, exist_ok=True)
                self._storage_enabled = True
                self._load_from_disk()
            except OSError:
                self.storage_path = None
        else:
            self.storage_path = None

    def _generate_id(self, content: str | bytes) -> str:
        timestamp = str(time.time())
        if isinstance(content, bytes):
            unique_input = f"{content.hex()}:{timestamp}"
        else:
            unique_input = f"{content}:{timestamp}:{id(content)}"
        return hashlib.sha256(unique_input.encode()).hexdigest()[:16]

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _get_content_path(self, content_id: str) -> Path | None:
        if not self.storage_path:
            return None
        return self.storage_path / f"{content_id}.json"

    def _save_to_disk(self, content_id: str, stored: StoredContent) -> None:
        if not self._storage_enabled or not self.storage_path:
            return
        content_path = self._get_content_path(content_id)
        if not content_path:
            return
        try:
            data = {
                "content": (
                    stored.content
                    if isinstance(stored.content, str)
                    else stored.content.decode("utf-8", errors="replace")
                ),
                "content_type": stored.content_type,
                "created_at": stored.created_at,
                "expires_at": stored.expires_at,
                "token": stored.token,
            }
            with open(content_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass

    def _delete_from_disk(self, content_id: str) -> None:
        if not self.storage_path:
            return
        content_path = self._get_content_path(content_id)
        if content_path and content_path.exists():
            content_path.unlink()

    def _load_from_disk(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        now = time.time()
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                stored = StoredContent(
                    content=data["content"],
                    content_type=data["content_type"],
                    created_at=data["created_at"],
                    expires_at=data["expires_at"],
                    token=data["token"],
                )
                if now <= stored.expires_at:
                    self._store[file_path.stem] = stored
                else:
                    file_path.unlink()
            except (json.JSONDecodeError, KeyError, OSError):
                file_path.unlink()

    def store(
        self,
        content: str | bytes,
        content_type: str = "text/html",
        ttl: float | None = None,
    ) -> tuple[str, str]:
        if ttl is None:
            ttl = self.default_ttl

        content_id = self._generate_id(content)
        token = self._generate_token()
        now = time.time()

        # TTL of 0 means endless (never expire)
        expires_at = float("inf") if ttl == 0 else now + ttl

        stored = StoredContent(
            content=content,
            content_type=content_type,
            created_at=now,
            expires_at=expires_at,
            token=token,
        )

        if len(self._store) >= self.max_size:
            self._evict_expired()
            if len(self._store) >= self.max_size:
                evicted_id, _ = self._store.popitem(last=False)
                self._delete_from_disk(evicted_id)

        self._store[content_id] = stored
        self._store.move_to_end(content_id)

        self._save_to_disk(content_id, stored)

        return content_id, token

    def get(self, content_id: str) -> StoredContent | None:
        if content_id not in self._store:
            return None

        stored = self._store[content_id]

        if time.time() > stored.expires_at:
            del self._store[content_id]
            return None

        self._store.move_to_end(content_id)
        return stored

    def delete(self, content_id: str) -> bool:
        if content_id in self._store:
            del self._store[content_id]
            self._delete_from_disk(content_id)
            return True
        return False

    def evict_expired(self) -> int:
        return self._evict_expired()

    def _evict_expired(self) -> int:
        now = time.time()
        expired = [cid for cid, s in self._store.items() if now > s.expires_at]
        for cid in expired:
            del self._store[cid]
            self._delete_from_disk(cid)
        return len(expired)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def get_stats(self) -> dict:
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "cleanup_interval": self.cleanup_interval,
        }

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.cleanup_interval)
            self._evict_expired()

    def start_cleanup_task(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup_task(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


_content_store: ContentStore | None = None


def get_content_store() -> ContentStore:
    global _content_store

    if _content_store is None:
        from web_mcp.config import get_config

        config = get_config()
        _content_store = ContentStore(
            default_ttl=float(config.content_ttl),
            storage_path=config.content_storage_path,
        )

    return _content_store


def start_cleanup_task() -> None:
    store = get_content_store()
    store.start_cleanup_task()


def stop_cleanup_task() -> None:
    global _content_store
    if _content_store:
        _content_store.stop_cleanup_task()


def reset_content_store() -> None:
    global _content_store
    if _content_store:
        _content_store.stop_cleanup_task()
    _content_store = None
