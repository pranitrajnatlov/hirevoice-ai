"""
Provider registry — wires concrete implementations behind the Protocols in base.py.

The default implementations delegate to the EXISTING, UNCHANGED app/ modules, which
already branch local<->openai via HIREVOICE_MODE. Adding Claude/Gemini/ElevenLabs later
means adding a class here — no change to interview or assessment logic.
"""

from __future__ import annotations

from app import llm, resume_parser, stt, transcript_processing, tts  # existing AI core — reused, not rewritten


class AppLLM:
    """LLMProvider backed by app/llm.py (Ollama local or OpenAI, per config)."""
    def chat(self, messages, *, temperature=0.7, max_tokens=512) -> str:
        return llm.chat(messages, temperature=temperature, max_tokens=max_tokens)


class AppSTT:
    """STTProvider backed by app/stt.py (faster-whisper local or OpenAI Whisper)."""
    def transcribe(self, audio_path, *, language="en") -> str:
        return stt.transcribe(audio_path, language=language)

    def transcribe_detailed(self, audio_path, *, vocabulary=None, language="en"):
        """Word timestamps + per-word confidence + vocabulary boosting (spec #7-9)."""
        return stt.transcribe_detailed(audio_path, vocabulary=vocabulary, language=language)


class AppTTS:
    """TTSProvider backed by app/tts.py (Piper local or OpenAI TTS)."""
    def synthesize(self, text) -> str:
        return tts.synthesize(text)


class AppResumeParser:
    """ResumeParserProvider backed by app/resume_parser.py (deterministic, no LLM)."""
    def parse(self, source, *, is_text=False) -> dict:
        return resume_parser.parse_resume(source, is_text=is_text)


class AppTranscriptProcessor:
    """TranscriptProcessorProvider backed by app/transcript_processing.py."""
    def process(self, text, *, vocabulary=None, history="", job_description="") -> dict:
        return transcript_processing.post_process(
            text, vocabulary=vocabulary, history=history, job_description=job_description
        )


class AppStreamingSTT:
    """
    StreamingSTTProvider — approximates streaming by re-transcribing the accumulated
    buffer with vocabulary boosting. Swap for Deepgram/cloud later (spec #18).
    """
    def transcribe_chunk(self, audio_path, *, vocabulary=None) -> dict:
        res = stt.transcribe_detailed(audio_path, vocabulary=vocabulary)
        return {"text": res.text, "confidence": res.avg_confidence}


class ProviderRegistry:
    def __init__(self) -> None:
        self.llm = AppLLM()
        self.stt = AppSTT()
        self.tts = AppTTS()
        self.resume = AppResumeParser()
        self.transcript = AppTranscriptProcessor()
        self.streaming_stt = AppStreamingSTT()


# Singleton used by routers. Swap implementations here (or via settings) to change vendors.
PROVIDERS = ProviderRegistry()
