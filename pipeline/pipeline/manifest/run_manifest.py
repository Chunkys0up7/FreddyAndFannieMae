"""Per-run JSON manifest of pipeline execution."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RunManifest:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: str = ""
    tracks: list[str] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_result(self, track: str, payload: Any) -> None:
        self.tracks.append(track)
        self.results[track] = payload

    def add_error(self, track: str, exc: Exception) -> None:
        self.errors.append(
            {"track": track, "error": str(exc), "type": type(exc).__name__}
        )

    def finalize(self, manifest_dir: Path) -> Path:
        self.finished_at = datetime.utcnow().isoformat()
        manifest_dir.mkdir(parents=True, exist_ok=True)
        out = manifest_dir / f"run-{self.run_id}.json"
        out.write_text(json.dumps(asdict(self), indent=2, default=str))
        return out
