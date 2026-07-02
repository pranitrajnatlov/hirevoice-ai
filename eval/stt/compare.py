#!/usr/bin/env python
"""
Compare two STT eval result files (from run_eval.py --out) side by side.

Usage:
    .venv/bin/python eval/stt/compare.py eval/stt/results_small.json eval/stt/results_turbo.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ACCENT_ORDER = ["indian", "american", "british", "australian", "canadian", "irish",
                 "singaporean", "middle_eastern", "african"]


def _key(a: str):
    return (_ACCENT_ORDER.index(a) if a in _ACCENT_ORDER else len(_ACCENT_ORDER), a)


def _wer(per_accent: dict, accent: str) -> float | None:
    node = per_accent.get(accent, {})
    base = node.get("baseline") or {}
    return base.get("wer")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: compare.py <results_a.json> <results_b.json>")
    a = json.loads(Path(sys.argv[1]).read_text())
    b = json.loads(Path(sys.argv[2]).read_text())
    la, lb = a.get("model", "A"), b.get("model", "B")

    accents = sorted(set(a["per_accent"]) | set(b["per_accent"]), key=_key)
    print(f"\nWER comparison · {la}  vs  {lb}   (baseline; lower is better)\n")
    print(f"  {'accent':<14}{la:>16}{lb:>16}{'Δ (pts)':>12}")
    print("  " + "-" * 56)

    def row(name, wa, wb):
        sa = f"{wa*100:.1f}%" if wa is not None else "—"
        sb = f"{wb*100:.1f}%" if wb is not None else "—"
        delta = f"{(wa-wb)*100:+.1f}" if (wa is not None and wb is not None) else "—"
        print(f"  {name:<14}{sa:>16}{sb:>16}{delta:>12}")

    for acc in accents:
        if acc == "ALL":
            continue
        row(acc, _wer(a["per_accent"], acc), _wer(b["per_accent"], acc))
    print("  " + "-" * 56)
    row("ALL", (a.get("overall", {}).get("baseline") or {}).get("wer"),
        (b.get("overall", {}).get("baseline") or {}).get("wer"))
    print("\n  Δ is positive when the second model is more accurate.")


if __name__ == "__main__":
    main()
