"""
Structured resume parser (spec #1-6) — deterministic, no LLM in the hot path.

Pipeline:  extract_layout()  ->  detect_sections()  ->  field extraction  ->  schema

Tolerant of single/multi-page, multi-column, tables, varied fonts, and arbitrary
section ordering. Every extracted field carries a confidence (spec #4); low-confidence
fields are flagged in ``_meta`` rather than dropped. ``pdfplumber`` gives column-aware
PDF extraction with a graceful ``pypdf`` fallback; ``rapidfuzz`` tolerates heading noise.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from app.resume_integration import _extract_docx, _extract_pdf, load_resume_from_file
from app.vocabulary import fuzzy_match, normalize_skills

logger = logging.getLogger(__name__)

# ── Section heading aliases → canonical section key (spec #1) ──────────────────
SECTION_ALIASES: dict[str, list[str]] = {
    "experience": [
        "experience", "work experience", "professional experience", "employment history",
        "work history", "career history", "employment", "professional background",
    ],
    "skills": [
        "skills", "technical skills", "core competencies", "technologies", "tech stack",
        "skill set", "competencies", "areas of expertise", "key skills",
    ],
    "education": [
        "education", "academic qualification", "academic qualifications", "academics",
        "educational background", "academic background",
    ],
    "projects": [
        "projects", "personal projects", "academic projects", "key projects",
        "selected projects", "notable projects",
    ],
    "certifications": [
        "certifications", "certificates", "licenses & certifications", "licenses",
        "certification",
    ],
    "summary": [
        "summary", "professional summary", "profile", "about", "objective",
        "career objective", "about me", "professional profile",
    ],
    "languages": ["languages", "language proficiency", "languages known"],
    "personal_information": [
        "personal information", "contact", "contact information", "personal details",
        "contact details",
    ],
    "achievements": [
        "achievements", "awards", "honors", "awards & achievements", "accomplishments",
        "awards and achievements",
    ],
    "internships": ["internships", "internship", "internship experience"],
    "volunteer": ["volunteer", "volunteer experience", "volunteering", "community service"],
    "publications": ["publications", "papers", "research", "research papers"],
    "interests": ["interests", "hobbies", "interests & hobbies", "interests and hobbies"],
}

_HEADING_CONF_EXACT = 0.95
_HEADING_FUZZY_CUTOFF = 80.0
_LOW_CONF_THRESHOLD = 0.6

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_LINK_RE = re.compile(r"(https?://\S+|(?:www\.)?(?:linkedin|github)\.com/\S+)", re.I)
_YEAR_RANGE_RE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec\w*)?\.?\s*"
    r"(?:19|20)\d{2})\s*[-–—to]+\s*(present|current|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec\w*)?\.?\s*(?:19|20)\d{2})",
    re.I,
)
_DEGREE_RE = re.compile(
    r"\b(bachelor|master|b\.?tech|m\.?tech|b\.?e\b|m\.?e\b|b\.?sc|m\.?sc|bca|mca|mba|ph\.?d|"
    r"diploma|intermediate|high school|associate)\b",
    re.I,
)
_ROLE_RE = re.compile(
    r"\b(developer|engineer|manager|analyst|consultant|designer|architect|intern|"
    r"lead|specialist|administrator|scientist|director|officer)\b",
    re.I,
)
_BULLET_RE = re.compile(r"^\s*[-•*▪◦‣·]\s+")
_SKILL_SPLIT_RE = re.compile(r"[,|;/]|\s{2,}|•|·|•")


# ── Layout extraction (spec #1, #3) ────────────────────────────────────────────
class ExtractResult:
    def __init__(self, lines: list[str], fmt: str, pages: int, raw_text: str):
        self.lines = lines
        self.format = fmt
        self.pages = pages
        self.raw_text = raw_text


def extract_layout(path: str | Path) -> ExtractResult:
    """Extract ordered text lines from PDF/DOCX/TXT, preserving reading order."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        lines, pages = _extract_pdf_layout(path)
        raw = "\n".join(lines)
        return ExtractResult(lines, "pdf", pages, raw)

    if suffix in (".docx", ".doc"):
        text = _extract_docx_layout(path)
        lines = _clean_lines(text)
        return ExtractResult(lines, "docx", 1, text)

    text = load_resume_from_file(path)  # TXT or unknown
    return ExtractResult(_clean_lines(text), "txt", 1, text)


