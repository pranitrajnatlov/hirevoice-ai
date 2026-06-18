"""
Speech-to-Text wrapper with lazy loading via ResourceManager.

Local mode: faster-whisper
OpenAI mode: OpenAI Whisper API (Phase 4)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional, Union

from app.config import (
    SAMPLE_RATE,
    STT_BEAM_SIZE,
    STT_COMPUTE_TYPE,
    STT_DEVICE,
    STT_MODEL_SIZE,
    is_local_mode,
    is_openai_mode,
)
from utils.resource_manager import ModelType, get_resource_manager

logger = logging.getLogger(__name__)

_whisper_model = None


def _resolve_device() -> str:
    if STT_DEVICE != "auto":
        return STT_DEVICE
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _load_whisper_instance():
    """Load faster-whisper model (called by ResourceManager)."""
    global _whisper_model
    from faster_whisper import WhisperModel

    device = _resolve_device()
    compute = STT_COMPUTE_TYPE if device == "cpu" else "float16"
    logger.info(
        "Initializing faster-whisper '%s' on %s (%s)",
        STT_MODEL_SIZE, device, compute,
    )
    _whisper_model = WhisperModel(
        STT_MODEL_SIZE,
        device=device,
        compute_type=compute,
    )
    return _whisper_model


def _unload_whisper_instance(model) -> None:
    global _whisper_model
    _whisper_model = None
    del model


def _ensure_registered() -> None:
    rm = get_resource_manager()
    if not rm._states[ModelType.STT].load_fn:
        rm.register(ModelType.STT, _load_whisper_instance, _unload_whisper_instance)


def warm() -> None:
    """Pre-load the STT model so the first answer doesn't pay load/download latency mid-interview."""
    if is_openai_mode():
        return
    _ensure_registered()
    get_resource_manager().load(ModelType.STT)
    logger.info("STT model '%s' pre-warmed", STT_MODEL_SIZE)


def transcribe(
    audio: Union[str, Path, tuple, object],
    language: Optional[str] = "en",
) -> str:
    """
    Transcribe audio to text.

    Args:
        audio: File path, numpy array, or (sample_rate, ndarray) tuple from Gradio.
        language: ISO language code or None for auto-detect.

    Returns:
        Transcribed text string.
    """
    if is_openai_mode():
        return _transcribe_openai(audio)

    _ensure_registered()
    rm = get_resource_manager()
    model = rm.load(ModelType.STT)
    rm.touch(ModelType.STT)

    audio_path = _prepare_audio(audio)

    try:
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=STT_BEAM_SIZE,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("STT result (%s, %.1fs): %s", info.language, info.duration, text[:80])
        return text
    finally:
        if isinstance(audio_path, Path) and audio_path.parent == Path(tempfile.gettempdir()):
            audio_path.unlink(missing_ok=True)


def _prepare_audio(audio: Union[str, Path, "np.ndarray", tuple]) -> Path:
    """Normalize various audio inputs to a file path."""
    import numpy as np
    import soundfile as sf

    if isinstance(audio, (str, Path)):
        return Path(audio)

    if isinstance(audio, tuple) and len(audio) == 2:
        sr, data = audio
    else:
        sr, data = SAMPLE_RATE, audio

    if data is None or (hasattr(data, "__len__") and len(data) == 0):
        raise ValueError("Empty audio input")

    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim > 1:
        arr = arr.mean(axis=1)

    # Gradio mic returns int16 values (-32768..32767); normalize to [-1, 1].
    # soundfile clips out-of-range float32 to [-1, 1] which destroys the signal.
    if arr.max() > 1.0 or arr.min() < -1.0:
        arr = arr / 32768.0

    tmp = Path(tempfile.mktemp(suffix=".wav"))
    sf.write(str(tmp), arr, int(sr))
    get_resource_manager().track_audio_buffer(tmp)
    return tmp


def _transcribe_openai(audio) -> str:
    """OpenAI Whisper API transcription."""
    from openai import OpenAI
    from app.config import OPENAI_STT_MODEL, get_openai_key

    key = get_openai_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set — enter it in the Settings tab")

    client = OpenAI(api_key=key)
    audio_path = _prepare_audio(audio)

    try:
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=OPENAI_STT_MODEL,
                file=f,
                language="en",
            )
        logger.info("OpenAI STT result: %s", result.text[:80])
        return result.text
    finally:
        if isinstance(audio_path, Path) and audio_path.parent == Path(tempfile.gettempdir()):
            audio_path.unlink(missing_ok=True)


def unload() -> None:
    get_resource_manager().unload(ModelType.STT)