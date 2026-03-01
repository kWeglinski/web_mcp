import hashlib
import time
from dataclasses import dataclass
from typing import Optional

from collections import OrderedDict


@dataclass
class StoredContent:
    content: str
    content_type: str
    created_at: float
    expires_at: float


class ContentStore:
    DEFAULT_TTL: float = 3600.0
    DEFAULT_MAX_SIZE: int = 1000
    
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, default_ttl: float = DEFAULT_TTL):
        self.max_size: int = max_size
        self.default_ttl: float = default_ttl
        self._store: OrderedDict[str, StoredContent] = OrderedDict()
    
    def _generate_id(self, content: str) -> str:
        timestamp = str(time.time())
        unique_input = f"{content}:{timestamp}:{id(content)}"
        return hashlib.sha256(unique_input.encode()).hexdigest()[:16]
    
    def store(self, content: str, content_type: str = "text/html", ttl: Optional[float] = None) -> str:
        if ttl is None:
            ttl = self.default_ttl
        
        content_id = self._generate_id(content)
        now = time.time()
        
        stored = StoredContent(
            content=content,
            content_type=content_type,
            created_at=now,
            expires_at=now + ttl,
        )
        
        if len(self._store) >= self.max_size:
            self._evict_expired()
            if len(self._store) >= self.max_size:
                self._store.popitem(last=False)
        
        self._store[content_id] = stored
        self._store.move_to_end(content_id)
        
        return content_id
    
    def get(self, content_id: str) -> Optional[StoredContent]:
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
        }


_content_store: Optional[ContentStore] = None


def get_content_store() -> ContentStore:
    global _content_store
    
    if _content_store is None:
        from web_mcp.config import get_config
        config = get_config()
        _content_store = ContentStore(default_ttl=float(config.content_ttl))
    
    return _content_store


def reset_content_store() -> None:
    global _content_store
    _content_store = None
