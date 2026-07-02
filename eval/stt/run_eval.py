#!/usr/bin/env python
"""
STT accuracy evaluation harness.

Runs the HireVoice STT pipeline over a labeled audio manifest and reports WER/CER,
broken down by accent and by pipeline mode, so you can measure transcription accuracy
across different accents AND quantify how much vocabulary boosting + context-aware
post-processing actually help.

Pipeline modes
--------------
  baseline    : raw faster-whisper, no vocabulary, no post-processing
  vocab       : transcribe_detailed() with the clip's vocabulary (hotword biasing)
  vocab+post  : vocab transcription + transcript_processing.post_process (alias/phonetic fixes)

Manifest (JSON Lines — one clip per line), paths relative to the manifest's folder:
  {"audio": "clips/in_001.wav", "reference": "the exact transcript",
   "accent": "indian", "vocabulary": ["Kafka", "Spring Boot"]}

Usage
-----
  .venv/bin/python eval/stt/run_eval.py
  .venv/bin/python eval/stt/run_eval.py --model large-v3-turbo
  .venv/bin/python eval/stt/run_eval.py --manifest eval/stt/dataset/manifest.jsonl --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

MODES = ["baseline", "vocab", "vocab+post"]
_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")
# Indian English first (highest-priority accent), then the rest, "synthetic"/unknown last.
_ACCENT_ORDER = ["indian", "american", "british", "australian", "canadian", "irish",
                 "singaporean", "middle_eastern", "african"]


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — applied to ref and hyp alike."""
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", (text or "").lower())).strip()


def load_manifest(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            sys.exit(f"Manifest line {i} is not valid JSON: {exc}")
    return rows


def transcribe_modes(audio_path: str, vocabulary: list[str], modes: list[str]) -> dict[str, str]:
    """Transcribe one clip in each requested mode (vocab transcription is computed once)."""
    from app import stt

    # Newer trees expose transcribe_detailed (word timings + hotword biasing); older trees
    # and OpenAI-API mode only need plain transcribe() for baseline WER.
    detailed = getattr(stt, "transcribe_detailed", None)

    def _plain(path: str) -> str:
        if detailed is not None:
            return detailed(path).text
        return stt.transcribe(path)

    out: dict[str, str] = {}
    if "baseline" in modes:
        out["baseline"] = _plain(audio_path)
    if "vocab" in modes or "vocab+post" in modes:
        if detailed is None:
            sys.exit("vocab/vocab+post modes need app.stt.transcribe_detailed (not in this tree) — run with --modes baseline")
        vres = detailed(audio_path, vocabulary=vocabulary or None)
        if "vocab" in modes:
            out["vocab"] = vres.text
        if "vocab+post" in modes:
            from app.transcript_processing import post_process
            out["vocab+post"] = post_process(vres.text, vocabulary=vocabulary or [])["text"]
    return out


_AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm")


def accent_from_filename(stem: str) -> str:
    """Derive an accent label from a filename like 'hindi3' -> 'hindi' (leading letters)."""
    m = re.match(r"([a-zA-Z]+)", stem)
    return m.group(1).lower() if m else "unknown"


def build_rows_from_dir(clips_dir: Path, reference: str, *, per_accent: int | None,
                        accents: list[str] | None, limit: int | None, seed: int) -> list[dict]:
    """
    Build eval rows from a directory of clips that all read the SAME reference passage
    (e.g. the Speech Accent Archive). Accent is taken from the filename prefix. Supports
    per-accent sampling, accent filtering, and a global cap so big corpora stay tractable.
    """
    import random

    files = sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in _AUDIO_EXTS)
    by_accent: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        by_accent[accent_from_filename(f.stem)].append(f)

    if accents:
        wanted = {a.lower() for a in accents}
        by_accent = {a: fs for a, fs in by_accent.items() if a in wanted}

    rng = random.Random(seed)
    rows: list[dict] = []
    for accent in sorted(by_accent.keys(), key=_accent_sort_key):
        clips = by_accent[accent]
        if per_accent and len(clips) > per_accent:
            clips = rng.sample(clips, per_accent)
        for c in sorted(clips):
            rows.append({"audio": str(c.resolve()), "reference": reference, "accent": accent, "vocabulary": []})
    if limit:
        rows = rows[:limit]
    return rows


