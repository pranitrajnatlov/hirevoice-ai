"""
Text-to-Speech wrapper with lazy loading via ResourceManager.

Local mode: piper-tts (lightweight ONNX)
OpenAI mode: OpenAI TTS API (Phase 4)
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Union

from app.config import (
    AUDIO_DIR,
    PIPER_CONFIG_URL,
    PIPER_MODELS_DIR,
    PIPER_VOICE,
    PIPER_VOICE_URL,
    SAMPLE_RATE,
    is_openai_mode,
    ensure_dirs,
)
from utils.resource_manager import ModelType, get_resource_manager

logger = logging.getLogger(__name__)

_piper_voice = None


def _download_piper_model() -> tuple[Path, Path]:
    """Download piper voice model via huggingface_hub if not present."""
    ensure_dirs()

    # Check both flat (legacy) and hf_hub subdirectory layouts
    flat_onnx = PIPER_MODELS_DIR / f"{PIPER_VOICE}.onnx"
    flat_json = PIPER_MODELS_DIR / f"{PIPER_VOICE}.onnx.json"
    if flat_onnx.exists() and flat_json.exists():
        return flat_onnx, flat_json

    # Use huggingface_hub — handles auth, retries, and LFS redirects correctly
    hf_filename_onnx = f"en/en_US/lessac/medium/{PIPER_VOICE}.onnx"
    hf_filename_json = f"en/en_US/lessac/medium/{PIPER_VOICE}.onnx.json"

    try:
        from huggingface_hub import hf_hub_download
        logger.info("Downloading piper voice via HuggingFace Hub: %s", PIPER_VOICE)
        onnx_path = Path(hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=hf_filename_onnx,
            local_dir=str(PIPER_MODELS_DIR),
        ))
        json_path = Path(hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=hf_filename_json,
            local_dir=str(PIPER_MODELS_DIR),
        ))
    except Exception as exc:
        # Fallback: direct URL download (may fail behind restrictive proxies)
        logger.warning("hf_hub_download failed (%s) — trying direct URL", exc)
        onnx_path = flat_onnx
        json_path = flat_json
        if not onnx_path.exists():
            urllib.request.urlretrieve(PIPER_VOICE_URL, onnx_path)
        if not json_path.exists():
            urllib.request.urlretrieve(PIPER_CONFIG_URL, json_path)

    return onnx_path, json_path


def _load_piper_instance():
    """Load piper voice (called by ResourceManager)."""
    global _piper_voice
    onnx_path, json_path = _download_piper_model()

    try:
        from piper import PiperVoice
        _piper_voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
        logger.info("Piper voice loaded: %s", PIPER_VOICE)
        return _piper_voice
    except ImportError:
        logger.info("piper-tts Python pkg not found — using CLI fallback")
        return {"mode": "cli", "onnx": onnx_path, "json": json_path}


def _unload_piper_instance(instance) -> None:
    global _piper_voice
    _piper_voice = None
    del instance


def _ensure_registered() -> None:
    rm = get_resource_manager()
    if not rm._states[ModelType.TTS].load_fn:
        rm.register(ModelType.TTS, _load_piper_instance, _unload_piper_instance)


def synthesize(
    text: str,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Convert text to speech audio file.

    Args:
        text: Text to speak.
        output_path: Optional output .wav path. Auto-generated if None.

    Returns:
        Path to the generated .wav file.
    """
    if not text.strip():
        raise ValueError("Empty text for TTS")

    if is_openai_mode():
        return _synthesize_openai(text, output_path)

    _ensure_registered()
    rm = get_resource_manager()
    voice = rm.load(ModelType.TTS)
    rm.touch(ModelType.TTS)

    ensure_dirs()
    if output_path is None:
        output_path = AUDIO_DIR / f"tts_{hash(text) & 0xFFFFFFFF:08x}.wav"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(voice, dict) and voice.get("mode") == "cli":
        _synthesize_piper_cli(text, voice["onnx"], output_path)
    else:
        _synthesize_piper_python(text, voice, output_path)

    rm.track_audio_buffer(output_path)
    logger.info("TTS output: %s (%.0f chars)", output_path, len(text))
    return str(output_path)


def _synthesize_piper_python(text: str, voice, output_path: Path) -> None:
    import wave

    with wave.open(str(output_path), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)


def _synthesize_piper_cli(text: str, onnx_path: Path, output_path: Path) -> None:
    """Fallback using piper CLI if Python package unavailable."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text)
        text_path = f.name

    try:
        subprocess.run(
            ["piper", "--model", str(onnx_path), "--output_file", str(output_path)],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
            check=True,
        )
    except FileNotFoundError:
        _synthesize_fallback_beep(text, output_path)
    except subprocess.CalledProcessError as exc:
        logger.warning("piper CLI failed: %s — using fallback", exc.stderr)
        _synthesize_fallback_beep(text, output_path)
    finally:
        Path(text_path).unlink(missing_ok=True)


def _synthesize_fallback_beep(text: str, output_path: Path) -> None:
    """Generate a short silent WAV as last-resort fallback."""
    import numpy as np
    import soundfile as sf

    duration = min(len(text) * 0.05, 10.0)
    samples = int(SAMPLE_RATE * duration)
    silence = np.zeros(samples, dtype=np.float32)
    sf.write(str(output_path), silence, SAMPLE_RATE)
    logger.warning("TTS fallback: silent audio (install piper-tts)")


def _synthesize_openai(text: str, output_path: Optional[Union[str, Path]]) -> str:
    from openai import OpenAI
    from app.config import OPENAI_TTS_VOICE, get_openai_key

    key = get_openai_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set — enter it in the Settings tab")

    ensure_dirs()
    if output_path is None:
        output_path = AUDIO_DIR / f"tts_openai_{hash(text) & 0xFFFFFFFF:08x}.mp3"
    output_path = Path(output_path)

    client = OpenAI(api_key=key)
    response = client.audio.speech.create(
        model="tts-1-hd",
        voice=OPENAI_TTS_VOICE,
        input=text,
    )
    response.stream_to_file(str(output_path))
    logger.info("OpenAI TTS output: %s", output_path)
    return str(output_path)


def unload() -> None:
    get_resource_manager().unload(ModelType.TTS)