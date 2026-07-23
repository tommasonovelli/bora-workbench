"""Copy archive members while reporting truthful byte progress."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

from qwen_launcher._engine_types import TransferProgress, TransferProgressCallback

_CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True)
class ByteTracker:
    """Track extracted bytes across all regular members in one archive."""

    total_bytes: int
    progress: TransferProgressCallback | None
    completed_bytes: int = 0

    def start(self) -> None:
        """Report the known uncompressed archive size before copying members."""
        if self.progress is not None:
            self.progress(TransferProgress(0, self.total_bytes))

    def copy(self, source: BinaryIO, output: BinaryIO) -> None:
        """Copy one member in bounded chunks and report cumulative extracted bytes."""
        while chunk := source.read(_CHUNK_SIZE):
            output.write(chunk)
            self.completed_bytes += len(chunk)
            if self.progress is not None:
                self.progress(TransferProgress(self.completed_bytes, self.total_bytes))