def extract_from_text(text: str) -> ExtractResult:
    """Build an ExtractResult from already-extracted text (e.g. stored ``extracted_text``)."""
    return ExtractResult(_clean_lines(text), "text", 1, text)


def _extract_pdf_layout(path: Path) -> tuple[list[str], int]:
    """Column-aware PDF extraction via pdfplumber; falls back to pypdf plain text."""
    try:
        import pdfplumber  # type: ignore

        all_lines: list[str] = []
        with pdfplumber.open(str(path)) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                all_lines.extend(_page_lines_columnaware(page))
        if all_lines:
            return _clean_lines("\n".join(all_lines)), pages
    except Exception as exc:  # pragma: no cover - depends on file/lib
        logger.warning("pdfplumber failed (%s) — falling back to pypdf", exc)

    text = _extract_pdf(path)  # existing pypdf path
    return _clean_lines(text), text.count("\f") + 1


def _page_lines_columnaware(page) -> list[str]:
    """
    Detect columns by clustering word x-positions, then read column-by-column,
    top-to-bottom within each column. Handles two-column / sidebar resumes.
    """
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return []

    page_width = page.width or max((w["x1"] for w in words), default=1)
    mid = page_width / 2
    left = [w for w in words if (w["x0"] + w["x1"]) / 2 < mid]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= mid]

    # Two-column only if both sides are substantial; otherwise treat as single column.
    if len(left) > 12 and len(right) > 12:
        groups = [left, right]
    else:
        groups = [words]

    lines: list[str] = []
    for group in groups:
        lines.extend(_words_to_lines(group))
    return lines


def _words_to_lines(words: list[dict], y_tol: float = 3.0) -> list[str]:
    """Group words into visual lines by their vertical position."""
    rows: list[tuple[float, list[dict]]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        placed = False
        for i, (top, row) in enumerate(rows):
            if abs(w["top"] - top) <= y_tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append((w["top"], [w]))
    out = []
    for _, row in sorted(rows, key=lambda r: r[0]):
        text = " ".join(x["text"] for x in sorted(row, key=lambda x: x["x0"]))
        out.append(text)
    return out


def _extract_docx_layout(path: Path) -> str:
    """DOCX paragraphs + table cells (tables are common in resumes, spec #3)."""
    try:
        from docx import Document  # type: ignore

        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append("  ".join(cells))
        return "\n".join(parts)
    except ImportError:  # pragma: no cover
        return _extract_docx(path)


def _clean_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]


# ── Section detection (spec #1) ────────────────────────────────────────────────
def _match_heading(line: str) -> Optional[tuple[str, float]]:
    """Return (canonical_section, confidence) if the line is a section heading."""
    raw = line.strip()
    words = raw.split()
    if not raw or len(words) > 5 or len(raw) > 45:
        return None
    if _EMAIL_RE.search(raw) or _PHONE_RE.search(raw):
        return None
    cleaned = re.sub(r"[^a-z& ]", "", raw.lower()).strip()
    if not cleaned:
        return None

    for canon, aliases in SECTION_ALIASES.items():
        if cleaned in aliases:
            return canon, _HEADING_CONF_EXACT
    # fuzzy — tolerate OCR / spacing noise; only for short heading-like lines
    flat_aliases = {a: c for c, al in SECTION_ALIASES.items() for a in al}
    hit = fuzzy_match(cleaned, flat_aliases.keys(), cutoff=_HEADING_FUZZY_CUTOFF)
    if hit:
        return flat_aliases[hit[0]], round(0.7 + (hit[1] - _HEADING_FUZZY_CUTOFF) / 100.0, 2)
    return None


def detect_sections(lines: list[str]) -> tuple[dict[str, list[str]], dict[str, float], list[str]]:
    """
    Bucket lines under detected canonical sections (order-independent, spec #1).

    Returns (sections, section_confidence, preamble) where preamble is everything
    before the first heading (usually name/contact/summary).
    """
    sections: dict[str, list[str]] = {}
    confidence: dict[str, float] = {}
    preamble: list[str] = []
    current: Optional[str] = None

    for line in lines:
        head = _match_heading(line)
        if head:
            current = head[0]
            sections.setdefault(current, [])
            confidence[current] = max(confidence.get(current, 0.0), head[1])
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)

    return sections, confidence, preamble


# ── Field extraction ───────────────────────────────────────────────────────────
def _vc(value, confidence: float) -> dict:
    return {"value": value, "confidence": round(confidence, 2)}


