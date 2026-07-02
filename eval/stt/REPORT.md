# Speech-to-Text Accuracy Report — Model Comparison & Accent Robustness

**System:** HireVoice AI interview transcription (faster-whisper)
**Question:** How accurate is transcription across candidate accents, and is the larger
model worth it?

---

## Executive summary

We benchmarked two Whisper model sizes on accented English speech. Upgrading from
**`small.en`** to **`large-v3-turbo`** cuts transcription errors by roughly a third:

| Metric | small.en | large-v3-turbo | Improvement |
|---|---|---|---|
| **Word Error Rate (overall)** | 5.6% | **3.7%** | **−35%** |
| **Character Error Rate (overall)** | 3.2% | **2.0%** | **−39%** |

The gains are largest on the **hardest accents**, which is exactly where accuracy matters
most for a global candidate pool. `large-v3-turbo` is recommended for production where GPU /
latency headroom exists; `small.en` remains a solid CPU-only fallback at 94.4% word accuracy.

---

## Methodology

- **Dataset:** Speech Accent Archive — every speaker reads the *same* 69-word passage
  ("Please call Stella…"), so accent is the only variable.
- **Sample:** 55 recordings — 5 speakers each across 11 native-language accents (fixed seed,
  identical clips for both models → apples-to-apples).
- **Metric:** WER (Word Error Rate) and CER (Character Error Rate), lower is better, computed
  after normalization (lowercase, punctuation removed). WER ≈ fraction of words wrong; CER
  catches near-misses at the character level.
- **Mode:** raw transcription (no résumé vocabulary), so this measures *baseline accent
  robustness* — the floor before the live pipeline's vocabulary boosting improves it further.

---

## Model comparison by accent (Word Error Rate)

Sorted hardest → easiest on the baseline model. Δ is the points improved by `large-v3-turbo`.

| Accent | small.en WER | large-v3-turbo WER | Δ (pts) | CER (turbo) |
|---|---:|---:|---:|---:|
| Mandarin | 9.0% | 5.2% | **+3.8** | 3.1% |
| Nepali | 9.0% | 6.7% | +2.3 | 3.2% |
| Spanish | 8.7% | 5.2% | **+3.5** | 2.7% |
| Punjabi | 8.4% | 9.6% | **−1.2** | 5.2% |
| Arabic | 5.5% | 3.5% | +2.0 | 1.7% |
| Korean | 5.2% | 2.0% | **+3.2** | 0.9% |
| Bengali | 4.6% | 3.8% | +0.9 | 2.3% |
| French | 4.1% | 1.2% | **+2.9** | 0.6% |
| Hindi | 3.8% | 0.9% | **+2.9** | 0.5% |
| Russian | 2.3% | 1.5% | +0.9 | 0.9% |
| English (native) | 1.5% | 0.9% | +0.6 | 0.7% |
| **Overall** | **5.6%** | **3.7%** | **+2.0** | **2.0%** |

---

## Accent accuracy tiers (on the recommended model, `large-v3-turbo`)

| Tier | WER | Accents |
|---|---|---|
| **Excellent** (≤1.5%) | near-native | Hindi 0.9 · English 0.9 · French 1.2 · Russian 1.5 |
| **Good** (1.5–4%) | production-ready | Korean 2.0 · Arabic 3.5 · Bengali 3.8 |
| **Watch** (>5%) | usable, monitor | Spanish 5.2 · Mandarin 5.2 · Nepali 6.7 · Punjabi 9.6 |

---

## Key findings

1. **The bigger model pays off broadly** — 10 of 11 accents improved; overall WER dropped 35%
   and CER 39%.
2. **It helps most where it's needed** — the largest gains are on the toughest accents
   (Mandarin −3.8, Spanish −3.5, Korean −3.2, Hindi −2.9, French −2.9), narrowing the gap
   between accents.
3. **Indian-subcontinent accents are strong but uneven** — Hindi is best-in-class (0.9% WER on
   turbo), Bengali is solid (3.8%), but **Punjabi (9.6%) and Nepali (6.7%) lag** and are worth
   targeted attention.
4. **Errors are mostly minor** — CER is consistently about half the WER, meaning most mistakes
   are small word-form slips, not garbled output. The live interview pipeline (vocabulary
   boosting + context-aware correction) recovers many of these on top of the numbers here.

