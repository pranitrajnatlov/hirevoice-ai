"""
LLM wrapper with lazy loading and Ollama unload support.

Local mode: Ollama API (models managed by Ollama process)
OpenAI mode: GPT-4o API (Phase 4)
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import (
    LLM_MODEL,
    OLLAMA_HOST,
    OLLAMA_TIMEOUT,
    OPENAI_API_KEY,
    OPENAI_LLM_MODEL,
    is_local_mode,
    is_openai_mode,
)
from utils.resource_manager import ModelType, get_resource_manager

logger = logging.getLogger(__name__)


@dataclass
class LLMClient:
    """Thin client handle — actual inference goes through HTTP."""
    model: str
    host: str = OLLAMA_HOST
    _warmed: bool = field(default=False, repr=False)

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        if is_openai_mode():
            return _generate_openai(messages, temperature, max_tokens)
        return _generate_ollama(self, messages, temperature, max_tokens)


def _load_llm_instance() -> LLMClient:
    """Create LLM client and optionally warm up the Ollama model."""
    client = LLMClient(model=LLM_MODEL, host=OLLAMA_HOST)
    if is_local_mode():
        _warm_ollama(client)
    return client


def _warm_ollama(client: LLMClient) -> None:
    """Send a tiny prompt to load the model into Ollama's memory."""
    try:
        _generate_ollama(
            client,
            [{"role": "user", "content": "Hi"}],
            temperature=0.0,
            max_tokens=5,
        )
        client._warmed = True
        logger.info("Ollama model '%s' warmed up", client.model)
    except Exception as exc:
        logger.warning("Ollama warm-up failed (will retry on first real call): %s", exc)


def _ensure_registered() -> None:
    rm = get_resource_manager()
    if not rm._states[ModelType.LLM].load_fn:
        from utils.resource_manager import _unload_llm_instance
        rm.register(ModelType.LLM, _load_llm_instance, _unload_llm_instance)


def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> str:
    """
    Send a chat completion request.

    Args:
        messages: OpenAI-style message list [{role, content}, ...].
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.

    Returns:
        Assistant response text.
    """
    _ensure_registered()
    rm = get_resource_manager()
    client = rm.load(ModelType.LLM)
    rm.touch(ModelType.LLM)
    return client.generate(messages, temperature=temperature, max_tokens=max_tokens)


def _generate_ollama(
    client: LLMClient,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    url = f"{client.host.rstrip('/')}/api/chat"
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            result = json.loads(resp.read())
        return result.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama not reachable at {client.host}. "
            f"Is Ollama running? Try: ollama serve\n{exc}"
        ) from exc


def _generate_openai(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    from app.config import OPENAI_LLM_MODEL as _model, get_openai_key
    _key = get_openai_key()
    if not _key:
        raise RuntimeError("OPENAI_API_KEY not set — enter it in the Settings tab")

    from openai import OpenAI

    client = OpenAI(api_key=_key)
    response = client.chat.completions.create(
        model=_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def unload() -> None:
    """Unload LLM client and stop Ollama model."""
    from utils.resource_manager import unload_llm
    unload_llm()


def check_openai_available() -> tuple[bool, str]:
    """Health check for OpenAI API connectivity."""
    from app.config import OPENAI_LLM_MODEL, get_openai_key
    key = get_openai_key()
    if not key:
        return False, "API key not set — enter it in the Settings tab"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        models = client.models.list()
        names = [m.id for m in models.data]
        if OPENAI_LLM_MODEL in names:
            return True, f"OpenAI OK — {OPENAI_LLM_MODEL} available"
        return True, f"OpenAI connected (model: {OPENAI_LLM_MODEL})"
    except Exception as exc:
        return False, f"OpenAI error: {exc}"


def check_ollama_available() -> tuple[bool, str]:
    """Health check for Ollama connectivity."""
    try:
        url = f"{OLLAMA_HOST.rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if any(LLM_MODEL.split(":")[0] in m for m in models):
            return True, f"Ollama OK — {LLM_MODEL} available"
        return False, (
            f"Ollama running but '{LLM_MODEL}' not found. "
            f"Run: ollama pull {LLM_MODEL}"
        )
    except Exception as exc:
        return False, f"Ollama not reachable: {exc}"