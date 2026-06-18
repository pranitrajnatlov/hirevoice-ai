"""
Resource Manager — lazy loading and automatic unloading of AI models.

Core principle: models are loaded on first use and released when idle or
after an interview ends. Nothing stays in memory unless actively needed.
"""

from __future__ import annotations

import gc
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import psutil

from app.config import (
    AUTO_UNLOAD_MODELS,
    IDLE_UNLOAD_SECONDS,
    LLM_MODEL,
    MAX_RAM_USAGE_GB,
    OLLAMA_HOST,
    is_local_mode,
)

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"


@dataclass
class ModelState:
    loaded: bool = False
    last_used: float = 0.0
    instance: Any = None
    load_fn: Optional[Callable[[], Any]] = None
    unload_fn: Optional[Callable[[Any], None]] = None


@dataclass
class MemorySnapshot:
    process_rss_gb: float
    system_used_gb: float
    system_total_gb: float
    system_percent: float
    loaded_models: list[str] = field(default_factory=list)

    def to_display(self) -> str:
        lines = [
            f"Process RAM: {self.process_rss_gb:.2f} GB",
            f"System RAM:  {self.system_used_gb:.1f} / {self.system_total_gb:.1f} GB "
            f"({self.system_percent:.0f}%)",
        ]
        if self.loaded_models:
            lines.append(f"Loaded: {', '.join(self.loaded_models)}")
        else:
            lines.append("Loaded: (none)")
        return "\n".join(lines)


