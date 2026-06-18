"""Tests for the resource management layer."""

import gc
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.resource_manager import (
    ModelType,
    ResourceManager,
    cleanup_all,
    get_memory_usage,
    get_resource_manager,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    ResourceManager._instance = None
    yield
    ResourceManager._instance = None


class TestResourceManager:
    def test_singleton(self):
        rm1 = get_resource_manager()
        rm2 = get_resource_manager()
        assert rm1 is rm2

    def test_lazy_load(self):
        rm = get_resource_manager()
        mock_instance = MagicMock()
        load_fn = MagicMock(return_value=mock_instance)
        unload_fn = MagicMock()

        rm.register(ModelType.STT, load_fn, unload_fn)
        assert not rm.is_loaded(ModelType.STT)

        result = rm.load(ModelType.STT)
        assert result is mock_instance
        assert rm.is_loaded(ModelType.STT)
        load_fn.assert_called_once()

        # Second load should not call load_fn again
        rm.load(ModelType.STT)
        load_fn.assert_called_once()

    def test_unload(self):
        rm = get_resource_manager()
        mock_instance = MagicMock()
        rm.register(ModelType.LLM, MagicMock(return_value=mock_instance), MagicMock())

        rm.load(ModelType.LLM)
        rm.unload(ModelType.LLM)
        assert not rm.is_loaded(ModelType.LLM)

    def test_cleanup_all(self):
        rm = get_resource_manager()
        for mt in ModelType:
            rm.register(mt, MagicMock(return_value=MagicMock()), MagicMock())
            rm.load(mt)

        with patch("utils.resource_manager._stop_ollama_model", return_value="stopped"):
            summary = rm.cleanup_all()

        assert not rm.get_loaded_models()
        assert "Cleanup complete" in summary

    def test_interview_lifecycle_triggers_cleanup(self):
        rm = get_resource_manager()
        rm.register(ModelType.STT, MagicMock(return_value=MagicMock()), MagicMock())
        rm.load(ModelType.STT)

        with patch.object(rm, "cleanup_all", return_value="done") as mock_cleanup:
            rm.set_interview_active(True)
            mock_cleanup.assert_not_called()

            rm.set_interview_active(False)
            mock_cleanup.assert_called_once()

    def test_get_loaded_models(self):
        rm = get_resource_manager()
        rm.register(ModelType.TTS, MagicMock(return_value="voice"), MagicMock())
        rm.load(ModelType.TTS)
        assert "tts" in rm.get_loaded_models()

    def test_audio_buffer_tracking(self):
        rm = get_resource_manager()
        rm.track_audio_buffer("/tmp/test.wav")
        rm.track_audio_buffer("/tmp/test2.wav")
        assert len(rm._audio_buffers) == 2
        rm.clear_audio_buffers()
        assert len(rm._audio_buffers) == 0


class TestMemoryUsage:
    def test_get_memory_usage_returns_snapshot(self):
        mem = get_memory_usage()
        assert mem.process_rss_gb >= 0
        assert mem.system_total_gb > 0
        assert 0 <= mem.system_percent <= 100

    def test_snapshot_display(self):
        mem = get_memory_usage()
        mem.loaded_models = ["stt", "llm"]
        display = mem.to_display()
        assert "Process RAM" in display
        assert "stt" in display


class TestCleanupAll:
    def test_module_level_cleanup(self):
        rm = get_resource_manager()
        rm.register(ModelType.STT, MagicMock(return_value=MagicMock()), MagicMock())
        rm.load(ModelType.STT)

        with patch("utils.resource_manager._stop_ollama_model", return_value=None):
            result = cleanup_all()
        assert "Cleanup complete" in result