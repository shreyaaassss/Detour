"""Append-only audit log with a hash chain (FR-15).

Every entry stores the hash of the one before it, so editing, deleting or reordering any
past entry is detectable with verify(). Entries are written through to a JSONL file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

GENESIS = "0" * 64


class AuditEntry(BaseModel):
    id: int
    ts: str
    sim_time: float | None  # the simulated clock (minutes since midnight) when it happened
    actor: str
    action: str
    details: dict[str, Any]
    prev_hash: str
    hash: str


def _digest(prev_hash: str, body: dict[str, Any]) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(f"{prev_hash}|{canon}".encode()).hexdigest()


def _body(e: AuditEntry | dict[str, Any]) -> dict[str, Any]:
    d = e.model_dump() if isinstance(e, AuditEntry) else e
    return {k: d[k] for k in ("id", "ts", "sim_time", "actor", "action", "details")}


class AuditLog:
    def __init__(self, path: Path | None = None, on_append: Callable[[AuditEntry], None] | None = None):
        self.path = path
        self.on_append = on_append
        self.entries: list[AuditEntry] = []
        self.archived: Path | None = None
        if path is not None and path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        try:
            loaded = [AuditEntry.model_validate_json(line) for line in path.read_text().splitlines() if line.strip()]
        except ValueError:
            loaded = []
        self.entries = loaded
        if loaded and not self.verify()["valid"]:
            # a log that fails verification is kept for inspection and never extended
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            self.archived = path.with_name(f"{path.stem}.corrupt-{stamp}{path.suffix}")
            path.rename(self.archived)
            self.entries = []

    def append(
        self, actor: str, action: str, details: dict[str, Any] | None = None, sim_time: float | None = None
    ) -> AuditEntry:
        prev = self.entries[-1].hash if self.entries else GENESIS
        body = {
            "id": len(self.entries) + 1,
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "sim_time": None if sim_time is None else float(sim_time),
            "actor": actor,
            "action": action,
            "details": json.loads(json.dumps(details or {}, default=str)),
        }
        entry = AuditEntry(**body, prev_hash=prev, hash=_digest(prev, body))
        self.entries.append(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(entry.model_dump_json() + "\n")
        if self.on_append:
            self.on_append(entry)
        return entry

    def verify(self, entries: list[AuditEntry] | None = None) -> dict[str, Any]:
        """Recompute the chain. Reports the first broken entry, if any."""
        es = self.entries if entries is None else entries
        prev = GENESIS
        for i, e in enumerate(es):
            if e.id != i + 1:
                return {"valid": False, "entries": len(es), "broken_at": e.id, "reason": "entry missing or reordered"}
            if e.prev_hash != prev:
                return {"valid": False, "entries": len(es), "broken_at": e.id, "reason": "chain link does not match"}
            if _digest(prev, _body(e)) != e.hash:
                return {"valid": False, "entries": len(es), "broken_at": e.id, "reason": "entry was modified"}
            prev = e.hash
        return {"valid": True, "entries": len(es), "broken_at": None, "reason": None, "head": prev}

    def tail(self, limit: int = 200, after: int = 0) -> list[AuditEntry]:
        return [e for e in self.entries if e.id > after][-limit:]
