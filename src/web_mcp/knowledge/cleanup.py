"""Background cleanup task for stale knowledge entries."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC

logger = logging.getLogger(__name__)

_cleanup_task: asyncio.Task | None = None
_cleanup_stop_event: asyncio.Event | None = None


class KnowledgeCleanupTask:
    """Periodically cleans up stale knowledge entries based on TTL."""

    def __init__(
        self,
        mem0_memory,
        cleanup_interval: int = 3600,
        ttl_days: int = 90,
    ):
        """Initialize cleanup task.

        Args:
            mem0_memory: mem0.Memory instance
            cleanup_interval: Seconds between cleanup runs
            ttl_days: Days after which entries are considered stale
        """
        self.mem0_memory = mem0_memory
        self.cleanup_interval = cleanup_interval
        self.ttl_days = ttl_days
        self._running = False
        self._stop_event = asyncio.Event()

    async def run_once(self) -> dict:
        """Run a single cleanup cycle.

        Returns:
            dict with cleanup statistics
        """
        from datetime import datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(days=self.ttl_days)
        cutoff_iso = cutoff.isoformat()

        logger.info(f"Starting knowledge cleanup (TTL: {self.ttl_days} days, cutoff: {cutoff_iso})")

        # Note: mem0 doesn't have a native TTL query, so we scan all memories
        # and remove ones older than the cutoff
        # In production, you'd use a more efficient approach (e.g., tagged timestamps)
        try:
            # Get all memories for the current user
            memories = self.mem0_memory.list()

            removed = 0
            kept = 0
            for mem in memories:
                # Check memory metadata for timestamp
                metadata = getattr(mem, "metadata", {}) or {}
                created_at = metadata.get("created_at") or metadata.get("timestamp")
                if created_at:
                    try:
                        mem_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        if mem_time < cutoff:
                            self.mem0_memory.delete(memory_id=mem.id)
                            removed += 1
                        else:
                            kept += 1
                    except (ValueError, TypeError):
                        kept += 1
                else:
                    # No timestamp — keep it
                    kept += 1

            logger.info(f"Knowledge cleanup complete: removed={removed}, kept={kept}")
            return {"removed": removed, "kept": kept, "cutoff": cutoff_iso}
        except Exception as e:
            logger.error(f"Knowledge cleanup failed: {e}")
            return {"error": str(e)}

    async def run(self):
        """Run the cleanup loop."""
        self._running = True
        logger.info(
            f"Knowledge cleanup started (interval: {self.cleanup_interval}s, TTL: {self.ttl_days} days)"
        )

        while self._running:
            await self.run_once()
            # Wait for next interval or stop signal
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.cleanup_interval)
                break
            except TimeoutError:
                continue

        logger.info("Knowledge cleanup stopped")

    def stop(self):
        """Signal the cleanup task to stop."""
        self._running = False
        if self._stop_event:
            self._stop_event.set()


def start_cleanup_task(
    mem0_memory,
    cleanup_interval: int = 3600,
    ttl_days: int = 90,
) -> KnowledgeCleanupTask:
    """Start the knowledge cleanup background task.

    Args:
        mem0_memory: mem0.Memory instance
        cleanup_interval: Seconds between cleanup runs
        ttl_days: TTL in days

    Returns:
        KnowledgeCleanupTask instance
    """
    global _cleanup_task, _cleanup_stop_event

    task = KnowledgeCleanupTask(mem0_memory, cleanup_interval, ttl_days)
    _cleanup_stop_event = asyncio.Event()
    _cleanup_task = asyncio.create_task(task.run())
    return task


def stop_cleanup_task() -> bool:
    """Stop the running knowledge cleanup task.

    Returns:
        True if a task was stopped, False if none was running
    """
    global _cleanup_task

    if _cleanup_task is None:
        return False

    if hasattr(_cleanup_task, "_instance"):
        _cleanup_task._instance.stop()

    _cleanup_task.cancel()
    _cleanup_task = None
    return True
