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


@runtime_checkable
class ResumeParserProvider(Protocol):
    """Structured resume parsing (spec #1-6). Returns the schema dict from spec #2."""
    def parse(self, source: str, *, is_text: bool = False) -> dict: ...


@runtime_checkable
class TranscriptProcessorProvider(Protocol):
    """Transcript clean-up + context-aware correction (spec #10, #11)."""
    def process(self, text: str, *, vocabulary=None, history: str = "", job_description: str = "") -> dict: ...


@runtime_checkable
class StreamingSTTProvider(Protocol):
    """
    Real-time partial transcription (spec #7).

    Local faster-whisper is a batch model, so the default implementation approximates
    streaming by re-transcribing the accumulated audio buffer. A cloud provider
    (e.g. Deepgram) implementing this Protocol drops in for true sub-500ms partials
    with no caller changes (spec #18).
    """
    def transcribe_chunk(self, audio_path: str, *, vocabulary=None) -> dict: ...
