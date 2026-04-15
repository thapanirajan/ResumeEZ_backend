"""
5-Stage AI Resume Screening Pipeline
=====================================
Stage 1 — Section Segmentation      (Python parsing)
Stage 2 — Skill Extraction NER      (Ollama qwen3:8b)
Stage 3 — Semantic Matching         (BGE embeddings + FAISS + rapidfuzz)
Stage 4 — LLM Reranker              (Ollama holistic scoring)
Stage 5 — Scoring + Gap Analysis    (weighted ATS score + roadmap)
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz
from src.services.groq_service import call_groq

# ─── BGE model singleton (lazy load) ──────────────────────────────────────────
_bge_model = None


def _get_bge_model():
    global _bge_model
    if _bge_model is None:
        from sentence_transformers import SentenceTransformer
        _MODEL_PATH = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../models/skill_embeddings")
        )
        print(f"[BGE] Looking for fine-tuned model at: {_MODEL_PATH}")
        if os.path.isdir(_MODEL_PATH):
            print("[BGE] Loading fine-tuned skill_embeddings model")
            _bge_model = SentenceTransformer(_MODEL_PATH)
        else:
            print("[BGE] Fine-tuned model not found, using BAAI/bge-small-en-v1.5")
            _bge_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _bge_model


# ─── spaCy NER model singleton (lazy load) ────────────────────────────────────
_ner_model = None


def _get_ner_model():
    global _ner_model
    if _ner_model is None:
        import spacy
        _NER_PATH = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../models/skill_ner/model-best")
        )
        print(f"[NER] Looking for model at: {_NER_PATH}")
        if os.path.isdir(_NER_PATH):
            _ner_model = spacy.load(_NER_PATH)
        # If model not found, _ner_model stays None → Ollama fallback is used
    return _ner_model


# ─── Pipeline result dataclasses ──────────────────────────────────────────────

@dataclass
class MatchedSkillItem:
    name: str
    canonical_id: str
    match_type: str          # "exact" | "fuzzy" | "semantic"
    confidence: float        # 0.0–1.0
    category: str
    years: int = 0
    weighted_score: float = 0.0


@dataclass
class MissingSkillItem:
    name: str
    canonical_id: str
    category: str
    computed_weight: float
    priority_score: float
    section: str             # "required" | "preferred" | "general"


@dataclass
class ExtraSkillItem:
    name: str
    canonical_id: str
    category: str


@dataclass
class RoadmapSkillItem:
    name: str
    canonical_id: str
    category: str
    domain: str | None
    is_prerequisite: bool
    priority_score: float
    subtopics: list[str] = field(default_factory=list)


@dataclass
class RoadmapPhases:
    phase_1_core: list[RoadmapSkillItem] = field(default_factory=list)
    phase_2_primary: list[RoadmapSkillItem] = field(default_factory=list)
    phase_3_advanced: list[RoadmapSkillItem] = field(default_factory=list)


@dataclass
class PipelineResult:
    ats_score: int
    skills_score: int
    experience_score: int
    education_score: int
    matched_skills: list[MatchedSkillItem]
    missing_skills: list[MissingSkillItem]
    extra_skills: list[ExtraSkillItem]
    hard_skill_match: float | None
    soft_skill_match: float | None
    total_jd_skills: int
    gap_report: str
    roadmap: RoadmapPhases
    reasoning: str
    debug: dict[str, Any] | None = None


@dataclass
class ExtractedSkills:
    technical: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)

    # Groups of interchangeable skills (JD-only), e.g. ["React", "Angular", "Vue.js"]
    alternatives: list[list[str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "technical": self.technical,
            "frameworks": self.frameworks,
            "tools": self.tools,
            "soft": self.soft,
        }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _to_canonical_id(name: str) -> str:
    """Convert a skill name to a stable canonical ID."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")


def _canonicalize_skill_name(name: str) -> str:
    """Normalize common aliases to improve matching consistency."""
    s = (name or "").strip()
    if not s:
        return s

    norm = re.sub(r"[\s\-_]+", " ", s.lower()).strip(" \t\r\n.,;:()[]{}")
    alias_map = {
        # DevOps / CI
        "github actions": "GitHub Actions",
        "actions": "GitHub Actions",
        "ci/cd": "CI/CD",
        "ci cd": "CI/CD",
        "cicd": "CI/CD",
        # API phrasing
        "rest api": "REST API",
        "restful api": "REST API",
        "rest": "REST API",
        "restful api design": "API design",
        "api design": "API design",
        # Agile
        "agile": "Agile/Scrum methodology",
        "scrum": "Agile/Scrum methodology",
        "agile scrum": "Agile/Scrum methodology",
        "agile/scrum": "Agile/Scrum methodology",
        "agile scrum methodology": "Agile/Scrum methodology",
        # GraphQL
        "graphql api": "GraphQL",
        "graphql api development": "GraphQL",
        # Microservices
        "microservices": "microservices architecture",
        "microservices architecture": "microservices architecture",
        # BI
        "power bi": "Power BI",
    }

    return alias_map.get(norm, s)


