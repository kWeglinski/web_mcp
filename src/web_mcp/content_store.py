import asyncio
import hashlib
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass


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
    ):
        self.max_size: int = max_size
        self.default_ttl: float = default_ttl
        self.cleanup_interval: float = cleanup_interval
        self._store: OrderedDict[str, StoredContent] = OrderedDict()
        self._cleanup_task: asyncio.Task | None = None

    def _generate_id(self, content: str | bytes) -> str:
        timestamp = str(time.time())
        if isinstance(content, bytes):
            unique_input = f"{content.hex()}:{timestamp}"
        else:
            unique_input = f"{content}:{timestamp}:{id(content)}"
        return hashlib.sha256(unique_input.encode()).hexdigest()[:16]

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

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
                self._store.popitem(last=False)

        self._store[content_id] = stored
        self._store.move_to_end(content_id)

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
            return True
        return False

    def evict_expired(self) -> int:
        return self._evict_expired()

    def _evict_expired(self) -> int:
        now = time.time()
        expired = [cid for cid, s in self._store.items() if now > s.expires_at]
        for cid in expired:
            del self._store[cid]
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
        _content_store = ContentStore(default_ttl=float(config.content_ttl))

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
