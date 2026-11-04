"""The answer cache of the image service (like AudioCache in the text-to-speech services, but for PNG answers)."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class ImageCache:
    """The last answers, least recently used out. Per replica and in memory, so with N replicas the hit rate is
    about 1/N; an answer over MAX_BYTES is not kept, so `size` entries cost at most size * MAX_BYTES.

    shortcut: no shared store between replicas, upgrade only if the hit rate matters."""

    MAX_BYTES = 1_000_000  # a 256x256 PNG is about 150 KB

    def __init__(self) -> None:
        self._items: OrderedDict[Any, dict[str, Any]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._items)

    def get(self, key: Any, size: int) -> dict[str, Any] | None:
        """The kept answer for `key`, or None. `size` 0 turns the cache off and empties it."""
        if not size:
            self._items.clear()
            return None
        item = self._items.get(key)
        if item is not None:
            self._items.move_to_end(key)
        return item

    def put(self, key: Any, item: dict[str, Any], size: int) -> None:
        if not size or len(item["png"]) > self.MAX_BYTES:
            return
        self._items[key] = item
        self._items.move_to_end(key)
        while len(self._items) > size:
            self._items.popitem(last=False)
