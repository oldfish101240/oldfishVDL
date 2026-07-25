"""將高頻背景進度事件合併後再送往 UI，避免 WebEngine 被頻繁重繪拖慢。"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class ProgressDispatcher:
    """每個下載任務最多每 ``interval`` 秒送出一次進度更新。

    完成、錯誤等最終事件仍由呼叫端直接送出，避免延後顯示最終狀態。
    """

    def __init__(self, emit: Callable[..., None], interval: float = 0.12):
        self._emit = emit
        self._interval = interval
        self._lock = threading.Lock()
        self._last_emit: dict[str, float] = {}
        self._pending: dict[str, tuple] = {}
        self._timers: dict[str, threading.Timer] = {}

    def publish(self, task_id, *args) -> None:
        key = str(task_id)
        now = time.monotonic()
        emit_now = False
        with self._lock:
            if now - self._last_emit.get(key, 0.0) >= self._interval:
                self._last_emit[key] = now
                self._pending.pop(key, None)
                emit_now = True
            else:
                self._pending[key] = args
                if key not in self._timers:
                    delay = max(0.0, self._interval - (now - self._last_emit.get(key, now)))
                    timer = threading.Timer(delay, self._flush, args=(key,))
                    timer.daemon = True
                    self._timers[key] = timer
                    timer.start()
        if emit_now:
            self._emit(*args)

    def flush(self, task_id) -> None:
        """立即送出指定任務尚未傳遞的最後一次狀態。"""
        self._flush(str(task_id))

    def _flush(self, key: str) -> None:
        args = None
        with self._lock:
            self._timers.pop(key, None)
            args = self._pending.pop(key, None)
            if args is not None:
                self._last_emit[key] = time.monotonic()
        if args is not None:
            self._emit(*args)