def _accent_sort_key(accent: str):
    a = accent.lower()
    return (_ACCENT_ORDER.index(a) if a in _ACCENT_ORDER else len(_ACCENT_ORDER), a)


def _fmt_pct(x: float | None) -> str:
    return f"{x * 100:5.1f}%" if x is not None else "   —  "


def print_table(title: str, metric: str, per_accent: dict, modes: list[str]) -> None:
    accents = sorted(per_accent.keys(), key=_accent_sort_key)
    print(f"\n{title}")
    header = f"  {'accent':<16}{'n':>4}  " + "  ".join(f"{m:>11}" for m in modes)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for acc in accents:
        cells = []
        n = 0
        for m in modes:
            vals = per_accent[acc].get(m, [])
            n = max(n, len(vals))
            cells.append(_fmt_pct(mean(vals) if vals else None))
        print(f"  {acc:<16}{n:>4}  " + "  ".join(f"{c:>11}" for c in cells))


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate STT accuracy (WER/CER) per accent and pipeline mode.")
    ap.add_argument("--manifest", default=str(_REPO_ROOT / "eval/stt/dataset/manifest.jsonl"))
    ap.add_argument("--from-dir", help="Directory of clips that all read the same passage "
                                       "(accent inferred from filename). Bypasses --manifest.")
    ap.add_argument("--reference-file", default=str(_REPO_ROOT / "eval/stt/dataset/reading-passage.txt"),
                    help="Reference transcript file used by every clip in --from-dir.")
    ap.add_argument("--per-accent", type=int, help="Cap clips sampled per accent (keeps big corpora fast).")
    ap.add_argument("--accents", help="Comma-separated accent filter, e.g. english,hindi,bengali,arabic.")
    ap.add_argument("--limit", type=int, help="Global cap on total clips after sampling.")
    ap.add_argument("--seed", type=int, default=42, help="Sampling seed.")
    ap.add_argument("--model", help="Override HIREVOICE_STT_MODEL (e.g. small.en, base.en, large-v3-turbo).")
    ap.add_argument("--modes", nargs="+", default=None, choices=MODES)
    ap.add_argument("--out", default=str(_REPO_ROOT / "eval/stt/results.json"))
    ap.add_argument("--verbose", action="store_true", help="Print per-clip WER.")
    args = ap.parse_args()

    # Model override must be set before app.config is imported (it reads env at import).
    if args.model:
        os.environ["HIREVOICE_STT_MODEL"] = args.model

    import jiwer  # imported after arg parsing so --help is instant

    if args.from_dir:
        clips_dir = Path(args.from_dir).resolve()
        if not clips_dir.is_dir():
            sys.exit(f"--from-dir not found: {clips_dir}")
        ref_path = Path(args.reference_file).resolve()
        if not ref_path.exists():
            sys.exit(f"--reference-file not found: {ref_path}")
        reference = ref_path.read_text(encoding="utf-8").strip()
        rows = build_rows_from_dir(
            clips_dir, reference,
            per_accent=args.per_accent,
            accents=[a.strip() for a in args.accents.split(",")] if args.accents else None,
            limit=args.limit, seed=args.seed,
        )
        base_dir = Path("/")  # rows carry absolute audio paths
    else:
        manifest_path = Path(args.manifest).resolve()
        if not manifest_path.exists():
            sys.exit(f"Manifest not found: {manifest_path}")
        base_dir = manifest_path.parent
        rows = load_manifest(manifest_path)
    if not rows:
        sys.exit("No clips to evaluate.")

    # No per-clip vocabulary (e.g. a generic reading passage) makes vocab/vocab+post identical
    # to baseline — default to baseline-only unless the user explicitly chose modes.
    has_vocab = any(r.get("vocabulary") for r in rows)
    modes = args.modes or (MODES if has_vocab else ["baseline"])

    # Label results by what actually transcribes: the local whisper size, or the API model
    # when HIREVOICE_MODE=openai routes STT to OpenAI.
    if os.getenv("HIREVOICE_MODE", "local") == "openai":
        model_name = os.getenv("OPENAI_STT_MODEL", "whisper-1") + " (OpenAI API)"
    else:
        model_name = os.getenv("HIREVOICE_STT_MODEL", "small.en")
    print(f"Evaluating {len(rows)} clip(s) · model={model_name} · modes={modes}")

    wer_acc: dict = defaultdict(lambda: defaultdict(list))
    cer_acc: dict = defaultdict(lambda: defaultdict(list))
    wer_all: dict = defaultdict(list)
    cer_all: dict = defaultdict(list)
    detail = []

    for row in rows:
        ref = row.get("reference", "")
        accent = row.get("accent", "unknown")
        audio = (base_dir / row["audio"]).resolve()
        if not audio.exists():
            print(f"  ! missing audio, skipping: {audio}")
            continue
        ref_n = normalize(ref)
        if not ref_n:
            print(f"  ! empty reference, skipping: {row['audio']}")
            continue

        hyps = transcribe_modes(str(audio), row.get("vocabulary") or [], modes)
        clip = {"audio": row["audio"], "accent": accent, "reference": ref, "modes": {}}
        line_bits = []
        for m in modes:
            hyp_n = normalize(hyps.get(m, ""))
            wer = jiwer.wer(ref_n, hyp_n)
            cer = jiwer.cer(ref_n, hyp_n)
            wer_acc[accent][m].append(wer)
            cer_acc[accent][m].append(cer)
            wer_all[m].append(wer)
            cer_all[m].append(cer)
            clip["modes"][m] = {"hypothesis": hyps.get(m, ""), "wer": round(wer, 4), "cer": round(cer, 4)}
            line_bits.append(f"{m}={wer*100:.0f}%")
        detail.append(clip)
        if args.verbose:
            print(f"  [{accent}] {row['audio']}: " + "  ".join(line_bits))

    # Add an "ALL" row aggregating across accents.
    for m in modes:
        wer_acc["ALL"][m] = wer_all[m]
        cer_acc["ALL"][m] = cer_all[m]

    print_table("WER (Word Error Rate — lower is better)", "wer", wer_acc, modes)
    print_table("CER (Character Error Rate — lower is better)", "cer", cer_acc, modes)

    summary = {
        "model": model_name,
        "modes": modes,
        "clips": len(detail),
        "overall": {m: {"wer": round(mean(wer_all[m]), 4) if wer_all[m] else None,
                        "cer": round(mean(cer_all[m]), 4) if cer_all[m] else None} for m in modes},
        "per_accent": {
            acc: {m: {"wer": round(mean(wer_acc[acc][m]), 4) if wer_acc[acc][m] else None,
                      "cer": round(mean(cer_acc[acc][m]), 4) if cer_acc[acc][m] else None}
                  for m in modes}
            for acc in wer_acc
        },
        "clips_detail": detail,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote detailed results → {args.out}")

    if len(modes) > 1 and wer_all.get(modes[0]) and wer_all.get(modes[-1]):
        base, best = mean(wer_all[modes[0]]), mean(wer_all[modes[-1]])
        delta = (base - best) * 100
        print(f"Pipeline gain: {modes[0]} {base*100:.1f}% WER → {modes[-1]} {best*100:.1f}% WER "
              f"({delta:+.1f} pts)")


if __name__ == "__main__":
    main()
