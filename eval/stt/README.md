# STT Accuracy Evaluation

A batch harness that runs the HireVoice speech-to-text pipeline (`app/stt.py` → faster-whisper)
over labeled audio clips and reports **WER / CER** per accent and per pipeline mode.

Use it to measure transcription accuracy across accents and to quantify how much the
**vocabulary boosting** and **context-aware post-processing** (the accent-robustness work)
actually help.

## Setup

```bash
pip install -r eval/stt/requirements.txt        # adds jiwer
```

## Quick start

A synthetic smoke clip is included so it runs out of the box:

```bash
.venv/bin/python eval/stt/run_eval.py --verbose
```

## Add your own clips

1. Drop audio (`.wav` or `.mp3`, ~5–15s each, aim for ~10 per accent) into `eval/stt/dataset/clips/`.
2. Add one line per clip to `eval/stt/dataset/manifest.jsonl` (paths are relative to the dataset folder):

```jsonl
{"audio": "clips/in_001.wav", "reference": "I built a Kafka based microservice", "accent": "indian", "vocabulary": ["Kafka", "microservice"]}
{"audio": "clips/us_001.wav", "reference": "we deployed it on Kubernetes with Terraform", "accent": "american", "vocabulary": ["Kubernetes", "Terraform"]}
```

- **`reference`** — the exact, verbatim transcript (ground truth).
- **`accent`** — any label; known ones sort Indian-first in the report:
  `indian, american, british, australian, canadian, irish, singaporean, middle_eastern, african`.
- **`vocabulary`** — optional per-clip terms (skills/companies/projects) used for hotword
  biasing and post-correction; mirrors what a real interview supplies from the résumé.

Then re-run `run_eval.py`.

## Pipeline modes

Each clip is transcribed in three modes so you can isolate each layer's contribution:

| Mode | What it measures |
|---|---|
| `baseline` | raw faster-whisper, no vocabulary, no post-processing |
| `vocab` | `transcribe_detailed()` with the clip's vocabulary (hotword biasing) |
| `vocab+post` | `vocab` + `transcript_processing.post_process` (alias / phonetic correction) |

## Model sweep

The single biggest accuracy lever. Compare model sizes without code changes:

```bash
.venv/bin/python eval/stt/run_eval.py --model small.en          # default
.venv/bin/python eval/stt/run_eval.py --model large-v3-turbo    # most accurate, slower
.venv/bin/python eval/stt/run_eval.py --model base.en           # fastest
```

## Output

A WER table + CER table (per accent, with an `ALL` row), a one-line pipeline-gain summary,
and a full `eval/stt/results.json` with per-clip hypotheses and scores.

```
WER (Word Error Rate — lower is better)
  accent             n     baseline        vocab   vocab+post
  -----------------------------------------------------------
  ALL                1         0.0%         0.0%         7.1%
  synthetic          1         0.0%         0.0%         7.1%
```

## Interpreting results

- **WER** (Word Error Rate) is the headline metric — fraction of words wrong (substitutions +
  insertions + deletions). **CER** is the same at the character level (catches near-misses).
  Both are computed after normalization (lowercase, punctuation stripped).
- **Expected pattern on accented audio:** `baseline` ≥ `vocab` ≥ `vocab+post` (boosting +
  correction recover misheard technical terms). The gains show up precisely where Whisper
  mangles a résumé term that's in the clip's vocabulary.
- **Caveat — canonicalization vs verbatim:** post-processing normalizes tech terms to canonical
  forms (e.g. `microservice` → `Microservices`, `tensaflow` → `TensorFlow`). Against a strictly
  verbatim reference this can *raise* WER even though it's semantically more correct (this is why
  the clean smoke clip shows `vocab+post` at 7%). If you want post-processing fully credited,
  write references using canonical tech spellings, or read CER alongside WER.
- **Accent priority:** Indian English is the top-priority accent and sorts first in the report.