def _is_headerish(line: str) -> bool:
    if _BULLET_RE.match(line):
        return False
    words = line.split()
    if not (1 <= len(words) <= 8):
        return False
    alpha = [w for w in words if any(c.isalpha() for c in w)]
    if not alpha:
        return False
    capped = sum(1 for w in alpha if w[0].isupper() or w.isupper())
    return capped / len(alpha) >= 0.6 and not line.rstrip().endswith(".")


def _extract_contact(preamble: list[str], full_text: str, base_conf: float) -> dict:
    info: dict = {}
    email = _EMAIL_RE.search(full_text)
    links = _LINK_RE.findall(full_text)
    if email:
        info["email"] = _vc(email.group(0), 0.95)
    # Phone: require >= 10 digits so date ranges like "2020 - 07" don't match.
    for m in _PHONE_RE.finditer(full_text):
        if len(re.sub(r"\D", "", m.group(0))) >= 10:
            info["phone"] = _vc(m.group(0).strip(), 0.8)
            break
    if links:
        info["links"] = [l if isinstance(l, str) else l[0] for l in links][:5]

    # Name: first short, title-case, alpha-only line near the top that isn't a
    # tech/skill line (reject commas and known technologies like "Spring Boot, Java").
    name, name_conf = None, 0.0
    for i, line in enumerate(preamble[:15]):
        words = line.split()
        if not (2 <= len(words) <= 4) or "," in line:
            continue
        if _EMAIL_RE.search(line) or _PHONE_RE.search(line) or any(ch.isdigit() for ch in line):
            continue
        if _match_heading(line):
            continue
        if re.search(r"\b(ltd|limited|inc|pvt|llc|technologies|solutions|corp|company|university|college|institute)\b", line, re.I):
            continue
        from app.vocabulary import normalize_skill
        if any(normalize_skill(w)[1] >= 0.9 for w in words):
            continue
        if all(w[0].isupper() or w.isupper() for w in words if w):
            name = line.strip()
            name_conf = 0.7 if i <= 3 else 0.6
            break
    if name:
        info["name"] = _vc(name, name_conf)
    return info


def _extract_experience(lines: list[str], base_conf: float) -> list[dict]:
    entries: list[dict] = []
    cur: Optional[dict] = None

    def _flush():
        nonlocal cur
        if cur and (cur.get("company") or cur.get("title") or cur.get("responsibilities")):
            entries.append(cur)
        cur = None

    for line in lines:
        date_hit = _YEAR_RANGE_RE.search(line)
        bullet = bool(_BULLET_RE.match(line))
        headerish = _is_headerish(line) and not bullet

        if headerish and cur and cur.get("responsibilities"):
            _flush()  # new entry begins after we've collected responsibilities
        if cur is None:
            cur = {"company": None, "title": None, "dates": None,
                   "responsibilities": [], "technologies": [], "confidence": round(base_conf, 2)}

        if date_hit:
            cur["dates"] = date_hit.group(0).strip()
        elif _ROLE_RE.search(line) and cur["title"] is None and headerish:
            cur["title"] = line.strip()
        elif headerish and cur["company"] is None:
            cur["company"] = line.strip()
        else:
            text = _BULLET_RE.sub("", line).strip()
            if text:
                cur["responsibilities"].append(text)

    _flush()

    # derive technologies per entry from its responsibility text
    for e in entries:
        joined = " ".join(e["responsibilities"])
        techs = _detect_inline_tech(joined)
        e["technologies"] = techs
    return entries


def _extract_education(lines: list[str], base_conf: float) -> list[dict]:
    entries: list[dict] = []
    for line in lines:
        if _DEGREE_RE.search(line) or re.search(r"\b(university|college|institute|school)\b", line, re.I):
            degree = _DEGREE_RE.search(line)
            entries.append({
                "institution": line.strip() if re.search(r"\b(university|college|institute|school)\b", line, re.I) else None,
                "degree": degree.group(0) if degree else None,
                "dates": (_YEAR_RANGE_RE.search(line).group(0) if _YEAR_RANGE_RE.search(line) else None),
                "raw": line.strip(),
                "confidence": round(base_conf, 2),
            })
    return entries


def _extract_projects(lines: list[str], base_conf: float) -> list[dict]:
    entries: list[dict] = []
    cur: Optional[dict] = None
    for line in lines:
        if _is_headerish(line) and not _BULLET_RE.match(line) and len(line.split()) <= 6:
            if cur:
                entries.append(cur)
            cur = {"name": line.strip(), "description": "", "technologies": [],
                   "confidence": round(base_conf, 2)}
        elif cur is not None:
            text = _BULLET_RE.sub("", line).strip()
            cur["description"] = (cur["description"] + " " + text).strip()
    if cur:
        entries.append(cur)
    for e in entries:
        e["technologies"] = _detect_inline_tech(e["description"])
    return entries


