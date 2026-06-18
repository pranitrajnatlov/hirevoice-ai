"""Tests for STT audio preprocessing — specifically the int16 normalization bug."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf


class TestPrepareAudio:
    """Verify _prepare_audio normalizes mic input correctly before writing to WAV."""

    def test_int16_mic_input_normalized_to_float_range(self, tmp_path):
        """Gradio mic returns int16 values; they must be divided by 32768 before sf.write."""
        from app.stt import _prepare_audio

        # Simulate Gradio mic: int16 values in typical speech range
        sr = 16000
        int16_data = (np.random.randn(sr) * 8000).astype(np.int16)
        audio_tuple = (sr, int16_data)

        path = _prepare_audio(audio_tuple)
        audio_back, _ = sf.read(str(path), dtype="float32")

        assert audio_back.max() <= 1.0, f"Audio max {audio_back.max():.4f} exceeds 1.0 — not normalized"
        assert audio_back.min() >= -1.0, f"Audio min {audio_back.min():.4f} below -1.0 — not normalized"
        # Signal should not be a flat line (clipped to ±1)
        unique_vals = np.unique(np.round(audio_back, 2))
        assert len(unique_vals) > 10, "Audio looks clipped (square wave) — normalization not applied"
        path.unlink(missing_ok=True)

    def test_already_normalized_float_passthrough(self, tmp_path):
        """Float32 input already in [-1, 1] must not be scaled again."""
        from app.stt import _prepare_audio

        sr = 16000
        float_data = np.random.randn(sr).astype(np.float32) * 0.3  # already in range
        audio_tuple = (sr, float_data)

        path = _prepare_audio(audio_tuple)
        audio_back, _ = sf.read(str(path), dtype="float32")

        assert audio_back.max() <= 1.0
        assert audio_back.min() >= -1.0
        path.unlink(missing_ok=True)

    def test_empty_audio_raises(self):
        from app.stt import _prepare_audio

        with pytest.raises(ValueError, match="Empty audio input"):
            _prepare_audio((16000, np.array([], dtype=np.int16)))

    def test_stereo_audio_converted_to_mono(self, tmp_path):
        from app.stt import _prepare_audio

        sr = 16000
        stereo = np.random.randn(sr, 2).astype(np.float32) * 0.3
        path = _prepare_audio((sr, stereo))
        audio_back, _ = sf.read(str(path))
        assert audio_back.ndim == 1, "Stereo not converted to mono"
        path.unlink(missing_ok=True)

    def test_file_path_passthrough(self, tmp_path):
        from app.stt import _prepare_audio

        wav = tmp_path / "test.wav"
        sf.write(str(wav), np.zeros(1000, dtype=np.float32), 16000)
        result = _prepare_audio(str(wav))
        assert str(result) == str(wav)