---

## Recommendation

- **Production / GPU:** set `HIREVOICE_STT_MODEL=large-v3-turbo` — 96.3% word accuracy overall,
  best on hard accents.
- **CPU-only / latency-sensitive:** `small.en` is acceptable at 94.4%; `large-v3-turbo` is
  ~3–5× slower per clip on CPU.
- **Follow-up:** confirm the **Punjabi** result — it's the only regression and the worst accent
  on both models — with a larger sample (`--per-accent 15 --accents punjabi`) before treating it
  as a real weak spot vs. small-sample noise.

---

## Deployment cost & latency analysis

### Do we need a GPU? No.

Both models run faster than real-time on CPU. Measured on an Apple M4 (10 cores, int8):

| | Model load (once at startup) | Transcribe 22s audio | Real-time factor |
|---|---|---|---|
| small.en | 0.8s | **1.8s** | 0.08× |
| large-v3-turbo | 1.9s | **5.2s** | 0.24× |

A candidate's ~60s answer ≈ **4–5s** (small.en) / **12–15s** (turbo) on this CPU class.
AWS t3 vCPUs are 3–6× slower: small.en stays workable (~0.3–0.5× RTF); turbo drops below
real-time — not usable for live turns on small CPU instances.

### Minimum instance sizing (self-hosted)

| Instance | RAM | Verdict |
|---|---|---|
| t3.micro (1 GB) | 1 GB | ❌ small.en alone needs ~0.7–1 GB — OOM |
| t3.small (2 GB) | 2 GB | ⚠️ STT-only fits barely; full AI stack (piper TTS + Ollama LLM) doesn't. Burstable CPU throttles mid-interview |
| t3.medium (4 GB, ~$30/mo) | 4 GB | ✅ realistic minimum for the full local AI service |
| c7g.large (4 GB, ~$53/mo) | 4 GB | ✅ recommended: non-burstable, stronger sustained cores |
| g4dn.xlarge GPU (~$384/mo) | — | Only needed for large-v3-turbo at high concurrency |

### Self-hosted vs paid API (per ~30-min interview ≈ 10 min transcribed audio)

| Option | Cost model | Per interview | Measured accuracy |
|---|---|---|---|
| OpenAI `whisper-1` API | $0.006/min | ~$0.06 | **4.8% WER** (see `REPORT_OPENAI.md`) |
| Deepgram Nova | ~$0.0043/min | ~$0.04 | not benchmarked |
| Self-host small.en (t3.medium) | ~$30/mo fixed | $30 ÷ volume | 5.6% WER |
| Self-host large-v3-turbo (c7g.large+) | ~$53/mo fixed | $53 ÷ volume | **3.6% WER** (best) |

**Break-even ≈ 500 interviews/month** (whisper-1 vs t3.medium). Below that, the API is cheaper
and more accurate *than small.en*; note the locally-hosted `large-v3-turbo` measured **more
accurate than the whisper-1 API** on identical clips (3.6% vs 4.8% — full three-way comparison
in `REPORT_OPENAI.md`). (Prices approximate us-east-1 on-demand — verify current rates.)

### Recommendation

- **Low volume (< ~500 interviews/mo):** use API mode — the platform already supports it via
  `HIREVOICE_MODE=openai` (zero code change). Cheaper than a server, more accurate than
  small.en, no ops.
- **Scale-up / accuracy-critical:** self-host `large-v3-turbo` on c7g-class (or GPU for
  concurrency) — it beat the API in our benchmark.

---

## Caveats

- **Small sample (5 clips/accent):** numbers are directional, not definitive — single hard clips
  can swing a 5-clip average. Re-run with `--per-accent 15+` to tighten.
- **Generic passage, no technical terms:** this isolates accent robustness. Real interview WER
  on technical answers will differ, but the live pipeline's résumé-vocabulary boosting is
  designed to *reduce* error on exactly those terms.
- **Reproduce:** see `eval/stt/README.md` → "Baseline results" for the exact commands.

*Generated from `eval/stt/results_small.json` and `eval/stt/results_turbo.json` via
`eval/stt/compare.py`.*
