"""Optional, provider-independent narrative enrichment.

The simulation never depends on this module. It is only used by explicit
user-triggered endpoints, so a missing API key or a slow provider can never
stall a run.
"""
from __future__ import annotations

import time

import httpx

from .config import settings


class LLMUnavailable(RuntimeError):
    pass


_last_calls: list[float] = []


def status() -> dict[str, object]:
    return {
        "enabled": settings.llm_enabled,
        "configured": settings.llm_active,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "mode": "manual narrative enrichment only",
        "affects_simulation": False,
        "calls_last_minute": len(_recent_calls()),
    }


def _recent_calls() -> list[float]:
    cutoff = time.monotonic() - 60.0
    while _last_calls and _last_calls[0] < cutoff:
        _last_calls.pop(0)
    return _last_calls


async def generate_chronicle(context: dict, kind: str = "summary") -> str:
    if not settings.llm_active:
        raise LLMUnavailable("LLM narrative is disabled. Set CIVITAS_LLM_ENABLED and CIVITAS_LLM_API_KEY.")
    if len(_recent_calls()) >= max(1, settings.llm_max_calls_per_minute):
        raise LLMUnavailable("LLM rate limit reached; try again in a minute.")

    style = {
        "summary": "Write a concise historical summary in 3 short paragraphs.",
        "dramatic": "Write an evocative chronicle in 3 short paragraphs. Stay factual to the supplied data.",
        "neutral": "Write a neutral observer's report in 3 short paragraphs.",
    }.get(kind, "Write a concise historical summary.")
    system = (
        "You are the chronicler of a simulated civilization. Use ONLY the supplied facts. "
        "Do not invent people, battles, technologies, numbers or outcomes that are not present. "
        "If the record is sparse, say so. Avoid purple prose and never claim certainty beyond the data."
    )
    user = f"{style}\n\nSIMULATION RECORD:\n{context}"

    _last_calls.append(time.monotonic())
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "temperature": 0.6,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the caller
        raise LLMUnavailable(f"LLM request failed: {exc}") from exc
