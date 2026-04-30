"""Bulletin metadata lookup via the pipeline REST API."""
from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import AgentConfig


log = logging.getLogger(__name__)


def list_recent_bulletins(
    cfg: AgentConfig, agency: Optional[str] = None, days: int = 90
) -> list[dict]:
    params: dict = {"days": days}
    if agency:
        params["agency"] = agency
    try:
        r = requests.get(f"{cfg.pipeline_api_url}/bulletins", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("list_recent_bulletins failed: %s", exc)
        return []


def get_bulletin(cfg: AgentConfig, bulletin_id: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"{cfg.pipeline_api_url}/bulletins/{bulletin_id}", timeout=10
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("get_bulletin(%s) failed: %s", bulletin_id, exc)
        return None
