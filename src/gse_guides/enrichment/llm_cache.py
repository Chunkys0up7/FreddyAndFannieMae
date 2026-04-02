"""Content-hash based cache for LLM enrichment results."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMCache:
    """File-based cache for LLM enrichment results.

    Cache key: SHA-256 of (content + model + prompt_version).
    Storage: {cache_dir}/{hash[0:2]}/{full_hash}.json
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._hits = 0
        self._misses = 0

    def get(
        self, content: str, model: str, prompt_version: str
    ) -> dict | None:
        """Return cached result or None on miss."""
        h = self.content_hash(content, model, prompt_version)
        path = self._path_for(h)

        if not path.exists():
            self._misses += 1
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._hits += 1
            return data.get("result")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Corrupt cache entry %s: %s", path.name, e)
            path.unlink(missing_ok=True)
            self._misses += 1
            return None

    def set(
        self,
        content: str,
        model: str,
        prompt_version: str,
        result: dict,
        tokens_used: int = 0,
    ) -> None:
        """Store a result in the cache."""
        h = self.content_hash(content, model, prompt_version)
        path = self._path_for(h)
        path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "result": result,
            "model": model,
            "prompt_version": prompt_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tokens_used": tokens_used,
        }
        path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total_entries = 0
        if self.cache_dir.exists():
            total_entries = sum(
                1 for _ in self.cache_dir.rglob("*.json")
            )
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_entries": total_entries,
            "hit_rate": (
                self._hits / (self._hits + self._misses)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }

    def clear(self) -> int:
        """Remove all cached results. Returns count deleted."""
        if not self.cache_dir.exists():
            return 0

        count = 0
        for json_file in self.cache_dir.rglob("*.json"):
            json_file.unlink()
            count += 1

        # Clean up empty shard directories
        for d in sorted(self.cache_dir.iterdir(), reverse=True):
            if d.is_dir():
                try:
                    d.rmdir()  # Only works if empty
                except OSError:
                    pass

        return count

    @staticmethod
    def content_hash(content: str, model: str, prompt_version: str) -> str:
        """SHA-256 hash combining content, model, and prompt version."""
        combined = f"{content}|{model}|{prompt_version}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _path_for(self, h: str) -> Path:
        """Get the cache file path for a hash (sharded by first 2 chars)."""
        return self.cache_dir / h[:2] / f"{h}.json"
