# HireVoice AI

AI-powered voice interview platform optimized for **MacBook Air M4** (16–24 GB RAM).
Recruiters create interview links, candidates join from the browser, and a local AI conducts the full interview — voice-to-voice — with resume-aware adaptive questioning.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (Next.js)                        │
│   Recruiter dashboard · Candidate interview room · Analytics    │
│              localhost:3000  →  /api/v1/* proxy                 │
└───────────────────────┬──────────────────────────────────────────┘
                        │  HTTP + WebSocket
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                         │
│   Auth (JWT) · Interview CRUD · Session lifecycle · WS hub      │
│   Meeting links · Analytics · TTS proxy                         │
│              localhost:8000  /api/v1/*                           │
└───────────────────────┬──────────────────────────────────────────┘
                        │  Internal HTTP
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                     AI Service (FastAPI)                         │
│   Resume parsing · Interview turn gen · STT · TTS · Assessment  │
│              localhost:8800  /ai/*                               │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
                ┌──────────────┐
                │  Ollama LLM  │
                │  localhost:   │
                │    11434      │
                └──────────────┘
```

### Project Structure

```
hirevoice-ai/
├── apps/web/                    # Next.js 15 recruiter + candidate frontend
│   ├── app/(auth)/              #   Login / register pages
│   ├── app/(recruiter)/         #   Dashboard, interviews, analytics
│   ├── app/interview/           #   Candidate interview room
│   ├── components/              #   Reusable UI components
│   └── lib/api.ts               #   Typed API client
│
├── services/gateway/            # FastAPI API gateway (port 8000)
│   └── app/
│       ├── api/v1/              #   REST routers (auth, interviews, sessions, …)
│       ├── ws/                  #   WebSocket manager (live transcript)
│       ├── security.py          #   JWT + PBKDF2 password hashing
│       ├── models.py            #   SQLAlchemy models
│       └── config.py            #   Gateway settings (pydantic-settings)
│
├── services/ai/                 # FastAPI AI service (port 8800)
│   └── app/
│       ├── main.py              #   Resume analysis, turn gen, STT, TTS, assessment
│       └── providers/           #   Pluggable AI backends (Ollama / OpenAI)
│
├── app/                         # Core AI logic (shared by AI service + Gradio)
│   ├── config.py                #   Mode selection, model names, RAM limits
│   ├── interviewer.py           #   Interview state machine
│   ├── stt.py                   #   faster-whisper (lazy loaded)
│   ├── llm.py                   #   Ollama API wrapper
│   ├── tts.py                   #   piper-tts (lazy loaded)
│   ├── assessment.py            #   Structured scoring + hiring recommendation
│   └── resume_integration.py    #   Resume text extraction
│
├── ui/gradio_app.py             # Gradio UI (standalone dev mode)
├── utils/resource_manager.py    # Model load/unload/cleanup singleton
├── prompts/                     # System prompt templates
├── tests/                       # pytest suite
├── data/                        # Runtime data (audio, sessions, piper models)
└── requirements.txt             # Core AI dependencies
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **Ollama** (local LLM) — [https://ollama.com](https://ollama.com)

### 1. Clone & enter project

```bash
git clone <your-repo-url>
cd hirevoice-ai
```

### 2. Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate

# Install all Python dependencies
pip install -r requirements.txt
pip install -r services/gateway/requirements.txt
pip install -r services/ai/requirements.txt
```

### 3. Install & start Ollama

```bash
brew install ollama            # or download from https://ollama.com
ollama serve                   # keep this running in a separate terminal
ollama pull llama3.2:11b       # default model (~7 GB download)
```

### 4. Start all three services

Open **three terminal tabs** (all from the repo root, each with the venv activated):

```bash
# Terminal 1 — API Gateway (port 8000)
source .venv/bin/activate
uvicorn services.gateway.app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — AI Service (port 8800)
source .venv/bin/activate
uvicorn services.ai.app.main:app --host 0.0.0.0 --port 8800 --reload

# Terminal 3 — Next.js Web App (port 3000)
cd apps/web
npm install        # first time only
npm run dev
```

### 5. Open the app

- **Recruiter dashboard:** [http://localhost:3000](http://localhost:3000)
- **Register** a recruiter account, then **create an interview** → share the meeting link with a candidate.

### Standalone Gradio Mode (optional)

For quick local testing without the full stack:

```bash
source .venv/bin/activate
python -m app.main
# Open http://localhost:7860
```

---

## Environment Variables

### Gateway (`services/gateway/`)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./hirevoice.db` | DB connection (SQLite for dev, Postgres for prod) |
| `JWT_SECRET` | `dev-secret-change-me` | **Change in production** |
| `ACCESS_TOKEN_TTL_MIN` | `720` (12 hours) | JWT access token lifetime |
| `AI_SERVICE_URL` | `http://localhost:8800` | Where the gateway finds the AI service |
| `MEETING_LINK_BASE` | `http://localhost:3000/interview` | Base URL for candidate meeting links |

### Web App (`apps/web/`)

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_URL` | `http://localhost:8000` | Gateway URL for Next.js API proxy |
| `NEXT_PUBLIC_API_URL` | _(empty = same-origin)_ | Client-side API base (leave empty for dev) |

Copy `apps/web/.env.example` to `apps/web/.env.local` and adjust as needed.

### AI Core (`app/`)

| Variable | Default | Description |
|---|---|---|
| `HIREVOICE_MODE` | `local` | `local` or `openai` |
| `HIREVOICE_LLM_MODEL` | `llama3.2:11b` | Ollama model name |
| `HIREVOICE_STT_MODEL` | `large-v3-turbo` | faster-whisper model |
| `HIREVOICE_AUTO_UNLOAD` | `true` | Unload models after interview ends |
| `HIREVOICE_MAX_RAM_GB` | `14` | RAM ceiling for model loading |
| `OPENAI_API_KEY` | — | Required if `HIREVOICE_MODE=openai` |

---

## Authentication & Sessions

The gateway issues **JWT access tokens** (default TTL: 12 hours for dev). When a token expires:

1. The API returns **401 Unauthorized**
2. The frontend API client detects the 401, clears `localStorage`, and redirects to `/login?expired=1`
3. The login page displays a **"Your session expired"** banner

> **Note:** If you see "Failed to create interview" errors after a long session, it's likely an expired JWT — the app will auto-redirect you to re-login.

---

## Resource Management

The `ResourceManager` singleton manages AI model lifecycle:

| Function | What it does |
|---|---|
| `load(ModelType)` | Lazy-loads STT / LLM / TTS on first use |
| `unload(ModelType)` | Releases a single model from memory |
| `cleanup_all()` | Unloads all models, stops Ollama, clears audio buffers |
| `get_memory_usage()` | Returns process + system RAM snapshot |
| `set_interview_active()` | Triggers auto-cleanup when interview ends |

Models are **never** loaded at startup. They load on demand and unload when the interview ends.

### Manual Cleanup

```bash
ollama stop llama3.2:11b    # stop a specific model
ollama ps                   # list running models
```

---

## Model Recommendations by RAM

| RAM | LLM | STT | Est. Storage | Est. Peak RAM |
|---|---|---|---|---|
| 16 GB | `llama3.2:11b` (Q4) | `large-v3-turbo` (int8) | ~12 GB | ~10 GB |
| 16 GB (tight) | `qwen2.5:7b` (Q4) | `medium` (int8) | ~8 GB | ~7 GB |
| 24 GB+ | `qwen2.5:32b` (Q4_K_M) | `large-v3-turbo` | ~25 GB | ~18 GB |
| 24 GB+ | `llama3.2:11b` + larger STT | `large-v3` | ~15 GB | ~12 GB |

**Total storage budget:** ~35–40 GB including Ollama models, Whisper weights, and piper voice (~50 MB).

```bash
# Pull models
ollama pull llama3.2:11b       # 16 GB MacBook
ollama pull qwen2.5:32b        # 24 GB+ MacBook
```

---

## Switching to OpenAI Mode

```bash
export HIREVOICE_MODE=openai
export OPENAI_API_KEY=sk-...
```

Uses OpenAI Whisper + GPT-4o + OpenAI TTS. No local models loaded.

---

## API Endpoints

### Gateway (port 8000)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Gateway health check |
| `GET` | `/health/ai` | Gateway + AI service health |
| `POST` | `/api/v1/auth/register` | Register recruiter account |
| `POST` | `/api/v1/auth/login` | Login → JWT access token |
| `GET` | `/api/v1/auth/me` | Current user info |
| `GET` | `/api/v1/interviews` | List recruiter's interviews |
| `POST` | `/api/v1/interviews` | Create interview + meeting link |
| `GET` | `/api/v1/interviews/:id` | Interview detail |
| `GET` | `/api/v1/interviews/:id/transcript` | Full transcript |
| `GET` | `/api/v1/interviews/:id/ai-context` | Parsed resume + strategy |
| `GET` | `/api/v1/meeting/:token` | Validate meeting link |
| `POST` | `/api/v1/sessions/:token/start` | Start candidate session |
| `POST` | `/api/v1/sessions/:id/answer` | Submit audio answer |
| `GET` | `/api/v1/analytics/overview` | Recruiter analytics |
| `WS` | `/api/v1/ws/:id` | Live transcript events |
| `WS` | `/api/v1/ws/stt/:id` | Streaming STT |

### AI Service (port 8800)

| Method | Path | Description |
|---|---|---|
| `GET` | `/ai/health` | AI service health |
| `POST` | `/ai/resume/analyze` | Parse resume → structured profile |
| `POST` | `/ai/interview/turn` | Generate next interview question |
| `POST` | `/ai/stt/transcribe` | Transcribe audio (with vocabulary boost) |
| `POST` | `/ai/tts/synthesize` | Text-to-speech → WAV file |
| `POST` | `/ai/assess` | Score interview + hiring recommendation |

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| "Failed to create interview" | JWT expired (401) | App auto-redirects to login; sign in again |
| `ModuleNotFoundError: gradio` | venv not activated | `source .venv/bin/activate` |
| Gateway won't start | Missing deps | `pip install -r services/gateway/requirements.txt` |
| AI service errors | Missing deps | `pip install -r services/ai/requirements.txt -r requirements.txt` |
| `Connection refused` on interview create | AI service not running | Start it: `uvicorn services.ai.app.main:app --port 8800` |
| Ollama model slow to respond | First inference, model loading | Wait ~30s for initial load; subsequent calls are fast |
| "Invalid token" errors | Clock skew or wrong secret | Ensure `JWT_SECRET` matches across restarts |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## Development Phases

- [x] **Phase 1** — Resource-efficient foundation (lazy loading, cleanup, voice loop)
- [x] **Phase 2** — Full-stack web platform (Next.js + Gateway + AI service)
- [x] **Phase 3** — Resume AI, adaptive interviews, structured assessment
- [ ] **Phase 4** — OpenAI fallback mode, production hardening

---

## License

MIT