"""
Transcript post-processing & context-aware correction (spec #10, #11).

Deterministic, no model dependency. Three correction tiers, safest first:

1. Alias normalization — map known technology aliases/misspellings to canonical
   form (``tensaflow``->TensorFlow, ``springboot``->Spring Boot). Always safe:
   the alias dictionary only contains real technologies.
2. Phonetic confusions — homophones a small STT model mishears (``coffee``->Kafka,
   ``radius``->Redis). GATED by the candidate's vocabulary so we only apply them
   when the target term is actually on their resume (spec #11: resume as dictionary).
3. Vocabulary fuzzy correction — near-miss spellings of the candidate's own terms
   (company/project/niche-skill names) at a high cutoff.

Then cosmetic clean-up: filler/duplicate removal and sentence-boundary punctuation.
High-confidence ordinary words are never touched — corrections require a match in
the technology dictionary or the candidate's vocabulary.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from app.vocabulary import _ALIAS_INDEX, fuzzy_match

# Homophones a small ASR model commonly mishears for tech terms (lowercased).
# Multi-word keys are applied as phrases. Gated by vocabulary unless marked always-safe.
PHONETIC_CONFUSIONS: dict[str, str] = {
    "coffee": "Kafka",
    "copy": "Kafka",
    "kafira": "Kafka",
    "radius": "Redis",
    "reddis": "Redis",
    "spring fruit": "Spring Boot",
    "spring boots": "Spring Boot",
    "docker ize": "Dockerize",
    "cuber netis": "Kubernetes",
    "cubernetes": "Kubernetes",
    "post gres": "PostgreSQL",
    "my sequel": "MySQL",
    "graph cool": "GraphQL",
    "jason": "JSON",
    "rest full": "REST",
    "micro service": "Microservices",
}

_FILLER_WORDS = {"um", "uh", "umm", "uhh", "er", "ah", "hmm"}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _phrase_sub(text: str, phrase: str, replacement: str) -> tuple[str, int]:
    """Case-insensitive whole-phrase replacement; returns (new_text, count)."""
    pattern = re.compile(rf"(?<![\w]){re.escape(phrase)}(?![\w])", re.IGNORECASE)
    new, n = pattern.subn(replacement, text)
    return new, n


def _normalize_aliases(text: str, corrections: list[dict]) -> str:
    """Tier 1 — map known aliases/misspellings to canonical tech names (always safe)."""
    # longest aliases first so multi-word phrases win over single words
    for alias in sorted(_ALIAS_INDEX.keys(), key=len, reverse=True):
        canonical = _ALIAS_INDEX[alias]
        if alias == canonical.lower():
            # still normalize casing, but don't log a "correction" for pure case fixes
            new, n = _phrase_sub(text, alias, canonical)
            text = new
            continue
        new, n = _phrase_sub(text, alias, canonical)
        if n:
            corrections.append({"from": alias, "to": canonical, "type": "alias"})
            text = new
    return text


def _apply_phonetic(text: str, vocab_lower: set[str], corrections: list[dict]) -> str:
    """Tier 2 — homophone fixes, gated by the candidate's vocabulary."""
    for wrong, right in sorted(PHONETIC_CONFUSIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if right.lower() not in vocab_lower:
            continue  # only correct toward terms the candidate actually mentioned
        new, n = _phrase_sub(text, wrong, right)
        if n:
            corrections.append({"from": wrong, "to": right, "type": "phonetic"})
            text = new
    return text


def _vocab_fuzzy(text: str, vocabulary: list[str], corrections: list[dict]) -> str:
    """Tier 3 — correct near-miss spellings of the candidate's own terms (high cutoff)."""
    if not vocabulary:
        return text
    single_terms = [v for v in vocabulary if len(v.split()) == 1 and len(v) >= 4]
    if not single_terms:
        return text
    term_lower = {v.lower() for v in vocabulary}

    def fix(m: re.Match) -> str:
        tok = m.group(0)
        low = tok.lower()
        if low in term_lower or low in _ALIAS_INDEX or len(tok) < 4:
            return tok  # already correct / known / too short to risk
        hit = fuzzy_match(tok, single_terms, cutoff=88.0)
        if hit and hit[0].lower() != low:
            corrections.append({"from": tok, "to": hit[0], "type": "vocab"})
            return hit[0]
        return tok

    return _TOKEN_RE.sub(fix, text)


def _clean_fillers(text: str) -> str:
    """Remove standalone fillers and collapse immediate duplicate words (spec #10)."""
    tokens = text.split()
    out: list[str] = []
    for tok in tokens:
        bare = re.sub(r"[^A-Za-z]", "", tok).lower()
        if bare in _FILLER_WORDS:
            continue
        if out and out[-1].lower().strip(".,") == tok.lower().strip(".,"):
            continue  # "so so" -> "so"
        out.append(tok)
    return " ".join(out)


def _fix_sentences(text: str) -> str:
    """Capitalize sentence starts and ensure terminal punctuation (light touch)."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return text
    parts = _SENTENCE_SPLIT.split(text)
    fixed = []
    for p in parts:
        p = p.strip()
        if p:
            fixed.append(p[0].upper() + p[1:])
    out = " ".join(fixed)
    if out and out[-1] not in ".!?":
        out += "."
    return out


def post_process(
    text: str,
    vocabulary: Optional[Iterable[str]] = None,
    history: str = "",
    job_description: str = "",
) -> dict:
    """
    Clean and context-correct a raw transcript.

    Returns {text, corrections:[{from,to,type}], confidence}. The candidate vocabulary
    plus JD/history terms form the contextual dictionary (spec #11). Ordinary words with
    no dictionary/vocabulary match are left untouched.
    """
    raw = (text or "").strip()
    if not raw:
        return {"text": "", "corrections": [], "confidence": 0.0}

    vocab = list(vocabulary or [])
    # widen the contextual dictionary with JD + conversation history terms
    extra = _TOKEN_RE.findall(f"{job_description} {history}")
    vocab_all = vocab + [w for w in extra if len(w) >= 4]
    vocab_lower = {v.lower() for v in vocab_all}

    corrections: list[dict] = []
    out = raw
    out = _normalize_aliases(out, corrections)
    out = _apply_phonetic(out, vocab_lower, corrections)
    out = _vocab_fuzzy(out, vocab_all, corrections)
    out = _clean_fillers(out)
    out = _fix_sentences(out)

    # rough textual confidence: fewer corrections / less filler => higher
    word_count = max(len(raw.split()), 1)
    confidence = round(max(0.5, 1.0 - len(corrections) / word_count), 2)
    return {"text": out, "corrections": corrections, "confidence": confidence}
