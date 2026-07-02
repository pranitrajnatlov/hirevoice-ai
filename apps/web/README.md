# HireVoice Web (Next.js 15)

Premium AI-native frontend — candidate interview room + recruiter dashboard.
Dark-luxury theme, Tailwind + Framer Motion, Web Audio voice visualization.

## Run

```bash
cd apps/web
npm install            # Next 15, React 19, framer-motion, recharts, wavesurfer.js
cp .env.example .env.local
npm run dev            # http://localhost:3000
```

Requires the API gateway running on :8000 (see `services/gateway`) and the AI service on :8800
(see `services/ai`). The Next.js rewrite proxies `/api/v1/*` → gateway.

## Key screens

| Route | Screen |
|---|---|
| `/` | Landing |
| `/login` | Recruiter sign-in (JWT + OAuth buttons) |
| `/dashboard` | Recruiter overview — KPIs, score trend, skill radar, hiring funnel |
| `/interview/[token]` | **Candidate interview room** — AI avatar (idle/speaking/listening/thinking), live waveform, hold-to-speak mic, live transcript, live AI analysis |

## Structure

- `components/interview/*` — AiAvatar, VoiceWaveform, MicButton, QuestionCard, LiveTranscript, AnalysisPanel, ProgressRing
- `components/dashboard/*` — KpiCard, Sidebar, Charts (Recharts)
- `lib/api.ts` — typed gateway client · `lib/audio/recorder.ts` — MediaRecorder wrapper
- Design tokens in `tailwind.config.ts` + `app/globals.css`

## Next (Phase 3b)

- WebSocket wiring (`transcript:partial`, `ai:audio` streaming TTS, `score:update`) — currently
  the room uses request/response per turn and animates scores client-side.
- wavesurfer.js for AI audio playback scrubbing; OAuth callback routes; candidate detail page.
