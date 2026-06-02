import sys
import threading


class ProgressReporter:
    def __init__(self, enabled=True, stream=None):
        self.enabled = enabled
        self.stream = stream or sys.stderr
        self._lock = threading.Lock()

    def phase(self, label, total):
        return _ProgressPhase(label=label, total=total, enabled=self.enabled, stream=self.stream, lock=self._lock)


class _ProgressPhase:
    BAR_WIDTH = 24

    def __init__(self, label, total, enabled=True, stream=None, lock=None):
        self.label = label
        self.total = max(int(total or 0), 0)
        self.enabled = enabled and self.total > 0
        self.stream = stream or sys.stderr
        self._lock = lock or threading.Lock()
        self.completed = 0
        self._last_length = 0
        if self.enabled:
            self._render()

    def advance(self, step=1, detail=None):
        if not self.enabled:
            return
        self.completed = min(self.total, self.completed + step)
        self._render(detail=detail)

    def close(self, detail=None):
        if not self.enabled:
            return
        self.completed = self.total
        self._render(detail=detail)
        self.stream.write("\n")
        self.stream.flush()

    def _render(self, detail=None):
        with self._lock:
            ratio = 1.0 if self.total == 0 else self.completed / self.total
            filled = int(self.BAR_WIDTH * ratio)
            bar = "#" * filled + "-" * (self.BAR_WIDTH - filled)
            suffix = f" {detail}" if detail else ""
            line = f"\r[{bar}] {self.completed}/{self.total} {self.label}{suffix}"
            padding = max(0, self._last_length - len(line))
            self.stream.write(line + (" " * padding))
            self.stream.flush()
            self._last_length = len(line)
