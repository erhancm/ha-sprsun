"""In-memory circular live log for SPRSUN Modbus activity."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Iterable


class LiveLog:
    """Fixed-capacity ring buffer of timestamped log lines."""

    def __init__(self, capacity: int = 10_000) -> None:
        self.capacity = max(1, int(capacity))
        self._lines: deque[str] = deque(maxlen=self.capacity)
        self.generation: int = 0  # bumps on every append/clear so HA can refresh

    def __len__(self) -> int:
        return len(self._lines)

    @property
    def size(self) -> int:
        return len(self._lines)

    def append(self, message: str, *, level: str = "INFO") -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        text = " ".join(str(message).split())
        if not text:
            return
        self._lines.append(f"{ts} [{level}] {text}")
        self.generation += 1

    def info(self, message: str) -> None:
        self.append(message, level="INFO")

    def warn(self, message: str) -> None:
        self.append(message, level="WARN")

    def error(self, message: str) -> None:
        self.append(message, level="ERROR")

    def debug(self, message: str) -> None:
        self.append(message, level="DEBUG")

    def clear(self) -> None:
        self._lines.clear()
        self.generation += 1

    def tail(self, n: int = 40) -> list[str]:
        if n <= 0:
            return []
        if n >= len(self._lines):
            return list(self._lines)
        return list(self._lines)[-n:]

    def dump(self) -> str:
        return "\n".join(self._lines)

    def extend(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.append(line)
