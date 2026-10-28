from __future__ import annotations

import json
import os
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import MetricsResponse

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "requests.jsonl"


def new_monitoring_id() -> str:
    return uuid.uuid4().hex[:12]


def log_event(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_events(limit: int | None = None) -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    if limit:
        lines = lines[-limit:]
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def get_metrics() -> MetricsResponse:
    events = _read_events()
    total = len(events)
    blocked = sum(1 for e in events if e.get("blocked"))
    failed = sum(1 for e in events if e.get("status") == "error")
    latencies = [float(e.get("latency_ms", 0)) for e in events if e.get("latency_ms") is not None]
    papers = [int(e.get("papers_returned", 0)) for e in events if e.get("papers_returned") is not None]
    return MetricsResponse(
        total_requests=total,
        blocked_requests=blocked,
        failed_requests=failed,
        average_latency_ms=round(statistics.mean(latencies), 2) if latencies else 0.0,
        average_papers_returned=round(statistics.mean(papers), 2) if papers else 0.0,
        recent_requests=_read_events(limit=10),
    )
