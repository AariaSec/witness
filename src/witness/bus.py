"""The single in-process event bus.

Every listener (marker, sink, proc watcher, file watcher, tailer) emits
typed pydantic records onto one `queue.Queue`. Nothing but the ledger
writer ever consumes it — this is what keeps "one thread writes the
ledger" true and makes the hash chain meaningful.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel


class EventSource(Protocol):
    """A listener that can be started/stopped and emits records via a
    callback it is handed at `start()` time."""

    def start(self, emit: Callable[[BaseModel], None]) -> None: ...

    def stop(self) -> None: ...


class EventBus:
    """Thread-safe single-consumer queue of pydantic records.

    Listeners call `bus.emit_fn` (bound via `start(bus.emit_fn)`) from
    whatever thread they run on; one consumer thread (the ledger writer)
    calls `get()` / iterates `drain()`.
    """

    def __init__(self, maxsize: int = 0) -> None:
        self._q: queue.Queue[BaseModel] = queue.Queue(maxsize=maxsize)
        self._closed = threading.Event()

    def emit_fn(self, record: BaseModel) -> None:
        """Callback handed to listeners' `start()`."""
        if self._closed.is_set():
            return
        self._q.put(record)

    def get(self, timeout: float | None = None) -> BaseModel:
        """Block for the next record. Raises `queue.Empty` on timeout."""
        return self._q.get(timeout=timeout)

    def get_nowait(self) -> BaseModel | None:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def qsize(self) -> int:
        return self._q.qsize()

    def close(self) -> None:
        """Stop accepting new records. Already-queued records can still be
        drained by the consumer."""
        self._closed.set()


__all__ = ["EventBus", "EventSource"]
