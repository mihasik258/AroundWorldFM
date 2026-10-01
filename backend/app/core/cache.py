import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from typing import Any

from app.core.config import settings

_MISSING = object()


class TTLCache:
    """In-process TTL cache."""

    def __init__(self, ttl: float, max_entries: int):
        self.ttl = ttl
        self.max_entries = max_entries
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._locks: dict[Hashable, asyncio.Lock] = {}
        self._generation = 0

    def _get(self, key: Hashable) -> Any:
        entry = self._data.get(key)
        if entry is None:
            return _MISSING
        expires, value = entry
        if expires <= time.monotonic():
            del self._data[key]
            return _MISSING
        self._data.move_to_end(key)
        return value

    async def get_or_set(self, key: Hashable, producer: Callable[[], Awaitable[Any]]) -> Any:
        value = self._get(key)
        if value is not _MISSING:
            return value

        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                value = self._get(key)
                if value is not _MISSING:
                    return value
                generation = self._generation
                value = await producer()
                if generation == self._generation:
                    self._data[key] = (time.monotonic() + self.ttl, value)
                    self._data.move_to_end(key)
                    while len(self._data) > self.max_entries:
                        self._data.popitem(last=False)
                return value
        finally:
            if not lock.locked():
                self._locks.pop(key, None)

    def clear(self) -> None:
        self._generation += 1
        self._data.clear()


catalog_cache = TTLCache(ttl=settings.CATALOG_CACHE_TTL_SECONDS, max_entries=512)