def _extract_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        text = _BULLET_RE.sub("", line).strip()
        for part in _SKILL_SPLIT_RE.split(text):
            part = part.strip()
            if len(part) >= 2:
                items.append(part)
    return items


_SKILL_STOPWORDS = {
    "and", "the", "i", "a", "an", "with", "on", "for", "to", "of", "in", "we",
    "furthermore", "also", "my", "our", "using", "used", "key", "description",
}


def _looks_like_skill(token: str) -> bool:
    """Reject prose fragments that leak into a skills bucket (1-4 short words, no sentence markers)."""
    words = token.split()
    if not (1 <= len(words) <= 4):
        return False
    if token.endswith((".", ":")) or ". " in token:
        return False
    if words[0].lower() in _SKILL_STOPWORDS:
        return False
    return any(any(c.isalpha() for c in w) for w in words)


def _extract_skills(lines: list[str]) -> list[dict]:
    """Skill candidates filtered to plausible skills, then normalized to canonical forms."""
    candidates = [c for c in _extract_list_items(lines) if _looks_like_skill(c)]
    skills = normalize_skills(candidates)
    # keep known tech (high conf) or genuinely short unknown tokens (<=2 words) as niche skills
    return [s for s in skills if s["confidence"] >= 0.85 or len(s["value"].split()) <= 2]


def _detect_inline_tech(text: str) -> list[str]:
    """Find known technologies mentioned inside free text (for experience/project tech lists)."""
    if not text:
        return []
    found = normalize_skills(_extract_list_items([text]))
    return [s["value"] for s in found if s["confidence"] >= 0.85]


# ── Orchestration (spec #2, #5) ────────────────────────────────────────────────
def parse_resume(source: str | Path, *, is_text: bool = False) -> dict:
    """
    Parse a resume file (or already-extracted text) into the structured schema.

    Returns the schema dict from spec #2 plus a ``_meta`` block with parser confidence,
    detected sections, and low-confidence field flags.
    """
    extract = extract_from_text(str(source)) if is_text else extract_layout(source)
    sections, sec_conf, preamble = detect_sections(extract.lines)

    def conf(name: str, default: float = 0.5) -> float:
        return sec_conf.get(name, default)

    # Skills (most important downstream — drives vocabulary + interview context)
    skills = _extract_skills(sections.get("skills", []))

    profile: dict = {
        "personal_information": _extract_contact(preamble, extract.raw_text, conf("personal_information", 0.7)),
        "summary": _vc(" ".join(sections.get("summary", []))[:600], conf("summary", 0.5)) if sections.get("summary") or preamble else _vc("", 0.0),
        "experience": _extract_experience(sections.get("experience", []) + sections.get("internships", []), conf("experience", 0.6)),
        "education": _extract_education(sections.get("education", []), conf("education", 0.6)),
        "skills": skills,
        "projects": _extract_projects(sections.get("projects", []), conf("projects", 0.6)),
        "certifications": _extract_list_items(sections.get("certifications", [])),
        "languages": _extract_list_items(sections.get("languages", [])),
        "achievements": _extract_list_items(sections.get("achievements", [])),
    }

    # If no explicit summary heading, use the longest preamble sentence as a soft summary.
    if not profile["summary"]["value"] and preamble:
        longest = max(preamble, key=len)
        if len(longest) > 60:
            profile["summary"] = _vc(longest[:600], 0.5)

    # ── Confidence aggregation + low-confidence flags (spec #4) ──
    low_conf: list[str] = []
    for s in skills:
        if s["confidence"] < _LOW_CONF_THRESHOLD:
            low_conf.append(f"skills.{s['value']}")
    pi = profile["personal_information"]
    for k, v in pi.items():
        if isinstance(v, dict) and v.get("confidence", 1) < _LOW_CONF_THRESHOLD:
            low_conf.append(f"personal_information.{k}")

    section_confs = list(sec_conf.values()) or [0.4]
    parser_conf = round(sum(section_confs) / len(section_confs), 2)

    profile["_meta"] = {
        "parser_confidence": parser_conf,
        "sections_found": sorted(sections.keys()),
        "low_confidence_fields": low_conf,
        "format": extract.format,
        "pages": extract.pages,
        "skill_count": len(skills),
    }
    return profile
