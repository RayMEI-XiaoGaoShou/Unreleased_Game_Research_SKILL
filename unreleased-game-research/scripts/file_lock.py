from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def exclusive_file_lock(target_path: Path, timeout_seconds: float = 120.0, poll_seconds: float = 0.1) -> Iterator[None]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target_path.with_name(f"{target_path.name}.lock")
    start_time = time.monotonic()
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() - start_time >= timeout_seconds:
                raise SystemExit(f"Timed out waiting for file lock: {lock_path}")
            time.sleep(poll_seconds)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
