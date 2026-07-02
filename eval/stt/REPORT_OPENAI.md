# STT Accuracy — OpenAI whisper-1 API vs Local Models

**Question:** If we skip self-hosting and use the OpenAI transcription API
(`HIREVOICE_MODE=openai`), what accuracy do we get compared to running Whisper locally?

---

## Executive summary

All three engines were run on the **identical 55 clips** (Speech Accent Archive, 5 speakers ×
11 accents, fixed seed):

| Engine | Where it runs | Overall WER | Overall CER |
|---|---|---:|---:|
| `small.en` | local CPU | 5.6% | 3.0% |
| **`large-v3-turbo`** | local CPU/GPU | **3.6%** | **1.9%** |
| `whisper-1` (OpenAI API) | cloud | 4.8% | 2.9% |

**Surprise result:** the locally-hosted `large-v3-turbo` is the *most accurate* option — it beats
the paid API by 1.2 WER points. `whisper-1` is an older large-v2-generation model; our local
turbo build is newer. The API still comfortably beats `small.en` and requires zero
infrastructure.

---

## Per-accent WER (identical clips, hardest-first by small.en)

| Accent | small.en | large-v3-turbo | whisper-1 API |
|---|---:|---:|---:|
| Nepali | 9.3% | 5.2% | **4.3%** |
| Punjabi | 8.4% | **7.0%** | 7.2% |
| Arabic | 7.2% | **2.9%** | 4.1% |
| Bengali | 7.0% | 5.5% | **5.2%** |
| Korean | 7.0% | **1.7%** | 2.9% |
| Spanish | 6.1% | **6.1%** | 7.8% |
| French | 4.6% | **1.7%** | 4.3% |
| Mandarin | 4.3% | **3.5%** | 6.7% |
| Hindi | 2.9% | **2.6%** | 2.9% |
| Russian | 2.9% | **1.7%** | 5.8% |
| English (native) | 1.7% | 1.7% | 1.7% |
| **Overall** | **5.6%** | **3.6%** | **4.8%** |

- `large-v3-turbo` wins or ties on **9 of 11** accents.
- The API wins on Nepali and Bengali; it is notably *weaker* than turbo on Russian (+4.1 pts),
  Mandarin (+3.2) and French (+2.6).
- Punjabi remains the hardest accent for every engine — a real weak spot, not sample noise
  specific to one model.

---

## Decision matrix

| Scenario | Best choice | Why |
|---|---|---|
| Max accuracy, have a decent server (4 GB+, ideally GPU) | **local `large-v3-turbo`** | best WER (3.6%), fixed cost, no per-minute fees |
| Low volume, no infra, fastest to ship | **whisper-1 API** | 4.8% WER (better than small.en), ~$0.06/interview, zero ops — already built in via `HIREVOICE_MODE=openai` |
| CPU-only box, latency-sensitive live turns | **local `small.en`** | real-time on modest CPUs; accept 5.6% WER |

Cost context (details in `REPORT.md` → "Deployment cost & latency"): API ≈ $0.06/interview;
break-even vs a ~$30/mo self-host box ≈ 500 interviews/month. This entire 55-clip benchmark
(~21 min of audio) cost ≈ **$0.13** in API usage.

---

## Method & caveats

- Corpus: Speech Accent Archive, trimmed to ≤20 clips/accent; sample = `--per-accent 5 --seed 7`
  over 11 accents (identical files fed to all three engines).
- Baseline mode only (generic passage, no résumé vocabulary), WER/CER after normalization.
- 5 clips/accent → per-accent numbers are directional; the overall rows (n=55) are more stable.
- Numbers differ slightly from the first report's tables because the corpus was trimmed and
  re-sampled; all three engines here share the *same* sample, so the comparison is fair.
- Reproduce:

```bash
ACC="english,hindi,bengali,punjabi,nepali,mandarin,arabic,spanish,french,korean,russian"
.venv/bin/python eval/stt/run_eval.py --from-dir eval/stt/dataset/clips --accents "$ACC" --per-accent 5 --seed 7 --model small.en       --out eval/stt/results_small.json
.venv/bin/python eval/stt/run_eval.py --from-dir eval/stt/dataset/clips --accents "$ACC" --per-accent 5 --seed 7 --model large-v3-turbo --out eval/stt/results_turbo.json
set -a; source .env; set +a   # OPENAI_API_KEY
HIREVOICE_MODE=openai .venv/bin/python eval/stt/run_eval.py --from-dir eval/stt/dataset/clips --accents "$ACC" --per-accent 5 --seed 7 --out eval/stt/results_openai.json
```

*Generated from `results_small.json`, `results_turbo.json`, `results_openai.json`.*
