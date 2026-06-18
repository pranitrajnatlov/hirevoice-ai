# HireVoice AI

AI-powered voice interview system optimized for **MacBook Air M4** (16–24 GB RAM). Models load on demand and unload automatically when interviews end.

## Quick Start

```bash
# 1. Clone / enter project
cd hirevoice-ai

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install & start Ollama (local LLM)
brew install ollama        # or https://ollama.com
ollama serve               # in a separate terminal
ollama pull llama3.2:11b   # default model (~7 GB)

# 5. Run
python -m app.main
# Open http://localhost:7860
```

## Architecture

```
hirevoice-ai/
├── app/
│   ├── config.py           # All settings (mode, models, RAM limits)
│   ├── interviewer.py      # Interview state machine + voice loop
│   ├── stt.py              # faster-whisper (lazy loaded)
│   ├── llm.py              # Ollama API (with unload support)
│   ├── tts.py              # piper-tts (lazy loaded)
│   ├── assessment.py       # Structured assessment (Phase 3)
│   └── resume_integration.py
├── ui/
│   └── gradio_app.py       # Gradio UI with mic + cleanup button
├── utils/
│   └── resource_manager.py # ★ Core: load/unload/cleanup
└── prompts/
    ├── interviewer_system.txt
    └── assessment_system.txt
```

## Resource Management

The `ResourceManager` singleton is the heart of the system:

| Function | What it does |
|---|---|
| `load(ModelType)` | Lazy-loads STT/LLM/TTS on first use |
| `unload(ModelType)` | Releases a single model from memory |
| `cleanup_all()` | Unloads all models, stops Ollama, clears audio buffers |
| `get_memory_usage()` | Returns process + system RAM snapshot |
| `set_interview_active()` | Triggers auto-cleanup when interview ends |

Models are **never** loaded at startup. They load when you click "Start Interview" or submit audio, and unload when the interview ends or you click "Cleanup Resources".

### Manual Cleanup

```bash
# Stop a specific Ollama model
ollama stop llama3.2:11b

# List running Ollama models
ollama ps

# Or use the "Cleanup Resources" button in the UI
```

## Configuration

Edit `app/config.py` or set environment variables:

```bash
export HIREVOICE_MODE=local          # or "openai"
export HIREVOICE_LLM_MODEL=llama3.2:11b
export HIREVOICE_STT_MODEL=large-v3-turbo
export HIREVOICE_AUTO_UNLOAD=true
export HIREVOICE_MAX_RAM_GB=14
```

## Model Recommendations by RAM

| RAM | LLM | STT | Est. Storage | Est. Peak RAM |
|---|---|---|---|---|
| 16 GB | `llama3.2:11b` (Q4) | `large-v3-turbo` (int8) | ~12 GB | ~10 GB |
| 16 GB (tight) | `qwen2.5:7b` (Q4) | `medium` (int8) | ~8 GB | ~7 GB |
| 24 GB+ | `qwen2.5:32b` (Q4_K_M) | `large-v3-turbo` | ~25 GB | ~18 GB |
| 24 GB+ | `llama3.2:11b` + larger STT | `large-v3` | ~15 GB | ~12 GB |

**Total storage budget:** aim for 35–40 GB including Ollama models, Whisper weights, and piper voice (~50 MB).

### Pull only what you need

```bash
# Minimal (16 GB MacBook Air)
ollama pull llama3.2:11b

# Better quality (24 GB+)
ollama pull qwen2.5:32b
```

## Switching to OpenAI Mode

```bash
export HIREVOICE_MODE=openai
export OPENAI_API_KEY=sk-...
python -m app.main
```

Uses OpenAI Whisper + GPT-4o + OpenAI TTS. No local models loaded.

## Development Phases

- [x] **Phase 1** — Resource-efficient foundation (lazy loading, cleanup, voice loop)
- [ ] **Phase 2** — Interview logic + resume context
- [ ] **Phase 3** — Assessment generator + Resume AI integration
- [ ] **Phase 4** — Full OpenAI fallback mode

## License

MIT