def _categorize_skill(name: str) -> str:
    """Heuristic skill categorization based on keywords."""
    lower = name.lower()
    if any(w in lower for w in ["python", "javascript", "typescript", "java", "go", "rust", "c++", "c#", "kotlin", "swift", "ruby", "php", "scala"]):
        return "language"
    if any(w in lower for w in ["react", "vue", "angular", "next", "nuxt", "django", "flask", "fastapi", "spring", "express", "rails", "laravel"]):
        return "framework"
    if any(w in lower for w in ["docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "git", "linux", "nginx", "redis"]):
        return "tool"
    if any(w in lower for w in ["aws", "gcp", "azure", "cloud", "s3", "ec2", "lambda", "cloudflare"]):
        return "cloud"
    if any(w in lower for w in ["postgres", "mysql", "mongodb", "elasticsearch", "sqlite", "cassandra", "dynamodb", "sql"]):
        return "database"
    if any(w in lower for w in ["machine learning", "deep learning", "tensorflow", "pytorch", "scikit", "nlp", "llm", "data science"]) or re.search(r"\b(ai|ml)\b", lower):
        return "ai_ml"
    if any(w in lower for w in ["agile", "scrum", "kanban", "ci/cd", "devops", "tdd", "rest", "graphql", "microservices"]):
        return "methodology"
    if any(w in lower for w in ["communication", "leadership", "teamwork", "problem solving", "collaboration", "attention to detail", "management", "presentation"]):
        return "soft"
    if any(w in lower for w in ["api", "grpc", "websocket", "oauth", "jwt"]):
        return "api"
    return "tool"


# ─── Stage 1: Section Segmentation ───────────────────────────────────────────

def segment_resume(resume_data: dict) -> dict[str, str]:
    """Extract text per section from structured JSON resume."""
    sections: dict[str, list[str]] = {
        "summary": [],
        "experience": [],
        "education": [],
        "skills": [],
        "projects": [],
    }

    def _extend_section(key: str, value: Any):
        if value is None:
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                s = str(item).strip()
                if s:
                    sections[key].append(s)
            return
        s = str(value).strip()
        if s:
            sections[key].append(s)

    if v := resume_data.get("summary"):
        _extend_section("summary", v)
    if v := resume_data.get("title"):
        _extend_section("summary", v)

    for exp in resume_data.get("experience", []):
        parts: list[str] = []
        for k in ("role", "company", "description"):
            v = exp.get(k)
            if isinstance(v, (list, tuple, set)):
                parts.extend(str(x).strip() for x in v if str(x).strip())
            elif v:
                parts.append(str(v).strip())
        sections["experience"].append(" ".join(p for p in parts if p))

    for edu in resume_data.get("education", []):
        parts: list[str] = []
        for k in ("degree", "fieldOfStudy", "institution"):
            v = edu.get(k)
            if isinstance(v, (list, tuple, set)):
                parts.extend(str(x).strip() for x in v if str(x).strip())
            elif v:
                parts.append(str(v).strip())
        sections["education"].append(" ".join(p for p in parts if p))

    for skill in resume_data.get("skills", []):
        if v := skill.get("items"):
            _extend_section("skills", v)
        if v := skill.get("category"):
            _extend_section("skills", v)

    for proj in resume_data.get("projects", []):
        parts: list[str] = []
        for k in ("name", "techStack", "description"):
            v = proj.get(k)
            if isinstance(v, (list, tuple, set)):
                parts.extend(str(x).strip() for x in v if str(x).strip())
            elif v:
                parts.append(str(v).strip())
        sections["projects"].append(" ".join(p for p in parts if p))

    return {k: " ".join(v) for k, v in sections.items()}


def segment_resume_text(text: str) -> dict[str, str]:
    """Heuristic segmentation of raw resume text."""
    lines = text.split("\n")
    sections: dict[str, list[str]] = {
        "summary": [], "experience": [], "education": [], "skills": [], "projects": []
    }
    current = "summary"
    section_re = re.compile(
        r"^\s*(experience|work|education|skills?|projects?|summary|objective|profile)\s*:?\s*$",
        re.IGNORECASE,
    )
    for line in lines:
        m = section_re.match(line)
        if m:
            key = m.group(1).lower().rstrip("s")
            if key in ("work",):
                key = "experience"
            if key in ("objective", "profile"):
                key = "summary"
            if key in sections:
                current = key
        else:
            sections[current].append(line)
    return {k: " ".join(v).strip() for k, v in sections.items()}


def segment_jd(jd_text: str) -> dict[str, str]:
    """Split JD into requirements, responsibilities, nice-to-have."""
    lower = jd_text.lower()
    result = {"requirements": "", "responsibilities": "",
              "nice_to_have": "", "full": jd_text}

    # Try to detect sections by keywords
    req_start = -1
    resp_start = -1
    nice_start = -1

    for kw in ["requirement", "qualifications", "what you need", "must have"]:
        idx = lower.find(kw)
        if idx >= 0 and (req_start < 0 or idx < req_start):
            req_start = idx

    for kw in ["responsibilities", "what you'll do", "your role", "duties"]:
        idx = lower.find(kw)
        if idx >= 0 and (resp_start < 0 or idx < resp_start):
            resp_start = idx

    for kw in ["nice to have", "bonus", "preferred", "plus"]:
        idx = lower.find(kw)
        if idx >= 0 and (nice_start < 0 or idx < nice_start):
            nice_start = idx

    # Fallback: use the full JD for requirements if no sections found
    if req_start < 0 and resp_start < 0:
        result["requirements"] = jd_text
    else:
        if req_start >= 0:
            end = min(
                (x for x in [resp_start, nice_start,
                 len(jd_text)] if x > req_start),
                default=len(jd_text),
            )
            result["requirements"] = jd_text[req_start:end]
        if resp_start >= 0:
            end = min(
                (x for x in [req_start, nice_start,
                 len(jd_text)] if x > resp_start),
                default=len(jd_text),
            )
            result["responsibilities"] = jd_text[resp_start:end]
        if nice_start >= 0:
            result["nice_to_have"] = jd_text[nice_start:]

    return result


def _extract_alternative_skill_groups(jd_text: str, jd_skill_names: list[str]) -> list[list[str]]:
    """Detect alternative requirements like 'React, Angular, or Vue.js' from the raw JD text."""
    if not jd_text or not jd_skill_names:
        return []

    def _norm(s: str) -> str:
        return re.sub(r"[\s\-_]+", " ", s.lower()).strip(" \t\r\n.,;:()[]{}")

    jd_norm_map = {_norm(s): s for s in jd_skill_names}
    jd_norm_keys = list(jd_norm_map.keys())

    candidates: list[str] = []
    for line in jd_text.splitlines():
        if " or " in line.lower():
            candidates.append(line.strip())
    for m in re.finditer(r"\(([^)]{0,160}\bor\b[^)]{0,160})\)", jd_text, flags=re.IGNORECASE):
        candidates.append(m.group(1))

    groups: list[list[str]] = []
    seen_groups: set[tuple[str, ...]] = set()
    for chunk in candidates:
        # Primary method: split/sanitize and resolve to JD skills.
        parts = _split_and_sanitize_skill_candidates(chunk)
        resolved: list[str] = []
        for p in parts:
            n = _norm(p)
            if n in jd_norm_map:
                resolved.append(jd_norm_map[n])

        # Fallback: detect any JD skills that co-occur in the chunk.
        if len(resolved) < 2:
            chunk_norm = _norm(chunk)
            resolved = [jd_norm_map[k] for k in jd_norm_keys if k and k in chunk_norm]

        if len(resolved) < 2 or len(resolved) > 5:
            continue
        resolved = list(dict.fromkeys(resolved))
        if len(resolved) < 2:
            continue
        key = tuple(sorted(_norm(x) for x in resolved))
        if key in seen_groups:
            continue
        seen_groups.add(key)
        groups.append(resolved)
    return groups


def _apply_alternative_groups(
    matched: list[MatchedSkillItem],
    missing: list[MissingSkillItem],
    jd_skills: list[tuple[str, str]],
    alternative_groups: list[list[str]],
) -> tuple[list[MatchedSkillItem], list[MissingSkillItem], int, int, int]:
    """
    Collapse alternative groups so 'React, Angular, or Vue.js' counts as 1 requirement.
    Returns (matched, missing, effective_total, effective_hard_total, effective_soft_total).
    """
    total = len(jd_skills)
    hard_total = len([1 for _, c in jd_skills if c != "soft"])
    soft_total = len([1 for _, c in jd_skills if c == "soft"])
    if not alternative_groups:
        return matched, missing, total, hard_total, soft_total

    jd_cat = {s: c for s, c in jd_skills}
    matched_names = {m.name for m in matched}
    missing_by_name: dict[str, MissingSkillItem] = {m.name: m for m in missing}

    new_missing: list[MissingSkillItem] = list(missing)

    def _remove_missing_names(names: set[str]):
        nonlocal new_missing
        new_missing = [m for m in new_missing if m.name not in names]

    for group in alternative_groups:
        present = [s for s in group if s in jd_cat]
        if len(present) < 2:
            continue
        # For this project we want "FastAPI or Django" to count as two distinct requirements,
        # not a single alternative group.
        present_norm = {re.sub(r"[\s\-_]+", " ", s.lower()).strip() for s in present}
        if "fastapi" in present_norm and "django" in present_norm:
            continue

        reduction = len(present) - 1
        total -= reduction
        if any(jd_cat.get(s) == "soft" for s in present):
            soft_total -= reduction
        else:
            hard_total -= reduction

        satisfied = any(s in matched_names for s in present)
        if satisfied:
            _remove_missing_names(set(present))
            continue

        group_missing = [missing_by_name.get(s) for s in present if s in missing_by_name]
        if not group_missing:
            continue

        _remove_missing_names(set(present))

        combined_name = " / ".join(present)
        combined_section = "required" if any(m.section == "required" for m in group_missing) else (
            "preferred" if any(m.section == "preferred" for m in group_missing) else "general"
        )
        combined_weight = max(m.computed_weight for m in group_missing)
        combined_priority = max(m.priority_score for m in group_missing)
        combined_category = jd_cat.get(present[0], group_missing[0].category)

        new_missing.append(MissingSkillItem(
            name=combined_name,
            canonical_id=_to_canonical_id(combined_name),
            category=combined_category,
            computed_weight=combined_weight,
            priority_score=combined_priority,
            section=combined_section,
        ))

    new_missing.sort(key=lambda x: x.priority_score, reverse=True)
    return matched, new_missing, max(total, 0), max(hard_total, 0), max(soft_total, 0)


# ─── Groq helper ──────────────────────────────────────────────────────────────

async def _call_ollama(prompt: str) -> str:
    """Call Groq and return raw text response (drop-in replacement for Ollama)."""
    try:
        return await call_groq(
            prompt,
            system_prompt="You are an expert resume and job description analyzer. Follow the instructions exactly and return only what is asked."
        )
    except Exception:
        return ""


def _extract_json_from_text(text: str) -> Any:
    """Extract JSON object or array from LLM output that may include extra text."""
    # Try direct parse first
    text = text.strip()
    # Remove <think>...</think> blocks (qwen3 CoT)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block
    for pattern in [r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```", r"(\{[\s\S]*\})", r"(\[[\s\S]*\])"]:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


# ─── Stage 2: Skill Extraction ────────────────────────────────────────────────

def extract_skills_ner(text: str) -> ExtractedSkills:
    """Extract skills using the local spaCy NER model (fast, no network call)."""
    nlp = _get_ner_model()
    if nlp is None:
        return ExtractedSkills()

    _LABEL_MAP = {"TECHNICAL": "technical", "FRAMEWORK": "frameworks", "TOOL": "tools", "SOFT": "soft"}
    result = ExtractedSkills()

    # Run NER in chunks to handle long texts
    chunk_size = 1000
    seen: set[str] = set()
    for i in range(0, len(text), chunk_size):
        doc = nlp(text[i:i + chunk_size])
        for ent in doc.ents:
            key = _LABEL_MAP.get(ent.label_)
            skill = ent.text.strip()
            if key and skill and skill.lower() not in seen:
                seen.add(skill.lower())
                getattr(result, key).append(skill)

    return result


async def extract_skills_from_text(text: str, context: str = "resume") -> ExtractedSkills:
    """Extract categorized skills from text.

    Uses the local spaCy NER model first (fast). Falls back to Ollama LLM
    if the NER model is unavailable or returns too few skills (< 3 total).
    """
    if not text.strip():
        return ExtractedSkills()

    # ── Try spaCy NER first ────────────────────────────────────────────────────
    ner_result = extract_skills_ner(text)
    total_ner = sum(len(v) for v in ner_result.as_dict().values())
    if total_ner >= 3:
        return ner_result

    # ── Fall back to Ollama if NER found too little ────────────────────────────
    want_alternatives = context.lower() in {"job", "jd", "job description", "job_description", "jobdescription"}
    alt_key_line = (
        '\n - "alternatives": list of interchangeable skill groups from the job description (ONLY if explicitly written as alternatives like "X, Y, or Z"). Example: [["React","Angular","Vue.js"]]'
        if want_alternatives
        else ""
    )
    example_json = (
        '{"technical": ["JavaScript"], "frameworks": ["React"], "tools": ["Git"], "soft": ["communication"], "alternatives": [["React","Angular","Vue.js"]]}'
        if want_alternatives
        else '{"technical": ["JavaScript"], "frameworks": ["React"], "tools": ["Git"], "soft": ["communication"]}'
    )
    prompt = f"""You are extracting SKILL NAMES ONLY from {context} text.

Rules:
- Output ONLY technology/framework/language/tool names or clear soft-skill phrases.
- Do NOT output job titles, seniority levels, people/roles (e.g. "designers"), verbs (e.g. "collaborate"), or generic prose (e.g. "In this role", "highly").
- If the text says "X, Y, or Z", treat them as alternatives (not three separate mandatory requirements).{alt_key_line}
- Keep items short (1–3 words). Remove proficiency qualifiers like "(Basic)".

Return ONLY a JSON object with these keys:
 - "technical": programming languages (e.g. Python, JavaScript)
 - "frameworks": frameworks/libraries (e.g. React, Django)
 - "tools": tools/platforms (e.g. Git, Docker, AWS)
 - "soft": soft skills (e.g. communication, leadership){alt_key_line}

Text:
{text[:2500]}

Return ONLY valid JSON, no explanation. Example:
{example_json}"""

    raw = await _call_ollama(prompt)
    parsed = _extract_json_from_text(raw)

    if isinstance(parsed, dict):
        result = ExtractedSkills()
        for key in ("technical", "frameworks", "tools", "soft"):
            val = parsed.get(key, [])
            if isinstance(val, list):
                setattr(
                    result,
                    key,
                    [str(s).strip() for s in val if isinstance(s, str) and str(s).strip()],
                )
        if want_alternatives:
            alts = parsed.get("alternatives", [])
            if isinstance(alts, list):
                cleaned_groups: list[list[str]] = []
                for g in alts:
                    if isinstance(g, list):
                        cleaned = [str(x).strip() for x in g if isinstance(x, str) and str(x).strip()]
                        if len(cleaned) >= 2:
                            cleaned_groups.append(cleaned)
                result.alternatives = cleaned_groups
        return result

    # Last resort: simple regex extraction (PascalCase/acronym words only)
    words = re.findall(r"\b[A-Z][a-zA-Z+#.]{2,}\b", text)
    clean_words = [w for w in words if _sanitize_skill(w)]
    return ExtractedSkills(technical=list(dict.fromkeys(clean_words[:20])))


_RE_EMAIL   = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_RE_URL     = re.compile(r"https?://|www\.|\.com/|\.in/|\.org/|github\.com|linkedin\.com|/in/")
_RE_PHONE   = re.compile(r"\+?\d[\d\s\-().]{6,}")
_RE_PIPE    = re.compile(r"\|")
_RE_MULTI_WS = re.compile(r"\s+")

# Keep Ollama prompts bounded even if raw JD/resume is extremely long.
_ATS_OLLAMA_MAX_CHARS = int(os.getenv("ATS_OLLAMA_MAX_CHARS", "12000"))
_PIPELINE_DEBUG = os.getenv("PIPELINE_DEBUG", "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _debug_emit(enabled: bool, stage: str, payload: dict[str, Any]) -> None:
    if not enabled:
        return
    try:
        print(f"[PIPELINE_DEBUG] {stage}: {json.dumps(payload, ensure_ascii=False)}")
    except Exception:
        # Debugging should never break the pipeline
        print(f"[PIPELINE_DEBUG] {stage}: <failed to serialize debug payload>")


def _clean_text_for_scoring(text: str) -> str:
    """Compact text to fit more signal into limited model context."""
    if not text:
        return ""
    t = str(text)
    t = _RE_EMAIL.sub(" ", t)
    t = _RE_URL.sub(" ", t)
    t = _RE_PHONE.sub(" ", t)
    t = _RE_PIPE.sub(" ", t)
    t = t.replace("\u00a0", " ")
    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Preserve line breaks (helps both the cross-encoder and LLM fallback),
    # while still compressing whitespace within each line.
    lines: list[str] = []
    for line in t.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def _build_jd_text_for_scoring(jd_segments: dict[str, str]) -> str:
    parts: list[str] = []
    req = jd_segments.get("requirements", "").strip()
    resp = jd_segments.get("responsibilities", "").strip()
    nice = jd_segments.get("nice_to_have", "").strip()
    full = jd_segments.get("full", "").strip()

    if req:
        parts.append(req)
    if nice:
        parts.append(nice)
    if resp:
        parts.append(resp)
    if not parts and full:
        parts.append(full)

    return _clean_text_for_scoring("\n".join(parts))


def _build_resume_text_for_scoring(resume_segments: dict[str, str]) -> str:
    # Put skills early so the scorer sees explicit tech stacks even if experience text is short.
    parts: list[str] = []
    skills = resume_segments.get("skills", "").strip()
    exp = resume_segments.get("experience", "").strip()
    projects = resume_segments.get("projects", "").strip()
    edu = resume_segments.get("education", "").strip()
    summary = resume_segments.get("summary", "").strip()

    if skills:
        parts.append(skills)
    if exp:
        parts.append(exp)
    if projects:
        parts.append(projects)
    if edu:
        parts.append(edu)
    if not parts and summary:
        parts.append(summary)

    return _clean_text_for_scoring("\n".join(parts))


def _calibrate_scores(
    overall_score: int,
    skills_score: int,
    experience_score: int,
    education_score: int,
    match_pct: int,
) -> tuple[int, int, int, int]:
    """
    Anchor ATS scores to the objective skill-match percentage so that:
      - skills_score is never below match_pct (it is the most reliable signal)
      - overall_score has a FLOOR tied to match_pct (high-match → high overall)
      - overall_score has a CAP tied to match_pct (near-zero-match → cannot rank
        above a medium-match candidate just because of generous exp/edu scoring)

    Floor (overall >= floor):
      match ≥ 70%  → floor = match_pct
      match ≥ 50%  → floor = match_pct - 5
      match ≥ 30%  → floor = match_pct - 10
      match <  30% → floor = round(match_pct * 0.60)

    Cap (overall ≤ match_pct + margin):
      match <  20% → cap = match_pct + 18  (prevents very low match from looking "medium")
      match <  40% → cap = match_pct + 25
      match <  60% → cap = match_pct + 30
      (no cap for strong matches — exp/edu can still contribute upward)
    """
    match_pct = max(0, min(100, int(match_pct)))
    skills_score = max(0, min(100, int(skills_score)))
    experience_score = max(0, min(100, int(experience_score)))
    education_score = max(0, min(100, int(education_score)))
    overall_score = max(0, min(100, int(overall_score)))

    # Skills is the most reliable signal: never below match_pct.
    skills_score = max(skills_score, match_pct)
    # For very low match, prevent generous LLM scoring from producing a "medium" skills score.
    if match_pct < 20:
        skills_score = min(skills_score, match_pct + 22)
    elif match_pct < 40:
        skills_score = min(skills_score, match_pct + 28)

    # Blend overall toward the weighted breakdown when they diverge significantly.
    weighted_overall = round(0.55 * skills_score + 0.30 * experience_score + 0.15 * education_score)
    if overall_score < weighted_overall - 10:
        overall_score = round(0.5 * overall_score + 0.5 * weighted_overall)

    # ── Floor: high skill-match should lift overall ──────────────────────────
    if match_pct >= 70:
        floor = match_pct
    elif match_pct >= 50:
        floor = max(0, match_pct - 5)
    elif match_pct >= 30:
        floor = max(0, match_pct - 10)
    else:
        floor = round(0.60 * match_pct)
    overall_score = max(overall_score, floor)

    # ── Cap: very low skill-match should not rank above medium-match ─────────
    if match_pct < 20:
        cap = match_pct + 18
        overall_score = min(overall_score, cap)
    elif match_pct < 40:
        cap = match_pct + 25
        overall_score = min(overall_score, cap)
    elif match_pct < 60:
        cap = match_pct + 30
        overall_score = min(overall_score, cap)

    overall_score = max(0, min(100, overall_score))
    return overall_score, skills_score, experience_score, education_score

_BANNED_SKILL_NORMALIZED = frozenset({
    # Common JD/section headings that frequently get misclassified as "skills"
    "overview",
    "skills",
    "skill",
    "technical skills",
    "soft skills",
    "key skills",
    "experience",
    "work experience",
    "education",
    "projects",
    "project",
    "certifications",
    "certification",
    "tools",
    "tool",
    "languages",
    "language",
    "frameworks",
    "framework",
    "platform",
    "platforms",
    "key responsibilities",
    "responsibilities",
    "responsibility",
    "key responsibility",
    "requirements",
    "requirement",
    "qualifications",
    "preferred qualifications",
    "nice to have",
    "bonus",
    "about you",
    "about the role",
    "job description",
    # UI labels / shorthands occasionally present in scraped JDs
    "req",
    "pref",
    # Common prose phrases / non-skills that slip through extraction
    "in this role",
    "this role",
    "highly",
    "highly skilled",
    "experienced",
    "we are seeking",
    "mid level",
    "mid-level",
})
_BANNED_SKILL_TAIL_WORDS = frozenset({"responsibilities", "responsibility"})
_LOWERCASE_SKILL_ALLOWLIST = frozenset({
    "agile",
    "scrum",
    "kanban",
    "tdd",
    "rest",
    "graphql",
    "debugging",
    "accessibility",
    "usability",
    "git",
    "docker",
    "kubernetes",
    "redux",
    "mobx",
    "jest",
    "cypress",
    "tailwind",
    "postman",
    "figma",
    "aws",
    "gcp",
    "azure",
})
_NON_SKILL_SINGLE_WORDS = frozenset({
    "highly",
    "experienced",
    "role",
    "overview",
    "built",
    "build",
    "developed",
    "develop",
    "implemented",
    "implement",
    "maintained",
    "maintain",
    "deployed",
    "deploy",
    "managed",
    "manage",
    "designed",
    "design",
    "created",
    "create",
    "analyzed",
    "analyze",
    "responsible",
    "responsibilities",
    "database",
    "databases",
    "api",
    "apis",
    "backend",
    "frontend",
    "worked",
    "architect",
    "collaborate",
    "maintainability",
    "scalability",
    "designers",
    "developer",
    "developers",
    "engineer",
    "engineers",
    "manager",
    "managers",
    "team",
    "teams",
    "junior",
    "mid",
    "senior",
})


def _sanitize_skill(name: str) -> str | None:
    """Return cleaned skill name, or None if it should be discarded."""
    s = name.strip().strip("\"'").strip()
    if not s:
        return None

    # Reject contact info
    if _RE_EMAIL.search(s):
        return None
    if _RE_URL.search(s):
        return None
    if _RE_PHONE.search(s):
        return None
    if _RE_PIPE.search(s):
        return None

    # Reject if it starts with a digit or special char
    if s[0].isdigit() or s[0] in ("+", "/", "@", "#", "."):
        return None

    # Reject strings containing contact-info keywords
    _CONTACT_WORDS = frozenset({"email", "phone", "mobile", "github", "linkedin",
                                "address", "location", "city", "country", "nepal",
                                "india", "portfolio", "website"})
    if any(w.lower() in _CONTACT_WORDS for w in s.split()):
        return None

    # Remove leading bullets / list markers
    s = re.sub(r"^\s*[-•\u2022]+\s*", "", s).strip()
    # Normalize whitespace and strip common trailing punctuation/ellipsis.
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(".,;:)\u2026").rstrip(".")
    # Strip proficiency qualifiers like "(Basic)" or "(Intermediate)"
    if "(" in s:
        s = s.split("(", 1)[0].strip()

    # Reject common section headings / labels (case-insensitive)
    norm = re.sub(r"[\s\-_]+", " ", s.lower()).strip(" \t\r\n.,;:()[]{}")
    if norm in _BANNED_SKILL_NORMALIZED:
        return None
    norm_words = norm.split()
    if norm_words and norm_words[-1] in _BANNED_SKILL_TAIL_WORDS and len(norm_words) <= 2:
        return None

    # Reject overly long phrases — real skill names are short (max 3 words)
    if len(s) > 40 or len(s.split()) > 3:
        return None

    # Reject if first word is a common English descriptor (not a tech term)
    _DESCRIPTORS = frozenset({
        "modern", "various", "extensive", "advanced", "basic", "core",
        "strong", "solid", "good", "excellent", "proficient", "senior",
        "junior", "frontend", "backend", "full", "stay", "up", "using",
        "working", "knowledge", "experience", "understanding", "ability",
        "familiar", "general", "common", "popular", "standard",
    })
    # Reject if last word is a generic category noun (not a specific skill)
    _CATEGORY_NOUNS = frozenset({
        "libraries", "frameworks", "tools", "technologies", "solutions",
        "platforms", "systems", "languages", "concepts", "practices",
        "methods", "techniques", "extensive", "skills", "ability", "databases",
    })
    words_lower = [w.lower() for w in s.split()]
    if not words_lower:
        return None
    if words_lower[0] in _DESCRIPTORS:
        return None
    if len(words_lower) > 1 and words_lower[-1] in _CATEGORY_NOUNS:
        return None

    # Reject job titles that frequently get misclassified as "skills".
    _JOB_TITLE_TAIL_WORDS = frozenset({
        "engineer", "engineers", "developer", "developers", "manager", "managers",
        "analyst", "analysts", "consultant", "consultants", "architect", "architects",
        "director", "directors", "specialist", "specialists", "administrator", "administrators",
        "intern", "interns", "lead", "leads",
    })
    if words_lower[-1] in _JOB_TITLE_TAIL_WORDS and len(words_lower) <= 3:
        return None

    # Reject obvious non-skills
    if len(words_lower) == 1:
        w = words_lower[0]
        if re.search(r"(corp|inc|ltd|llc|university|college|company)$", w):
            return None
        if w in _NON_SKILL_SINGLE_WORDS:
            return None
        # If it is a plain lowercase English word and not explicitly allowed, drop it.
        if s.islower() and w not in _LOWERCASE_SKILL_ALLOWLIST and not re.search(r"[0-9A-Z+#./]", s):
            return None

    # Reject 2-word phrases where the second word is a common English verb/preposition
    # that indicates a sentence fragment ("Flask Worked", "version control Some", etc.)
    _FRAGMENT_TAIL_WORDS = frozenset({
        "worked", "managed", "used", "some", "with", "for", "based",
        "driven", "oriented", "focused", "enabled", "related", "built",
        "written", "developed", "using", "data",
    })
    # If the phrase ends with one of these words, it's almost certainly a sentence fragment.
    if len(words_lower) >= 2 and any(w in _FRAGMENT_TAIL_WORDS for w in words_lower[1:]):
        return None

    # Reject 3-word phrases where the last word is a generic output-noun — indicates
    # the NER captured a sentence fragment ("task management system", "sales dashboard", etc.)
    _FRAGMENT_3W_TAIL = frozenset({
        "system", "systems", "dashboard", "management", "pipeline",
        "backend", "frontend", "platform", "service", "services",
        "application", "applications", "architecture",
    })
    if len(words_lower) == 3 and words_lower[-1] in _FRAGMENT_3W_TAIL:
        _ALLOWED_3W = frozenset({
            "machine learning", "deep learning", "natural language",
            "ci/cd pipelines", "ci cd pipelines",
        })
        if norm not in _ALLOWED_3W:
            return None

    # Reject multi-word phrases that are clearly sentence fragments (all non-first
    # words are common prose connectors)
    _PROSE_WORDS = frozenset({
        "using", "with", "for", "and", "the", "of", "in", "to", "from",
        "some", "tasks", "system", "systems", "dashboard", "data",
    })
    if len(words_lower) >= 2 and all(w in _PROSE_WORDS for w in words_lower[1:]):
        return None

    # Reject very short or all-lower words that are likely stop words
    if len(s) <= 1:
        return None

    # Strip trailing punctuation
    s = s.rstrip(".,;:)\u2026").rstrip(".")

    return s if s else None


def _split_and_sanitize_skill_candidates(text: str) -> list[str]:
    """Split a possibly multi-skill string into sanitized individual skills."""
    raw = str(text or "").strip()
    if not raw:
        return []

    raw = raw.replace("\u2013", "-").replace("\u2014", "-")
    raw = re.sub(r"^\s*[-•\u2022]+\s*", "", raw).strip()

    lower = raw.lower()
    for marker in ("such as", "including", "for example", "e.g.", "e.g", "eg."):
        idx = lower.find(marker)
        if idx >= 0:
            raw = raw[idx + len(marker):].strip(" :,-\t")
            break

    # Split on commas/semicolons and common list conjunctions.
    # Avoid splitting on "/" unless it is spaced (" / "), so "CI/CD" stays intact.
    parts = re.split(r"\s*(?:,|;|\||\band/or\b|\bor\b|\band\b|\s/\s)\s*", raw, flags=re.IGNORECASE)
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        p = part.strip().strip("\"'").strip()
        if not p:
            continue
        p = p.strip("()[]{}")
        p = re.sub(r"^\s*(one of|either|at least one of)\s+", "", p, flags=re.IGNORECASE).strip()
        # If the NER returns a label-prefixed phrase like "Tools SQL VBA",
        # drop the leading label and keep the actual skill tokens.
        p = re.sub(r"^\s*(tools?|languages?|databases?|frameworks?|frontend|backend|devops|cloud)\s+", "", p, flags=re.IGNORECASE).strip()
        candidates = [p]
        tokens = p.split()
        if 2 <= len(tokens) <= 3:
            norm_p = re.sub(r"[\s\-_]+", " ", p.lower()).strip(" \t\r\n.,;:()[]{}")
            _PRESERVE_MULTIWORD = frozenset({
                "machine learning",
                "deep learning",
                "natural language",
                "version control",
                "rest api",
                "ci/cd",
                "ci cd",
                "problem solving",
                "attention to detail",
                "power bi",
            })
            if norm_p not in _PRESERVE_MULTIWORD:
                if any(t.lower() in {"api", "apis"} for t in tokens):
                    # Prefer splitting phrases like "API GraphQL" into token skills.
                    candidates = tokens
                # Split only when it's clearly a packed list of well-known tech tokens.
                _KNOWN_TECH_TOKENS = frozenset({
                    "html", "css",
                    "python", "javascript", "typescript",
                    "react", "next.js", "django", "fastapi", "flask",
                    "postgresql", "mongodb", "redis", "mysql", "oracle", "sql", "vba",
                    "docker", "kubernetes", "jenkins", "git", "linux",
                    "aws", "ec2", "s3", "lambda",
                    "graphql", "microservices",
                    "excel", "tableau", "ssis",
                })
                token_norms = [re.sub(r"[^\w.+#/]+", "", t.lower()) for t in tokens]
                if all(t in _KNOWN_TECH_TOKENS for t in token_norms):
                    candidates = tokens
                elif re.fullmatch(r"(?:[A-Z]{2,})(?:\s+[A-Z]{2,}){1,3}", " ".join(tokens)):
                    # e.g. "HTML CSS" but preserve "Power BI" above.
                    candidates = tokens

        for cand in candidates:
            s = _sanitize_skill(cand)
            if not s:
                continue
            s = _canonicalize_skill_name(s)
            s = _sanitize_skill(s) or ""
            if not s:
                continue
            key = s.lower()
            if key not in seen:
                seen.add(key)
                cleaned.append(s)
    return cleaned


def _flatten_skills(skills_dict: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Flatten skill dict to list of (name, category) tuples, sanitizing each skill."""
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for category, skills in skills_dict.items():
        cat_label = {
            "technical": "language",
            "frameworks": "framework",
            "tools": "tool",
            "soft": "soft",
        }.get(category, category)
        for s in skills:
            for clean in _split_and_sanitize_skill_candidates(s):
                key = clean.lower()
                if key in seen:
                    continue
                seen.add(key)
                result.append((clean, cat_label))
    return result


# ─── Stage 3: Semantic Matching (BGE + FAISS + rapidfuzz) ────────────────────

def _fuzzy_match(skill: str, candidates: list[str], threshold: int = 80) -> tuple[str, float] | None:
    """Find best fuzzy match above threshold."""
    best_score = 0
    best_match = None
    for candidate in candidates:
        score = fuzz.token_sort_ratio(skill.lower(), candidate.lower())
        if score > best_score:
            best_score = score
            best_match = candidate
    if best_score >= threshold and best_match:
        return best_match, best_score / 100.0
    return None


def match_skills_semantic(
    resume_skills: list[tuple[str, str]],
    jd_skills: list[tuple[str, str]],
    semantic_threshold: float = 0.72,
    fuzzy_threshold: int = 80,
) -> tuple[list[MatchedSkillItem], list[MissingSkillItem], list[ExtraSkillItem]]:
    """
    Match resume skills against JD skills using:
    1. Exact string match
    2. Fuzzy match (rapidfuzz)
    3. Semantic match (BGE + FAISS)
    """
    import numpy as np

    matched: list[MatchedSkillItem] = []
    missing: list[MissingSkillItem] = []
    extra: list[ExtraSkillItem] = []

    if not jd_skills:
        extra = [ExtraSkillItem(name=s, canonical_id=_to_canonical_id(
            s), category=c) for s, c in resume_skills]
        return matched, missing, extra

    jd_names = [s for s, _ in jd_skills]
    jd_cats = {s: c for s, c in jd_skills}
    resume_names = [s for s, _ in resume_skills]
    resume_cats = {s: c for s, c in resume_skills}

    matched_jd: set[str] = set()
    matched_resume: set[str] = set()

    # Step 1: Exact matches
    for r_name, r_cat in resume_skills:
        for j_name in jd_names:
            if r_name.lower() == j_name.lower():
                matched.append(MatchedSkillItem(
                    name=j_name,
                    canonical_id=_to_canonical_id(j_name),
                    match_type="exact",
                    confidence=1.0,
                    category=jd_cats.get(j_name, r_cat),
                ))
                matched_jd.add(j_name)
                matched_resume.add(r_name)
                break

    # Step 2: Fuzzy matches for unmatched
    remaining_resume = [(s, c)
                        for s, c in resume_skills if s not in matched_resume]
    remaining_jd = [s for s in jd_names if s not in matched_jd]

    for r_name, r_cat in remaining_resume:
        result = _fuzzy_match(r_name, remaining_jd, fuzzy_threshold)
        if result:
            j_name, conf = result
            matched.append(MatchedSkillItem(
                name=j_name,
                canonical_id=_to_canonical_id(j_name),
                match_type="fuzzy",
                confidence=conf,
                category=jd_cats.get(j_name, r_cat),
            ))
            matched_jd.add(j_name)
            matched_resume.add(r_name)
            remaining_jd = [s for s in remaining_jd if s != j_name]

    # Step 3: Semantic matches (BGE + FAISS) for still-unmatched
    remaining_resume2 = [(s, c)
                         for s, c in resume_skills if s not in matched_resume]
    remaining_jd2 = [s for s in jd_names if s not in matched_jd]

    if remaining_resume2 and remaining_jd2:
        try:
            import faiss
            model = _get_bge_model()

            jd_embeddings = model.encode(
                remaining_jd2, normalize_embeddings=True)
            resume_embeddings = model.encode(
                [s for s, _ in remaining_resume2], normalize_embeddings=True)

            jd_embeddings = np.array(jd_embeddings, dtype="float32")
            resume_embeddings = np.array(resume_embeddings, dtype="float32")

            dim = jd_embeddings.shape[1]
            # Inner product = cosine similarity (normalized)
            index = faiss.IndexFlatIP(dim)
            index.add(jd_embeddings)

            D, I = index.search(resume_embeddings, k=1)

            for idx, (r_name, r_cat) in enumerate(remaining_resume2):
                sim = float(D[idx][0])
                j_idx = int(I[idx][0])
                if sim >= semantic_threshold and j_idx >= 0:
                    j_name = remaining_jd2[j_idx]
                    if j_name not in matched_jd:
                        matched.append(MatchedSkillItem(
                            name=j_name,
                            canonical_id=_to_canonical_id(j_name),
                            match_type="semantic",
                            confidence=sim,
                            category=jd_cats.get(j_name, r_cat),
                        ))
                        matched_jd.add(j_name)
                        matched_resume.add(r_name)
        except Exception:
            pass  # Graceful fallback if FAISS/BGE fails

    # Build missing skills from unmatched JD skills
    all_matched_jd = matched_jd
    for i, (j_name, j_cat) in enumerate(jd_skills):
        if j_name not in all_matched_jd:
            # Heuristic: first 40% of JD skills = required, next 30% = preferred, rest = general
            total = len(jd_skills)
            pos_ratio = i / max(total - 1, 1)
            if pos_ratio < 0.4:
                section = "required"
                weight = 1.0
            elif pos_ratio < 0.7:
                section = "preferred"
                weight = 0.6
            else:
                section = "general"
                weight = 0.3

            priority = round(weight * (1.0 - pos_ratio * 0.5), 3)
            missing.append(MissingSkillItem(
                name=j_name,
                canonical_id=_to_canonical_id(j_name),
                category=j_cat,
                computed_weight=weight,
                priority_score=priority,
                section=section,
            ))

    # Extra skills: in resume but not matched to any JD skill
    for r_name, r_cat in resume_skills:
        if r_name not in matched_resume:
            if r_cat == "soft":
                continue
            extra.append(ExtraSkillItem(
                name=r_name,
                canonical_id=_to_canonical_id(r_name),
                category=r_cat,
            ))

    # Sort missing by priority descending
    missing.sort(key=lambda x: x.priority_score, reverse=True)

    return matched, missing, extra


# ─── Stage 4: ATS Cross-Encoder Scorer ───────────────────────────────────────

_ATS_BASE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_ats_scorer_model = None
_ats_scorer_tokenizer = None
_ats_scorer_disabled = False


class _ATSScorer:
    """22M param cross-encoder that outputs 4 ATS scores from JD+resume pair."""
    def __init__(self):
        import torch.nn as nn
        from transformers import AutoModel
        import torch

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.encoder = AutoModel.from_pretrained(_ATS_BASE_MODEL)
                self.dropout = nn.Dropout(0.1)
                self.regressor = nn.Linear(self.encoder.config.hidden_size, 4)

            def forward(self, input_ids, attention_mask):
                out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
                cls = self.dropout(out.last_hidden_state[:, 0])
                return torch.sigmoid(self.regressor(cls))

        self._net = _Net()

    def load(self, model_pt: str):
        import torch
        self._net.load_state_dict(torch.load(model_pt, map_location="cpu", weights_only=True))
        self._net.eval()

    def predict(self, input_ids, attention_mask):
        import torch
        with torch.no_grad():
            return self._net(input_ids, attention_mask)


def _get_ats_scorer():
    """Load ATS scorer once, reuse forever. Returns (model, tokenizer) or (None, None)."""
    global _ats_scorer_model, _ats_scorer_tokenizer, _ats_scorer_disabled
    if _ats_scorer_disabled:
        return None, None
    if _ats_scorer_model is None:
        _MODEL_DIR = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../models/ats_scorer")
        )
        print(f"[ATS] Looking for scorer at: {_MODEL_DIR}")
        model_pt = os.path.join(_MODEL_DIR, "model.pt")
        if not os.path.isdir(_MODEL_DIR) or not os.path.exists(model_pt):
            return None, None
        try:
            import torch

            def _state_dict_looks_compatible(state: Any) -> bool:
                if not isinstance(state, dict):
                    return False
                # Our scorer must have the custom 4-output regressor head.
                if "regressor.weight" not in state or "regressor.bias" not in state:
                    return False
                # Reject common incompatible heads from the base cross-encoder.
                if "classifier.weight" in state or "classifier.bias" in state:
                    return False
                # Ensure we have encoder weights too (otherwise regressor alone would be nonsense).
                if not any(isinstance(k, str) and k.startswith("encoder.") for k in state.keys()):
                    return False
                try:
                    w = state.get("regressor.weight")
                    if hasattr(w, "shape") and len(w.shape) >= 1 and int(w.shape[0]) != 4:
                        return False
                except Exception:
                    return False
                return True

            # Check that the saved weights actually match our 4-output _ATSScorer architecture.
            # If the file contains the original cross-encoder's classifier head (classifier.weight /
            # classifier.bias) but NOT our custom regressor.weight, the regressor would be left
            # randomly initialised → garbage 4-score output.  Skip to Ollama in that case.
            state = torch.load(model_pt, map_location="cpu", weights_only=True)
            if not _state_dict_looks_compatible(state):
                print(
                    "[ATS] model.pt has incompatible architecture "
                    "(incompatible state_dict; expected encoder.* + regressor.* for 4 ATS outputs). "
                    "Skipping cross-encoder and using Ollama fallback."
                )
                _ats_scorer_disabled = True
                return None, None
            from transformers import AutoTokenizer
            try:
                _ats_scorer_tokenizer = AutoTokenizer.from_pretrained(_MODEL_DIR)
                _ats_scorer_model = _ATSScorer()
                _ats_scorer_model.load(model_pt)
            except Exception:
                _ats_scorer_model = None
                _ats_scorer_tokenizer = None
                _ats_scorer_disabled = True
                raise
        except Exception as e:
            print(f"[WARNING] Failed to load ATS scorer: {e}. Using Ollama fallback.")
            _ats_scorer_model = None
            _ats_scorer_tokenizer = None
            _ats_scorer_disabled = True
            return None, None
    return _ats_scorer_model, _ats_scorer_tokenizer


def _heuristic_experience_score(jd_segments: dict[str, str], resume_segments: dict[str, str]) -> int:
    """
    Cheap deterministic experience scoring to supplement the LLM/cross-encoder:
    - Years mentioned (e.g. "5 years")
    - Role-title relevance (full-stack/software/backend vs data analyst, etc.)
    - Keyword overlap in experience descriptions
    """
    jd_text = " ".join(str(v or "") for v in (jd_segments or {}).values())
    exp_text = str((resume_segments or {}).get("experience", "") or "")
    summary_text = str((resume_segments or {}).get("summary", "") or "")
    full_text = f"{summary_text}\n{exp_text}"

    years = 0
    for m in re.finditer(r"\b(\d{1,2})\s*(?:\+?\s*)years?\b", full_text, flags=re.IGNORECASE):
        try:
            years = max(years, int(m.group(1)))
        except Exception:
            continue
    years = max(0, min(15, years))
    years_score = round(min(1.0, years / 8.0) * 100)

    role_relevance = 50
    role_text = full_text.lower()
    if any(k in role_text for k in ["full-stack", "full stack", "software engineer", "backend developer", "frontend developer", "web developer"]):
        role_relevance += 25
    if any(k in role_text for k in ["senior", "lead", "principal"]):
        role_relevance += 10
    if any(k in role_text for k in ["data analyst", "business analyst", "accountant", "finance"]):
        role_relevance -= 25
    role_relevance = max(0, min(100, role_relevance))

    keywords = [
        "python", "typescript", "javascript", "react", "next", "fastapi", "django",
        "api", "rest", "postgres", "mongodb", "docker", "kubernetes", "aws", "s3",
        "lambda", "git", "ci/cd", "jenkins", "redis", "graphql",
    ]
    jd_kw = {k for k in keywords if k in jd_text.lower()}
    resume_hit = sum(1 for k in jd_kw if k in full_text.lower())
    overlap_score = round((resume_hit / max(len(jd_kw), 1)) * 100)

    score = round(0.40 * years_score + 0.30 * role_relevance + 0.30 * overlap_score)
    return max(0, min(100, int(score)))


async def llm_rerank(
    jd_segments: dict[str, str],
    resume_segments: dict[str, str],
    matched_skills: list[MatchedSkillItem],
    missing_skills: list[MissingSkillItem],
    total_jd_skills: int,
    hard_total: int | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Score candidate using local cross-encoder. Falls back to Ollama if model missing."""
    if hard_total is not None and hard_total > 0:
        hard_matched = [m for m in matched_skills if m.category != "soft"]
        match_pct = round(len(hard_matched) / hard_total * 100)
    else:
        match_pct = round(len(matched_skills) / max(total_jd_skills, 1) * 100)
    matched_names = [s.name for s in matched_skills[:15]]
    missing_names = [s.name for s in missing_skills[:15]]

    # ── Try local cross-encoder first ─────────────────────────────────────────
    scorer, tokenizer = _get_ats_scorer()
    if scorer is not None and tokenizer is not None:
        jd_text = _build_jd_text_for_scoring(jd_segments)
        resume_text = _build_resume_text_for_scoring(resume_segments)
        _debug_emit(debug, "stage4_input_cross_encoder", {
            "jd_chars": len(jd_text),
            "resume_chars": len(resume_text),
            "jd_preview": jd_text[:400],
            "resume_preview": resume_text[:400],
        })
        try:
            enc = tokenizer(
                jd_text, resume_text,
                max_length=512, padding="max_length",
                truncation=True, return_tensors="pt",
            )
            raw_scores = scorer.predict(enc["input_ids"], enc["attention_mask"])
            scores = (raw_scores.squeeze() * 100).int().tolist()
            heuristic_exp = _heuristic_experience_score(jd_segments, resume_segments)
            scores[2] = round(0.60 * int(scores[2]) + 0.40 * heuristic_exp)
            overall_score, skills_score, experience_score, education_score = _calibrate_scores(
                scores[0], scores[1], scores[2], scores[3], match_pct
            )
            return {
                "scorer": "cross_encoder",
                "overall_score":    overall_score,
                "skills_score":     skills_score,
                "experience_score": experience_score,
                "education_score":  education_score,
                "match_pct":        match_pct,
                "reasoning": (
                    f"Skill match: {match_pct}% ({len(matched_skills)}/{total_jd_skills} skills). "
                    f"Missing: {', '.join(missing_names[:3]) if missing_names else 'none'}."
                ),
            }
        except Exception as e:
            print(f"[WARNING] ATS scorer inference failed: {e}. Using Ollama fallback.")

    # ── Ollama fallback ────────────────────────────────────────────────────────
    jd_prompt_text = _build_jd_text_for_scoring(jd_segments)[:_ATS_OLLAMA_MAX_CHARS]
    resume_exp_text = _clean_text_for_scoring(resume_segments.get("experience", ""))[:_ATS_OLLAMA_MAX_CHARS]
    resume_edu_text = _clean_text_for_scoring(resume_segments.get("education", ""))[:_ATS_OLLAMA_MAX_CHARS]
    resume_skills_text = _clean_text_for_scoring(resume_segments.get("skills", ""))[:_ATS_OLLAMA_MAX_CHARS]

    _debug_emit(debug, "stage4_input_ollama", {
        "jd_chars": len(jd_prompt_text),
        "exp_chars": len(resume_exp_text),
        "edu_chars": len(resume_edu_text),
        "skills_chars": len(resume_skills_text),
        "skill_match_pct": match_pct,
        "matched_skills": matched_names,
        "missing_skills": missing_names,
    })

    prompt = f"""You are an ATS (Applicant Tracking System). Score this candidate against the job.

JOB REQUIREMENTS:
{jd_prompt_text}

CANDIDATE EXPERIENCE:
{resume_exp_text}

CANDIDATE EDUCATION:
{resume_edu_text}

CANDIDATE SKILLS:
{resume_skills_text}

SKILLS MATCHED: {', '.join(matched_names) if matched_names else 'none'}
SKILLS MISSING: {', '.join(missing_names) if missing_names else 'none'}
SKILL MATCH %: {match_pct}%

Return ONLY a JSON object with these keys:
- "overall_score": integer 0-100
- "skills_score": integer 0-100
- "experience_score": integer 0-100
- "education_score": integer 0-100
- "reasoning": one sentence explanation

Example: {{"overall_score": 72, "skills_score": 85, "experience_score": 65, "education_score": 70, "reasoning": "Strong technical skills but missing Docker and Kubernetes experience."}}"""

    raw    = await _call_ollama(prompt)
    parsed = _extract_json_from_text(raw)

    if isinstance(parsed, dict):
        heuristic_exp = _heuristic_experience_score(jd_segments, resume_segments)
        exp = round(0.60 * int(parsed.get("experience_score", 50)) + 0.40 * heuristic_exp)
        overall_score, skills_score, experience_score, education_score = _calibrate_scores(
            int(parsed.get("overall_score", match_pct)),
            int(parsed.get("skills_score", match_pct)),
            int(exp),
            int(parsed.get("education_score", 50)),
            match_pct,
        )
        return {
            "scorer": "ollama",
            "overall_score":    overall_score,
            "skills_score":     skills_score,
            "experience_score": experience_score,
            "education_score":  education_score,
            "match_pct":        match_pct,
            "reasoning":        str(parsed.get("reasoning", ""))[:500],
        }

    overall_score, skills_score, experience_score, education_score = _calibrate_scores(
        match_pct, match_pct, 50, 50, match_pct
    )
    return {
        "scorer": "fallback",
        "overall_score":    overall_score,
        "skills_score":     skills_score,
        "experience_score": experience_score,
        "education_score":  education_score,
        "match_pct":        match_pct,
        "reasoning":        f"Skill match: {match_pct}% ({len(matched_skills)}/{total_jd_skills} skills).",
    }


# ─── Stage 5: Gap Report + Roadmap ────────────────────────────────────────────

def generate_gap_report(
    matched_skills: list[MatchedSkillItem],
    missing_skills: list[MissingSkillItem],
    overall_score: int,
) -> str:
    """Generate a concise gap analysis narrative using templates (no Ollama call)."""
    matched_names    = [s.name for s in matched_skills[:6]]
    required_missing = [s.name for s in missing_skills if s.section == "required"][:4]
    preferred_missing = [s.name for s in missing_skills if s.section == "preferred"][:3]
    total_required   = len([s for s in missing_skills if s.section == "required"])

    if overall_score >= 80:
        verdict = "The candidate is well-qualified for this role."
    elif overall_score >= 60:
        verdict = "The candidate meets most of the core requirements."
    elif overall_score >= 40:
        verdict = "The candidate partially meets the requirements with some notable gaps."
    else:
        verdict = "The candidate has significant skill gaps relative to the job requirements."

    parts = [f"Overall ATS match: {overall_score}%. {verdict}"]

    if matched_names:
        parts.append(f"Matched skills include: {', '.join(matched_names)}.")

    if required_missing:
        parts.append(
            f"{total_required} required skill{'s' if total_required != 1 else ''} missing"
            f", including: {', '.join(required_missing)}."
        )
    elif preferred_missing:
        parts.append(f"Preferred skills to strengthen: {', '.join(preferred_missing)}.")
    elif not missing_skills:
        parts.append("No skill gaps detected — all required skills are present.")

    return " ".join(parts)


def _build_roadmap(missing_skills: list[MissingSkillItem]) -> RoadmapPhases:
    """Assign missing skills to learning roadmap phases."""
    required = [s for s in missing_skills if s.section == "required"]
    preferred = [s for s in missing_skills if s.section == "preferred"]
    general = [s for s in missing_skills if s.section == "general"]

    def to_roadmap_item(s: MissingSkillItem, is_prereq: bool = False) -> RoadmapSkillItem:
        return RoadmapSkillItem(
            name=s.name,
            canonical_id=s.canonical_id,
            category=s.category,
            domain=None,
            is_prerequisite=is_prereq,
            priority_score=s.priority_score,
            subtopics=[],
        )

    # Phase 1: required skills with highest priority (prerequisites)
    phase1 = [to_roadmap_item(s, is_prereq=True) for s in required[:4]]
    # Phase 2: remaining required + high-priority preferred
    phase2 = [to_roadmap_item(s) for s in required[4:]] + \
        [to_roadmap_item(s) for s in preferred[:4]]
    # Phase 3: rest
    phase3 = [to_roadmap_item(s) for s in preferred[4:]] + \
        [to_roadmap_item(s) for s in general[:4]]

    return RoadmapPhases(phase_1_core=phase1, phase_2_primary=phase2, phase_3_advanced=phase3)


# ─── Main Pipeline Orchestrator ───────────────────────────────────────────────

async def run_pipeline(
    jd_text: str,
    resume_data: dict | None = None,
    resume_text: str | None = None,
    debug: bool = False,
) -> PipelineResult:
    """
    Run the full 5-stage pipeline and return PipelineResult.
    Provide either resume_data (JSON) or resume_text (plain text).
    """
    import time
    _t0 = time.perf_counter()
    def _log(stage: str):
        print(f"[PIPELINE] {stage}: {(time.perf_counter() - _t0)*1000:.0f}ms")

    debug_enabled = debug or _PIPELINE_DEBUG

    # ── Stage 1: Segment ────────────────────────────────────────────────────
    jd_segments = segment_jd(jd_text)

    if resume_data is not None:
        resume_segments = segment_resume(resume_data)
    elif resume_text:
        resume_segments = segment_resume_text(resume_text)
    else:
        resume_segments = {"summary": "", "experience": "",
                           "education": "", "skills": "", "projects": ""}

    # Build full text — exclude summary from skill extraction (it often contains contact info)
    _skill_sections = ("skills", "experience", "projects")
    resume_full_text = " ".join(
        resume_segments.get(k, "") for k in _skill_sections if resume_segments.get(k)
    ) or " ".join(v for v in resume_segments.values() if v)

    # Strip email/URL/phone tokens from resume text before NER
    _clean = resume_full_text
    _clean = _RE_EMAIL.sub("", _clean)
    _clean = _RE_URL.sub("", _clean)
    _clean = _RE_PHONE.sub("", _clean)
    _clean = _RE_PIPE.sub(" ", _clean)
    resume_full_text = _clean

    jd_full_text = jd_segments.get("full", jd_text)
    _log("Stage 1 segmentation done")
    _debug_emit(debug_enabled, "stage1_segments", {
        "jd_keys": list(jd_segments.keys()),
        "resume_keys": list(resume_segments.keys()),
        "jd_lengths": {k: len(v or "") for k, v in jd_segments.items()},
        "resume_lengths": {k: len(v or "") for k, v in resume_segments.items()},
    })

    # ── Stage 2: Skill Extraction ────────────────────────────────────────────
    resume_skills_extracted = await extract_skills_from_text(resume_full_text, context="resume")
    _log("Stage 2a resume NER done")
    jd_skills_extracted = await extract_skills_from_text(jd_full_text, context="job description")
    _log("Stage 2b JD NER done")

    resume_skill_tuples = _flatten_skills(resume_skills_extracted.as_dict())
    jd_skill_tuples = _flatten_skills(jd_skills_extracted.as_dict())
    _debug_emit(debug_enabled, "stage2_extracted_skills", {
        "resume": resume_skills_extracted.as_dict(),
        "jd": jd_skills_extracted.as_dict(),
        "jd_alternatives": jd_skills_extracted.alternatives,
        "resume_flat_count": len(resume_skill_tuples),
        "jd_flat_count": len(jd_skill_tuples),
        "resume_flat_preview": resume_skill_tuples[:40],
        "jd_flat_preview": jd_skill_tuples[:60],
    })

    # Fallback: if NER/Ollama returned nothing, use simple keyword extraction
    if not jd_skill_tuples:
        words = re.findall(r"\b[A-Za-z][a-zA-Z+#.]{2,}\b", jd_full_text)
        _stop = frozenset({"the", "and", "for", "with", "that", "this", "are", "you",
                           "will", "have", "our", "your", "they", "their", "from",
                           "work", "role", "team", "using", "able", "must", "good"})
        seen: set[str] = set()
        for w in words:
            if w.lower() not in seen and w.lower() not in _stop and len(seen) < 30:
                clean = _sanitize_skill(w)
                if clean:
                    seen.add(w.lower())
                    jd_skill_tuples.append((clean, _categorize_skill(clean)))

    # Soft skills are tracked separately (so they don't inflate "JD skills" counts).
    def _detect_soft_skills(text: str) -> list[str]:
        found: list[str] = []
        for skill, pattern in [
            ("Communication", r"\bcommunication\b"),
            ("Problem Solving", r"\bproblem[\s-]?solving\b"),
            ("Teamwork", r"\bteamwork\b|\bcollaboration\b"),
            ("Leadership", r"\bleadership\b"),
            ("Presentation", r"\bpresentation\b"),
            ("Attention to Detail", r"\battention\s+to\s+detail\b"),
        ]:
            if re.search(pattern, text or "", flags=re.IGNORECASE):
                found.append(skill)
        # Deduplicate while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for s in found:
            k = s.lower()
            if k not in seen:
                seen.add(k)
                out.append(s)
        return out

    jd_soft_detected = _detect_soft_skills(jd_full_text)
    resume_soft_detected = _detect_soft_skills(resume_full_text)

    # If resume_data contains an explicit skills list, merge it in (higher recall than NER).
    try:
        for skill in (resume_data or {}).get("skills", []) or []:
            items = skill.get("items") if isinstance(skill, dict) else None
            if not items:
                continue
            for raw in items:
                for clean in _split_and_sanitize_skill_candidates(raw):
                    resume_skill_tuples.append((clean, _categorize_skill(clean)))
    except Exception:
        pass

    # Post-process categories for consistency (NER categories can be noisy).
    def _normalize_skill_tuples(tuples: list[tuple[str, str]]) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for name, _cat in tuples:
            clean = _sanitize_skill(name)
            if not clean:
                continue
            clean = _canonicalize_skill_name(clean)
            clean = _sanitize_skill(clean)
            if not clean:
                continue
            cat = _categorize_skill(clean)
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((clean, cat))
        return out

    resume_skill_tuples = _normalize_skill_tuples(resume_skill_tuples)
    jd_skill_tuples = _normalize_skill_tuples(jd_skill_tuples)
    raw_resume_skill_count = len(resume_skill_tuples)
    raw_jd_skill_count = len(jd_skill_tuples)

    # ── Stage 3: Semantic Matching ───────────────────────────────────────────
    matched, missing, extra = match_skills_semantic(
        resume_skill_tuples, jd_skill_tuples)
    _log("Stage 3 semantic matching done")

    jd_names = [s for s, _ in jd_skill_tuples]
    alternative_groups = jd_skills_extracted.alternatives or _extract_alternative_skill_groups(jd_full_text, jd_names)
    matched, missing, total_jd_skills, hard_total, soft_total = _apply_alternative_groups(
        matched, missing, jd_skill_tuples, alternative_groups
    )

    print(
        f"[PIPELINE] Resume skills: {raw_resume_skill_count}, JD skills: {raw_jd_skill_count} "
        f"(effective JD total after alternatives: {total_jd_skills})"
    )

    # Deduplicate outputs defensively (prevents duplicate roadmap items / repeated printing).
    def _dedupe_by_name_keep_first(items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        out: list[Any] = []
        for it in items:
            n = getattr(it, "name", "")
            key = str(n).lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    def _dedupe_missing_keep_max_priority(items: list[MissingSkillItem]) -> list[MissingSkillItem]:
        best: dict[str, MissingSkillItem] = {}
        for it in items:
            key = (it.canonical_id or _to_canonical_id(it.name)).lower()
            prev = best.get(key)
            if prev is None or it.priority_score > prev.priority_score:
                best[key] = it
        out = list(best.values())
        out.sort(key=lambda x: x.priority_score, reverse=True)
        return out

    matched = _dedupe_by_name_keep_first(matched)
    extra = _dedupe_by_name_keep_first(extra)
    missing = _dedupe_missing_keep_max_priority(missing)
    _debug_emit(debug_enabled, "stage3_matching", {
        "matched_count": len(matched),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "effective_total_jd_skills": total_jd_skills,
        "alternatives": alternative_groups,
        "matched_preview": [m.name for m in matched[:40]],
        "missing_preview": [m.name for m in missing[:40]],
        "extra_preview": [m.name for m in extra[:40]],
    })

    # Calculate hard/soft skill match percentages.
    # Hard skill match is based on the JD skill list (after alternative-group collapsing).
    hard_matched = [m for m in matched if m.category != "soft"]
    hard_skill_match: float | None = None
    if hard_total:
        hard_skill_match = round(len(hard_matched) / hard_total * 100, 1)

    # Soft skill match is computed separately from text signals so it doesn't inflate JD-skill totals.
    soft_skill_match: float | None = None
    if jd_soft_detected:
        jd_soft_set = {s.lower() for s in jd_soft_detected}
        resume_soft_set = {s.lower() for s in resume_soft_detected}
        soft_matched_count = len(jd_soft_set & resume_soft_set)
        soft_skill_match = round(soft_matched_count / len(jd_soft_set) * 100, 1)

    # ── Stage 4: LLM Reranker ────────────────────────────────────────────────
    scores = await llm_rerank(
        jd_segments,
        resume_segments,
        matched,
        missing,
        total_jd_skills,
        hard_total=hard_total,
        debug=debug_enabled,
    )
    _log("Stage 4 scoring done")
    _debug_emit(debug_enabled, "stage4_scores", scores)

    # Tune skill scoring weights: Hard 80%, Soft 20% (Full-Stack default).
    if hard_skill_match is not None:
        weighted_skill_pct = round(0.8 * hard_skill_match + 0.2 * float(soft_skill_match or 0.0))
        overall_score, skills_score, experience_score, education_score = _calibrate_scores(
            int(scores.get("overall_score", weighted_skill_pct)),
            int(weighted_skill_pct),
            int(scores.get("experience_score", 50)),
            int(scores.get("education_score", 50)),
            int(round(hard_skill_match)),
        )
        scores["overall_score"] = overall_score
        scores["skills_score"] = skills_score
        scores["experience_score"] = experience_score
        scores["education_score"] = education_score

    # ── Stage 5: Gap Report + Roadmap ────────────────────────────────────────
    gap_report = generate_gap_report(matched, missing, scores["overall_score"])
    roadmap = _build_roadmap(missing)
    _debug_emit(debug_enabled, "stage5_gap_roadmap", {
        "gap_report": gap_report,
        "roadmap_counts": {
            "phase_1_core": len(roadmap.phase_1_core),
            "phase_2_primary": len(roadmap.phase_2_primary),
            "phase_3_advanced": len(roadmap.phase_3_advanced),
        },
    })
    _log("Stage 5 gap report done — TOTAL")

    return PipelineResult(
        ats_score=scores["overall_score"],
        skills_score=scores["skills_score"],
        experience_score=scores["experience_score"],
        education_score=scores["education_score"],
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
        hard_skill_match=hard_skill_match,
        soft_skill_match=soft_skill_match,
        total_jd_skills=total_jd_skills,
        gap_report=gap_report,
        roadmap=roadmap,
        reasoning=scores["reasoning"],
        debug=(scores if debug_enabled else None),
    )
