"""
Provider registry — wires concrete implementations behind the Protocols in base.py.

The default implementations delegate to the EXISTING, UNCHANGED app/ modules, which
already branch local<->openai via HIREVOICE_MODE. Adding Claude/Gemini/ElevenLabs later
means adding a class here — no change to interview or assessment logic.
"""

from __future__ import annotations

from app import llm, stt, tts  # existing AI core — reused, not rewritten


class AppLLM:
    """LLMProvider backed by app/llm.py (Ollama local or OpenAI, per config)."""
    def chat(self, messages, *, temperature=0.7, max_tokens=512) -> str:
        return llm.chat(messages, temperature=temperature, max_tokens=max_tokens)


class AppSTT:
    """STTProvider backed by app/stt.py (faster-whisper local or OpenAI Whisper)."""
    def transcribe(self, audio_path, *, language="en") -> str:
        return stt.transcribe(audio_path, language=language)


class AppTTS:
    """TTSProvider backed by app/tts.py (Piper local or OpenAI TTS)."""
    def synthesize(self, text) -> str:
        return tts.synthesize(text)


class ProviderRegistry:
    def __init__(self) -> None:
        self.llm = AppLLM()
        self.stt = AppSTT()
        self.tts = AppTTS()


# Singleton used by routers. Swap implementations here (or via settings) to change vendors.
PROVIDERS = ProviderRegistry()
