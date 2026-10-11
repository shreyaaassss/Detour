"""Fan-out of state changes to connected clients as server-sent events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(q)

    @property
    def clients(self) -> int:
        return len(self._subs)

    def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # a stuck client must not block the others; it will resync on reconnect
                self._subs.discard(q)

    async def stream(
        self, hello: dict[str, Any], max_events: int | None = None, heartbeat: float = 15.0
    ) -> AsyncIterator[str]:
        q = self.subscribe()
        sent = 0
        try:
            yield sse("hello", hello)
            sent += 1
            while max_events is None or sent < max_events:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=heartbeat)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield sse(ev["type"], ev)
                sent += 1
        finally:
            self.unsubscribe(q)


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
