"""Recorder configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class RecordConfig(BaseModel):
    """Configuration for one `witness record` invocation."""

    model_config = ConfigDict(extra="forbid")

    lab: Path
    marker_port: int = 47101
    sink_port: int = 47102
    host: str = "127.0.0.1"
    fsync: bool = True
    max_seconds: float | None = None
    protected_paths: list[str] = Field(default_factory=lambda: ["protected"])
    hash_limit_bytes: int = 8 * 2**20
    poll_interval_s: float = 0.25
    capture_sizes: bool = False
    keydir: Path = Field(default_factory=lambda: Path.home() / ".witness" / "keys")

    @property
    def lab_resolved(self) -> Path:
        return self.lab.resolve()


__all__ = ["RecordConfig"]
