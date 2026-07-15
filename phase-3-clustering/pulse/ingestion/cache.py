"""On-disk cache of raw fetched payloads (architecture §3.2 — replayable backfill).

Caching raw responses makes reruns deterministic and lets backfill replay a historic window
without re-hitting the source. Keys are namespaced by source + product + a free-form suffix.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe(part: str) -> str:
    return _SAFE.sub("_", part)


class RawCache:
    def __init__(self, base_dir: str | Path = ".pulse/cache"):
        self.base = Path(base_dir)

    def _path(self, source: str, product_id: str, key: str) -> Path:
        return self.base / _safe(source) / _safe(product_id) / f"{_safe(key)}.json"

    def get(self, source: str, product_id: str, key: str):
        path = self._path(source, product_id, key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, source: str, product_id: str, key: str, payload) -> None:
        path = self._path(source, product_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
