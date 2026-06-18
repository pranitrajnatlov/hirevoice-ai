"""
HireVoice AI — Central configuration.

All resource and mode settings live here. Override via environment variables
or edit this file directly.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
PIPER_MODELS_DIR = DATA_DIR / "piper_models"

# ── Mode ───────────────────────────────────────────────────────────────────
# "local"  → faster-whisper + Ollama + piper-tts
# "openai" → OpenAI Whisper + GPT-4o + OpenAI TTS
MODE: str = os.getenv("HIREVOICE_MODE", "local")

# Runtime-mutable mode — use set_mode() / get_mode() instead of reading MODE directly.
_runtime_mode: str = MODE

# ── Local LLM (Ollama) ─────────────────────────────────────────────────────
# Smaller defaults for 16 GB RAM; bump to qwen2.5:32b on 24 GB+ machines.
LLM_MODEL: str = os.getenv("HIREVOICE_LLM_MODEL", "llama3.2:1b")
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ── Local STT (faster-whisper) ─────────────────────────────────────────────
# CTranslate2 is CPU-only on Apple Silicon (no Metal), so model size drives latency.
# Default "small.en": English-optimized, fast on M4, good accuracy for clear speech.
# More accuracy (slower): HIREVOICE_STT_MODEL=large-v3-turbo  ·  Faster: base.en
STT_MODEL_SIZE: str = os.getenv("HIREVOICE_STT_MODEL", "small.en")
STT_DEVICE: str = os.getenv("HIREVOICE_STT_DEVICE", "auto")  # auto | cpu | cuda
STT_COMPUTE_TYPE: str = os.getenv("HIREVOICE_STT_COMPUTE", "int8")
# Greedy decoding (beam_size=1) is ~3x faster than beam search with minimal
# accuracy loss for short interview answers. Bump to 5 for max accuracy.
STT_BEAM_SIZE: int = int(os.getenv("HIREVOICE_STT_BEAM_SIZE", "1"))

# ── Local TTS (piper) ──────────────────────────────────────────────────────
PIPER_VOICE: str = os.getenv(
    "HIREVOICE_PIPER_VOICE", "en_US-lessac-medium"
)
PIPER_VOICE_URL: str = os.getenv(
    "HIREVOICE_PIPER_VOICE_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
)
PIPER_CONFIG_URL: str = os.getenv(
    "HIREVOICE_PIPER_CONFIG_URL",
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
)

# ── OpenAI (Phase 4) ────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_LLM_MODEL: str = os.getenv("OPENAI_LLM_MODEL", "gpt-4o")
OPENAI_TTS_VOICE: str = os.getenv("OPENAI_TTS_VOICE", "nova")
OPENAI_STT_MODEL: str = os.getenv("OPENAI_STT_MODEL", "whisper-1")

# Runtime-mutable OpenAI key (set via UI or env; never logged)
_runtime_openai_key: str = OPENAI_API_KEY

# ── Resource Management ────────────────────────────────────────────────────
AUTO_UNLOAD_MODELS: bool = os.getenv("HIREVOICE_AUTO_UNLOAD", "true").lower() == "true"
MAX_RAM_USAGE_GB: float = float(os.getenv("HIREVOICE_MAX_RAM_GB", "14"))
IDLE_UNLOAD_SECONDS: int = int(os.getenv("HIREVOICE_IDLE_UNLOAD_SEC", "300"))

# ── Interview ──────────────────────────────────────────────────────────────
MAX_INTERVIEW_TURNS: int = int(os.getenv("HIREVOICE_MAX_TURNS", "20"))
SAMPLE_RATE: int = 16_000

# ── UI ─────────────────────────────────────────────────────────────────────
GRADIO_HOST: str = os.getenv("HIREVOICE_HOST", "0.0.0.0")
GRADIO_PORT: int = int(os.getenv("HIREVOICE_PORT", "7860"))
GRADIO_SHARE: bool = os.getenv("HIREVOICE_SHARE", "false").lower() == "true"


def get_openai_key() -> str:
    return _runtime_openai_key


def set_openai_key(key: str) -> None:
    global _runtime_openai_key
    _runtime_openai_key = key.strip()


def get_mode() -> str:
    return _runtime_mode


def set_mode(mode: str) -> None:
    """Switch mode at runtime. Triggers cleanup of local models if switching away from local."""
    global _runtime_mode
    if mode not in ("local", "openai"):
        raise ValueError(f"Invalid mode '{mode}' — must be 'local' or 'openai'")
    _runtime_mode = mode


def is_openai_mode() -> bool:
    return _runtime_mode.lower() == "openai"


def is_local_mode() -> bool:
    return not is_openai_mode()


def ensure_dirs() -> None:
    """Create runtime directories if they don't exist."""
    for d in (DATA_DIR, AUDIO_DIR, PIPER_MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)