class ResourceManager:
    """
    Singleton that tracks model lifecycle across STT, LLM, and TTS.

    Usage:
        rm = get_resource_manager()
        rm.register(ModelType.STT, load_fn=..., unload_fn=...)
        model = rm.load(ModelType.STT)   # lazy
        rm.unload(ModelType.STT)         # explicit
        rm.cleanup_all()                 # after interview
    """

    _instance: Optional["ResourceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ResourceManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._states: dict[ModelType, ModelState] = {
            t: ModelState() for t in ModelType
        }
        self._audio_buffers: list[Any] = []
        self._idle_timer: Optional[threading.Timer] = None
        self._interview_active = False
        self._initialized = True
        logger.info("ResourceManager initialized (auto_unload=%s)", AUTO_UNLOAD_MODELS)

    # ── Registration ───────────────────────────────────────────────────────

    def register(
        self,
        model_type: ModelType,
        load_fn: Callable[[], Any],
        unload_fn: Callable[[Any], None],
    ) -> None:
        state = self._states[model_type]
        state.load_fn = load_fn
        state.unload_fn = unload_fn

    # ── Load / Unload ──────────────────────────────────────────────────────

    def load(self, model_type: ModelType) -> Any:
        """Lazy-load a model. Returns the loaded instance."""
        state = self._states[model_type]
        if state.loaded and state.instance is not None:
            state.last_used = time.time()
            return state.instance

        if state.load_fn is None:
            raise RuntimeError(f"No load function registered for {model_type.value}")

        logger.info("Loading %s model...", model_type.value)
        mem_before = get_memory_usage()
        state.instance = state.load_fn()
        state.loaded = True
        state.last_used = time.time()
        mem_after = get_memory_usage()
        logger.info(
            "Loaded %s (process RAM: %.2f → %.2f GB)",
            model_type.value,
            mem_before.process_rss_gb,
            mem_after.process_rss_gb,
        )
        self._cancel_idle_timer()
        return state.instance

    def unload(self, model_type: ModelType) -> None:
        """Unload a single model and free memory."""
        state = self._states[model_type]
        if not state.loaded:
            return

        logger.info("Unloading %s model...", model_type.value)
        if state.unload_fn and state.instance is not None:
            try:
                state.unload_fn(state.instance)
            except Exception as exc:
                logger.warning("Error unloading %s: %s", model_type.value, exc)

        state.instance = None
        state.loaded = False
        gc.collect()
        logger.info("Unloaded %s", model_type.value)

    def is_loaded(self, model_type: ModelType) -> bool:
        return self._states[model_type].loaded

    def touch(self, model_type: ModelType) -> None:
        """Mark a model as recently used (resets idle timer)."""
        if self._states[model_type].loaded:
            self._states[model_type].last_used = time.time()

    # ── Interview lifecycle ──────────────────────────────────────────────────

    def set_interview_active(self, active: bool) -> Optional[str]:
        """Set interview state. Returns cleanup summary when deactivating with auto-unload."""
        self._interview_active = active
        if active:
            self._cancel_idle_timer()
            return None
        if AUTO_UNLOAD_MODELS:
            return self.cleanup_all()
        return None

    def cleanup_all(self) -> str:
        """
        Full cleanup after interview ends or manual trigger.
        Returns a human-readable summary.
        """
        actions: list[str] = []

        for model_type in ModelType:
            if self.is_loaded(model_type):
                self.unload(model_type)
                actions.append(f"Unloaded {model_type.value}")

        if is_local_mode():
            ollama_result = _stop_ollama_model(LLM_MODEL)
            if ollama_result:
                actions.append(ollama_result)

        buffer_count = len(self._audio_buffers)
        self._audio_buffers.clear()
        if buffer_count:
            actions.append(f"Cleared {buffer_count} audio buffer(s)")

        gc.collect()
        mem = get_memory_usage()
        actions.append(f"Process RAM now: {mem.process_rss_gb:.2f} GB")

        summary = "Cleanup complete:\n" + "\n".join(f"  • {a}" for a in actions)
        logger.info(summary)
        return summary

    # ── Audio buffer tracking ────────────────────────────────────────────────

    def track_audio_buffer(self, buf: Any) -> None:
        self._audio_buffers.append(buf)

    def clear_audio_buffers(self) -> None:
        self._audio_buffers.clear()

    # ── Idle watchdog ────────────────────────────────────────────────────────

    def start_idle_watchdog(self) -> None:
        """Schedule automatic unload if models sit idle."""
        if not AUTO_UNLOAD_MODELS or self._interview_active:
            return
        self._schedule_idle_check()

    def _schedule_idle_check(self) -> None:
        self._cancel_idle_timer()
        self._idle_timer = threading.Timer(
            float(IDLE_UNLOAD_SECONDS), self._on_idle_timeout
        )
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _cancel_idle_timer(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _on_idle_timeout(self) -> None:
        if self._interview_active:
            return
        now = time.time()
        for model_type, state in self._states.items():
            if state.loaded and (now - state.last_used) >= IDLE_UNLOAD_SECONDS:
                logger.info("Idle timeout — unloading %s", model_type.value)
                self.unload(model_type)

    # ── Status ───────────────────────────────────────────────────────────────

    def get_loaded_models(self) -> list[str]:
        return [t.value for t in ModelType if self._states[t].loaded]

    def get_status(self) -> MemorySnapshot:
        mem = get_memory_usage()
        mem.loaded_models = self.get_loaded_models()
        return mem

    def check_ram_limit(self) -> bool:
        """Return True if system RAM is within acceptable limits."""
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        return used_gb <= MAX_RAM_USAGE_GB


# ── Module-level helpers ───────────────────────────────────────────────────

_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    global _manager
    if _manager is None:
        _manager = ResourceManager()
    return _manager


def get_memory_usage() -> MemorySnapshot:
    """Return current RAM usage for process and system."""
    proc = psutil.Process()
    mem = psutil.virtual_memory()
    return MemorySnapshot(
        process_rss_gb=proc.memory_info().rss / (1024 ** 3),
        system_used_gb=mem.used / (1024 ** 3),
        system_total_gb=mem.total / (1024 ** 3),
        system_percent=mem.percent,
    )


def load_llm() -> Any:
    """Convenience: load LLM via resource manager."""
    from app.llm import _load_llm_instance

    rm = get_resource_manager()
    if not rm._states[ModelType.LLM].load_fn:
        rm.register(ModelType.LLM, _load_llm_instance, _unload_llm_instance)
    return rm.load(ModelType.LLM)


def unload_llm() -> None:
    rm = get_resource_manager()
    rm.unload(ModelType.LLM)
    if is_local_mode():
        _stop_ollama_model(LLM_MODEL)


def cleanup_all() -> str:
    return get_resource_manager().cleanup_all()


def _unload_llm_instance(instance: Any) -> None:
    """LLM unload hook — Ollama models live in the Ollama process."""
    if hasattr(instance, "close"):
        instance.close()
    del instance


def _stop_ollama_model(model_name: str) -> Optional[str]:
    """Stop a running Ollama model to free GPU/RAM."""
    try:
        result = subprocess.run(
            ["ollama", "stop", model_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return f"Stopped Ollama model: {model_name}"
        if "not found" in result.stderr.lower() or "not running" in result.stderr.lower():
            return None
        logger.warning("ollama stop stderr: %s", result.stderr)
        return f"ollama stop {model_name}: {result.stderr.strip()}"
    except FileNotFoundError:
        return "Ollama CLI not found — skip stop"
    except subprocess.TimeoutExpired:
        return f"ollama stop {model_name}: timed out"
    except Exception as exc:
        logger.warning("Failed to stop Ollama model: %s", exc)
        return None


def list_ollama_running_models() -> list[str]:
    """Query Ollama for currently loaded models."""
    try:
        import urllib.request
        import json

        url = f"{OLLAMA_HOST.rstrip('/')}/api/ps"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m.get("name", m.get("model", "?")) for m in data.get("models", [])]
    except Exception:
        return []