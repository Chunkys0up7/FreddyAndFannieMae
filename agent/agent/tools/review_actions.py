"""Review actions executed against the pipeline REST API."""
from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import AgentConfig


log = logging.getLogger(__name__)


def flag_for_review(
    cfg: AgentConfig,
    section_number: str,
    agency: str,
    reason: str,
    severity: str = "medium",
    reviewer: Optional[str] = None,
) -> dict:
    payload = {
        "section_number": section_number,
        "agency": agency,
        "reason": reason,
        "severity": severity,
    }
    if reviewer:
        payload["reviewer"] = reviewer
    r = requests.post(f"{cfg.pipeline_api_url}/reviews/flag", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def mark_reviewed(
    cfg: AgentConfig,
    section_number: str,
    notes: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> dict:
    payload: dict = {"section_number": section_number}
    if notes:
        payload["notes"] = notes
    if reviewer:
        payload["reviewer"] = reviewer
    r = requests.post(
        f"{cfg.pipeline_api_url}/reviews/mark-reviewed", json=payload, timeout=10
    )
    r.raise_for_status()
    return r.json()


def create_gap_note(
    cfg: AgentConfig,
    section_number: str,
    agency: str,
    current_sop: str,
    change: str,
    recommendation: str,
) -> dict:
    payload = {
        "section_number": section_number,
        "agency": agency,
        "current_sop": current_sop,
        "change": change,
        "recommendation": recommendation,
    }
    r = requests.post(
        f"{cfg.pipeline_api_url}/reviews/gap-note", json=payload, timeout=10
    )
    r.raise_for_status()
    return r.json()
