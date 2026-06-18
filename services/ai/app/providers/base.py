"""
Provider abstraction (deliverable #11).

Protocols that decouple application logic from concrete model vendors. The existing
`app/llm.py`, `app/stt.py`, `app/tts.py` already toggle local<->openai internally; the
registry generalizes that into a swappable provider set so models can change without
touching interview/assessment logic.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    def chat(self, messages: list[dict], *, temperature: float = 0.7, max_tokens: int = 512) -> str: ...


@runtime_checkable
class STTProvider(Protocol):
    def transcribe(self, audio_path: str, *, language: str = "en") -> str: ...


@runtime_checkable
class TTSProvider(Protocol):
    def synthesize(self, text: str) -> str:  # returns path to audio file
        ...
