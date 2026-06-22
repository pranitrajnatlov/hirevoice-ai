"""
Technology vocabulary & normalization (spec #5, #9).

Deterministic skill normalization + dynamic per-candidate vocabulary building.
No model dependency — works fully offline. ``rapidfuzz`` is used for near-miss
matching with a graceful ``difflib`` fallback so the module imports even if the
dependency is absent (degradation, spec #16).
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

try:  # preferred: fast, accurate
    from rapidfuzz import fuzz, process  # type: ignore

    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - fallback path
    import difflib

    _HAS_RAPIDFUZZ = False


# ── Canonical technology dictionary ────────────────────────────────────────────
# canonical display form -> list of lowercase aliases (variants/misspellings/abbr).
# The canonical key itself is always treated as an alias too.
TECH_ALIASES: dict[str, list[str]] = {
    # Languages
    "JavaScript": ["js", "java script", "ecmascript", "es6", "es2015"],
    "TypeScript": ["ts", "type script"],
    "Python": ["py", "python3", "python2"],
    "Java": ["core java", "java se", "java ee"],
    "C++": ["cpp", "c plus plus", "cplusplus"],
    "C#": ["c sharp", "csharp", "dotnet c#"],
    "Go": ["golang", "go lang"],
    "Rust": ["rustlang"],
    "Ruby": ["ruby lang"],
    "PHP": ["php7", "php8"],
    "Kotlin": ["kotlin lang"],
    "Swift": ["swift lang"],
    "Scala": [],
    "R": ["r language"],
    "SQL": ["structured query language"],
    "Bash": ["shell", "shell scripting", "sh"],
    # Frontend frameworks/libs
    "React": ["reactjs", "react js", "react.js"],
    "React Native": ["reactnative", "react-native"],
    "Next.js": ["nextjs", "next js"],
    "Vue.js": ["vue", "vuejs", "vue js"],
    "Angular": ["angularjs", "angular js"],
    "Svelte": ["sveltejs"],
    "Redux": ["redux toolkit", "rtk"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "HTML": ["html5"],
    "CSS": ["css3"],
    # Backend frameworks
    "Spring Boot": ["springboot", "spring boot", "spring-boot"],
    "Spring": ["spring framework", "spring mvc"],
    "Spring Security": ["springsecurity", "spring-security"],
    "Hibernate": ["hibernate orm"],
    "Node.js": ["node", "nodejs", "node js", "node.js"],
    "Express": ["expressjs", "express js", "express.js"],
    "Flask": ["flask framework"],
    "Django": ["django framework"],
    "FastAPI": ["fast api", "fastapi framework"],
    ".NET": ["dotnet", "dot net", "asp.net", "aspnet"],
    "Ruby on Rails": ["rails", "ror"],
    "GraphQL": ["graph ql"],
    "gRPC": ["grpc"],
    "REST": ["rest api", "restful", "restful api", "restful apis", "rest apis"],
    # Databases
    "PostgreSQL": ["postgres", "postgre sql", "psql"],
    "MySQL": ["my sql"],
    "MongoDB": ["mongo", "mongo db"],
    "Redis": ["redis cache"],
    "SQLite": ["sql lite"],
    "Cassandra": ["apache cassandra"],
    "DynamoDB": ["dynamo db", "dynamo"],
    "Elasticsearch": ["elastic search", "elastic"],
    "Oracle": ["oracle db", "oracle database"],
    "Snowflake": ["snow flake"],
    "Databricks": ["data bricks"],
    # Messaging / streaming
    "Kafka": ["apache kafka", "kafka streams"],
    "RabbitMQ": ["rabbit mq", "rabbitmq broker"],
    "Spark": ["apache spark", "pyspark"],
    "Airflow": ["apache airflow"],
    # Cloud / DevOps
    "AWS": ["amazon web services", "amazon aws"],
    "GCP": ["google cloud", "google cloud platform"],
    "Azure": ["microsoft azure", "ms azure"],
    "Docker": ["docker container", "dockerized"],
    "Kubernetes": ["k8s", "kube", "kubernetes cluster"],
    "Terraform": ["terra form"],
    "Ansible": ["ansible playbook"],
    "Jenkins": ["jenkins ci"],
    "GitHub Actions": ["github action", "gh actions"],
    "CI/CD": ["ci cd", "cicd", "ci/cd pipeline", "continuous integration"],
    "Nginx": ["nginx server"],
    "Kafka Connect": ["kafkaconnect"],
    # ML / data
    "TensorFlow": ["tensor flow", "tensaflow", "tf"],
    "PyTorch": ["py torch", "torch"],
    "scikit-learn": ["sklearn", "scikit learn", "sci-kit learn"],
    "Pandas": ["pandas library"],
    "NumPy": ["numpy", "num py"],
    "OpenCV": ["open cv"],
    "Hugging Face": ["huggingface", "hugging-face"],
    "LangChain": ["lang chain"],
    "OpenAI": ["open ai"],
    "Claude": ["anthropic claude"],
    # Tools / practices
    "Git": ["git scm"],
    "Jira": ["jira board"],
    "Linux": ["gnu linux", "unix"],
    "OAuth": ["oauth2", "o auth", "oauth 2.0"],
    "JWT": ["json web token", "jwt token"],
    "Microservices": ["micro services", "micro-services", "microservice"],
    "Unit Testing": ["unit test", "unit tests", "unit-testing"],
    "Integration Testing": ["integration test", "integration tests"],
    "JUnit": ["j unit", "junit5"],
    "Mockito": ["mockito framework"],
    "Pytest": ["py test"],
    "Jest": ["jestjs"],
    "Selenium": ["selenium webdriver"],
    "WebSocket": ["web socket", "websockets", "web sockets"],
    "Agile": ["agile methodology", "scrum"],
}

# Reverse index: alias (lowercased) -> canonical. Includes canonical-as-alias.
_ALIAS_INDEX: dict[str, str] = {}
for _canon, _aliases in TECH_ALIASES.items():
    _ALIAS_INDEX[_canon.lower()] = _canon
    for _a in _aliases:
        _ALIAS_INDEX[_a.lower()] = _canon

# Sorted canonical names, longest first — used for phrase capitalization so that
# "spring boot" is matched before "spring".
CANONICAL_TERMS: list[str] = sorted(TECH_ALIASES.keys(), key=len, reverse=True)

# ── Skill categorization (for the AI Interview Context viewer) ──────────────────
# canonical tech name -> display category. Anything unmapped falls back to "Other".
SKILL_CATEGORIES: dict[str, str] = {
    # Languages
    "JavaScript": "Languages", "TypeScript": "Languages", "Python": "Languages",
    "Java": "Languages", "C++": "Languages", "C#": "Languages", "Go": "Languages",
    "Rust": "Languages", "Ruby": "Languages", "PHP": "Languages", "Kotlin": "Languages",
    "Swift": "Languages", "Scala": "Languages", "R": "Languages", "SQL": "Languages",
    "Bash": "Languages",
    # Frontend
    "React": "Frontend", "React Native": "Frontend", "Next.js": "Frontend",
    "Vue.js": "Frontend", "Angular": "Frontend", "Svelte": "Frontend", "Redux": "Frontend",
    "Tailwind CSS": "Frontend", "HTML": "Frontend", "CSS": "Frontend",
    # Backend
    "Spring Boot": "Backend", "Spring": "Backend", "Spring Security": "Backend",
    "Hibernate": "Backend", "Node.js": "Backend", "Express": "Backend", "Flask": "Backend",
    "Django": "Backend", "FastAPI": "Backend", ".NET": "Backend", "Ruby on Rails": "Backend",
    "GraphQL": "Backend", "gRPC": "Backend", "REST": "Backend",
    # Databases
    "PostgreSQL": "Databases", "MySQL": "Databases", "MongoDB": "Databases",
    "Redis": "Databases", "SQLite": "Databases", "Cassandra": "Databases",
    "DynamoDB": "Databases", "Elasticsearch": "Databases", "Oracle": "Databases",
    "Snowflake": "Databases", "Databricks": "Databases",
    # Messaging & Streaming
    "Kafka": "Messaging & Streaming", "RabbitMQ": "Messaging & Streaming",
    "Spark": "Messaging & Streaming", "Airflow": "Messaging & Streaming",
    "Kafka Connect": "Messaging & Streaming",
    # Cloud / DevOps
    "AWS": "Cloud", "GCP": "Cloud", "Azure": "Cloud",
    "Docker": "DevOps", "Kubernetes": "DevOps", "Terraform": "DevOps", "Ansible": "DevOps",
    "Jenkins": "DevOps", "GitHub Actions": "DevOps", "CI/CD": "DevOps", "Nginx": "DevOps",
    # Data & ML
    "TensorFlow": "Data & ML", "PyTorch": "Data & ML", "scikit-learn": "Data & ML",
    "Pandas": "Data & ML", "NumPy": "Data & ML", "OpenCV": "Data & ML",
    "Hugging Face": "Data & ML", "LangChain": "Data & ML", "OpenAI": "Data & ML",
    "Claude": "Data & ML",
    # Testing
    "Unit Testing": "Testing", "Integration Testing": "Testing", "JUnit": "Testing",
    "Mockito": "Testing", "Pytest": "Testing", "Jest": "Testing", "Selenium": "Testing",
    # Tools / practices
    "Git": "Tools", "Jira": "Tools", "Linux": "Tools", "OAuth": "Tools", "JWT": "Tools",
    "Microservices": "Tools", "WebSocket": "Tools", "Agile": "Tools",
}

# Stable display order for skill categories (only non-empty ones are shown).
SKILL_CATEGORY_ORDER: list[str] = [
    "Languages", "Frontend", "Backend", "Databases", "Messaging & Streaming",
    "Cloud", "DevOps", "Data & ML", "Testing", "Tools", "Other",
]


def categorize_skill(canonical: str) -> str:
    """Map a canonical skill name to a display category ('Other' if unknown)."""
    return SKILL_CATEGORIES.get(canonical, "Other")


def categorize_skills(skills) -> dict[str, list[dict]]:
    """
    Group skills into display categories (spec #2). Accepts a list of canonical name
    strings or skill dicts ({value, confidence, ...}); returns {category: [skill, ...]}
    in SKILL_CATEGORY_ORDER, omitting empty categories.
    """
    grouped: dict[str, list[dict]] = {}
    for s in skills or []:
        if isinstance(s, dict):
            name = s.get("value")
            item = s
        else:
            name = s
            item = {"value": s}
        if not name:
            continue
        grouped.setdefault(categorize_skill(name), []).append(item)
    return {cat: grouped[cat] for cat in SKILL_CATEGORY_ORDER if cat in grouped}

_FUZZY_SKILL_CUTOFF = 88  # high to avoid mapping a real distinct skill to the wrong canonical
_CLEAN_RE = re.compile(r"[^a-z0-9+#.\s-]")


def _clean(raw: str) -> str:
    s = raw.strip().lower()
    s = _CLEAN_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fuzzy_match(
    term: str, candidates: Iterable[str], cutoff: float = 85.0
) -> Optional[tuple[str, float]]:
    """Return (best_candidate, score 0-100) above cutoff, else None."""
    term = term.strip()
    cand_list = list(candidates)
    if not term or not cand_list:
        return None
    if _HAS_RAPIDFUZZ:
        hit = process.extractOne(term, cand_list, scorer=fuzz.ratio, score_cutoff=cutoff)
        if hit:
            return hit[0], float(hit[1])
        return None
    # difflib fallback (0-1 ratio scaled to 0-100)
    best, best_score = None, 0.0
    for c in cand_list:
        score = difflib.SequenceMatcher(None, term.lower(), c.lower()).ratio() * 100
        if score > best_score:
            best, best_score = c, score
    if best is not None and best_score >= cutoff:
        return best, best_score
    return None


def normalize_skill(raw: str) -> tuple[str, float]:
    """
    Map a raw skill token to its canonical technology name with a confidence 0-1.

    - exact alias hit            -> (canonical, 1.0)
    - close fuzzy alias match    -> (canonical, score/100)   [score >= cutoff]
    - unknown / niche skill      -> (Title-cased raw, 0.4)   [flagged low, never dropped]
    """
    cleaned = _clean(raw)
    if not cleaned:
        return raw.strip(), 0.0
    if cleaned in _ALIAS_INDEX:
        return _ALIAS_INDEX[cleaned], 1.0
    hit = fuzzy_match(cleaned, _ALIAS_INDEX.keys(), cutoff=_FUZZY_SKILL_CUTOFF)
    if hit:
        return _ALIAS_INDEX[hit[0]], round(hit[1] / 100.0, 2)
    # Unknown — preserve candidate's term, flag low confidence.
    pretty = " ".join(w if w.isupper() else w.capitalize() for w in raw.strip().split())
    return pretty, 0.4


def normalize_skills(raws: Iterable[str]) -> list[dict]:
    """Normalize a list of raw skills into [{value, confidence, raw}], de-duplicated by canonical."""
    seen: dict[str, dict] = {}
    for raw in raws:
        raw = raw.strip()
        if not raw:
            continue
        canon, conf = normalize_skill(raw)
        # keep the highest-confidence occurrence per canonical
        if canon not in seen or conf > seen[canon]["confidence"]:
            seen[canon] = {"value": canon, "confidence": conf, "raw": raw}
    return list(seen.values())


def build_vocabulary(profile: dict) -> list[str]:
    """
    Build a dynamic per-candidate vocabulary (spec #9) from a structured resume profile.

    Pulls candidate name, company names, project names, normalized skills, certifications,
    and universities. Used to bias STT (hotwords) and drive context-aware correction.
    Returns a de-duplicated, case-preserving list.
    """
    terms: list[str] = []

    def _val(field):
        # fields may be {"value":..} or plain str
        if isinstance(field, dict):
            return field.get("value")
        return field

    pi = profile.get("personal_information") or {}
    name = _val(pi.get("name"))
    if name:
        terms.append(name)
        terms.extend(name.split())

    for exp in profile.get("experience") or []:
        company = _val(exp.get("company"))
        if company:
            terms.append(company)
        terms.extend(_val(t) or t for t in (exp.get("technologies") or []))

    for proj in profile.get("projects") or []:
        pname = _val(proj.get("name"))
        if pname:
            terms.append(pname)
        terms.extend(_val(t) or t for t in (proj.get("technologies") or []))

    for skill in profile.get("skills") or []:
        v = _val(skill)
        if v:
            terms.append(v)

    for edu in profile.get("education") or []:
        inst = _val(edu.get("institution"))
        if inst:
            terms.append(inst)

    for cert in profile.get("certifications") or []:
        v = _val(cert)
        if v:
            terms.append(v)

    # De-dupe case-insensitively, preserve first-seen casing, drop very short tokens.
    out: list[str] = []
    lower_seen: set[str] = set()
    for t in terms:
        t = (t or "").strip()
        if len(t) < 2:
            continue
        key = t.lower()
        if key not in lower_seen:
            lower_seen.add(key)
            out.append(t)
    return out
