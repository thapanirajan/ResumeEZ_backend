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

import httpx
from rapidfuzz import fuzz

# ─── Ollama config (reuse pattern from ollama_service.py) ─────────────────────
_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
_OLLAMA_TIMEOUT = 120.0

# ─── BGE model singleton (lazy load) ──────────────────────────────────────────
_bge_model = None


def _get_bge_model():
    global _bge_model
    if _bge_model is None:
        from sentence_transformers import SentenceTransformer
        _MODEL_PATH = os.path.join(os.path.dirname(__file__), "../../../models/skill_embeddings")
        if os.path.isdir(_MODEL_PATH):
            _bge_model = SentenceTransformer(_MODEL_PATH)
        else:
            _bge_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _bge_model


# ─── spaCy NER model singleton (lazy load) ────────────────────────────────────
_ner_model = None


def _get_ner_model():
    global _ner_model
    if _ner_model is None:
        import spacy
        _NER_PATH = os.path.join(os.path.dirname(__file__), "../../../models/skill_ner/model-best")
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _to_canonical_id(name: str) -> str:
    """Convert a skill name to a stable canonical ID."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower().strip()).strip("_")


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
    if any(w in lower for w in ["machine learning", "deep learning", "tensorflow", "pytorch", "scikit", "nlp", "llm", "ai", "ml", "data science"]):
        return "ai_ml"
    if any(w in lower for w in ["agile", "scrum", "kanban", "ci/cd", "devops", "tdd", "rest", "graphql", "microservices"]):
        return "methodology"
    if any(w in lower for w in ["communication", "leadership", "teamwork", "problem solving", "collaboration", "management", "presentation"]):
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

    if v := resume_data.get("summary"):
        sections["summary"].append(str(v))
    if v := resume_data.get("title"):
        sections["summary"].append(str(v))

    for exp in resume_data.get("experience", []):
        parts = [exp.get("role", ""), exp.get(
            "company", ""), exp.get("description", "")]
        sections["experience"].append(" ".join(p for p in parts if p))

    for edu in resume_data.get("education", []):
        parts = [edu.get("degree", ""), edu.get(
            "fieldOfStudy", ""), edu.get("institution", "")]
        sections["education"].append(" ".join(p for p in parts if p))

    for skill in resume_data.get("skills", []):
        if v := skill.get("items"):
            sections["skills"].append(str(v))
        if v := skill.get("category"):
            sections["skills"].append(str(v))

    for proj in resume_data.get("projects", []):
        parts = [proj.get("name", ""), proj.get(
            "techStack", ""), proj.get("description", "")]
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


# ─── Ollama helper ────────────────────────────────────────────────────────────

async def _call_ollama(prompt: str) -> str:
    """Call Ollama and return raw text response."""
    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            response = await client.post(
                f"{_OLLAMA_BASE}/api/generate",
                json={"model": _OLLAMA_MODEL,
                      "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json().get("response", "")
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

def extract_skills_ner(text: str) -> dict[str, list[str]]:
    """Extract skills using the local spaCy NER model (fast, no network call)."""
    nlp = _get_ner_model()
    if nlp is None:
        return {"technical": [], "frameworks": [], "tools": [], "soft": []}

    _LABEL_MAP = {"TECHNICAL": "technical", "FRAMEWORK": "frameworks", "TOOL": "tools", "SOFT": "soft"}
    result: dict[str, list[str]] = {"technical": [], "frameworks": [], "tools": [], "soft": []}

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
                result[key].append(skill)

    return result


async def extract_skills_from_text(text: str, context: str = "resume") -> dict[str, list[str]]:
    """Extract categorized skills from text.

    Uses the local spaCy NER model first (fast). Falls back to Ollama LLM
    if the NER model is unavailable or returns too few skills (< 3 total).
    """
    if not text.strip():
        return {"technical": [], "frameworks": [], "tools": [], "soft": []}

    # ── Try spaCy NER first ────────────────────────────────────────────────────
    ner_result = extract_skills_ner(text)
    total_ner = sum(len(v) for v in ner_result.values())
    if total_ner >= 3:
        return ner_result

    # ── Fall back to Ollama if NER found too little ────────────────────────────
    prompt = f"""Extract skills from this {context} text. Return ONLY a JSON object with these keys:
- "technical": programming languages (e.g. Python, JavaScript)
- "frameworks": frameworks/libraries (e.g. React, FastAPI, Django)
- "tools": tools/platforms (e.g. Docker, Git, AWS)
- "soft": soft skills (e.g. communication, leadership)

Text:
{text[:2000]}

Return ONLY valid JSON, no explanation. Example:
{{"technical": ["Python"], "frameworks": ["FastAPI"], "tools": ["Docker"], "soft": ["communication"]}}"""

    raw = await _call_ollama(prompt)
    parsed = _extract_json_from_text(raw)

    if isinstance(parsed, dict):
        result: dict[str, list[str]] = {}
        for key in ("technical", "frameworks", "tools", "soft"):
            val = parsed.get(key, [])
            result[key] = [str(s).strip()
                           for s in val if isinstance(s, str) and s.strip()]
        return result

    # Last resort: simple regex extraction
    words = re.findall(r"\b[A-Z][a-zA-Z+#.]{2,}\b", text)
    return {"technical": list(set(words[:20])), "frameworks": [], "tools": [], "soft": []}


def _flatten_skills(skills_dict: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Flatten skill dict to list of (name, category) tuples."""
    result: list[tuple[str, str]] = []
    for category, skills in skills_dict.items():
        cat_label = {
            "technical": "language",
            "frameworks": "framework",
            "tools": "tool",
            "soft": "soft",
        }.get(category, category)
        for s in skills:
            if s.strip():
                result.append((s.strip(), cat_label))
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
    semantic_threshold: float = 0.65,
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
            extra.append(ExtraSkillItem(
                name=r_name,
                canonical_id=_to_canonical_id(r_name),
                category=r_cat,
            ))

    # Sort missing by priority descending
    missing.sort(key=lambda x: x.priority_score, reverse=True)

    return matched, missing, extra


# ─── Stage 4: LLM Reranker ────────────────────────────────────────────────────

async def llm_rerank(
    jd_segments: dict[str, str],
    resume_segments: dict[str, str],
    matched_skills: list[MatchedSkillItem],
    missing_skills: list[MissingSkillItem],
    total_jd_skills: int,
) -> dict[str, Any]:
    """Use Ollama for holistic scoring and section scores."""
    match_pct = round(len(matched_skills) / max(total_jd_skills, 1) * 100)

    matched_names = [s.name for s in matched_skills[:15]]
    missing_names = [s.name for s in missing_skills[:15]]

    prompt = f"""You are an ATS (Applicant Tracking System). Score this candidate against the job.

JOB REQUIREMENTS:
{jd_segments.get('requirements', jd_segments.get('full', ''))[:800]}

CANDIDATE EXPERIENCE:
{resume_segments.get('experience', '')[:600]}

CANDIDATE EDUCATION:
{resume_segments.get('education', '')[:300]}

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

    raw = await _call_ollama(prompt)
    parsed = _extract_json_from_text(raw)

    if isinstance(parsed, dict):
        return {
            "overall_score": min(100, max(0, int(parsed.get("overall_score", match_pct)))),
            "skills_score": min(100, max(0, int(parsed.get("skills_score", match_pct)))),
            "experience_score": min(100, max(0, int(parsed.get("experience_score", 50)))),
            "education_score": min(100, max(0, int(parsed.get("education_score", 50)))),
            "reasoning": str(parsed.get("reasoning", ""))[:500],
        }

    # Fallback: use skill match percentage
    return {
        "overall_score": match_pct,
        "skills_score": match_pct,
        "experience_score": 50,
        "education_score": 50,
        "reasoning": f"Skill match: {match_pct}% ({len(matched_skills)}/{total_jd_skills} skills).",
    }


# ─── Stage 5: Gap Report + Roadmap ────────────────────────────────────────────

async def generate_gap_report(
    matched_skills: list[MatchedSkillItem],
    missing_skills: list[MissingSkillItem],
    overall_score: int,
) -> str:
    """Generate a concise gap analysis narrative."""
    matched_names = [s.name for s in matched_skills[:8]]
    missing_names = [s.name for s in missing_skills[:8]]
    required_missing = [
        s.name for s in missing_skills if s.section == "required"][:5]

    prompt = f"""Write a 2-3 sentence ATS gap analysis for a candidate with {overall_score}% match.
Matched skills: {', '.join(matched_names) if matched_names else 'none'}
Missing skills: {', '.join(missing_names) if missing_names else 'none'}
Required missing: {', '.join(required_missing) if required_missing else 'none'}

Write ONLY the analysis text, no JSON, no bullet points. Be specific and professional."""

    raw = await _call_ollama(prompt)
    # Strip think blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    if raw and len(raw) > 20:
        return raw[:600]

    # Fallback
    if not missing_skills:
        return f"Strong match at {overall_score}%. The candidate demonstrates all required skills."
    if required_missing:
        return (
            f"The candidate achieves a {overall_score}% match. "
            f"Key gaps include: {', '.join(required_missing[:3])}. "
            f"Addressing these would significantly strengthen the application."
        )
    return (
        f"Overall match is {overall_score}%. "
        f"The candidate has {len(matched_skills)} of {len(matched_skills) + len(missing_skills)} required skills."
    )


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
) -> PipelineResult:
    """
    Run the full 5-stage pipeline and return PipelineResult.
    Provide either resume_data (JSON) or resume_text (plain text).
    """
    # ── Stage 1: Segment ────────────────────────────────────────────────────
    jd_segments = segment_jd(jd_text)

    if resume_data is not None:
        resume_segments = segment_resume(resume_data)
    elif resume_text:
        resume_segments = segment_resume_text(resume_text)
    else:
        resume_segments = {"summary": "", "experience": "",
                           "education": "", "skills": "", "projects": ""}

    resume_full_text = " ".join(v for v in resume_segments.values() if v)
    jd_full_text = jd_segments.get("full", jd_text)

    # ── Stage 2: Skill Extraction ────────────────────────────────────────────
    resume_skills_dict = await extract_skills_from_text(resume_full_text, context="resume")
    jd_skills_dict = await extract_skills_from_text(jd_full_text, context="job description")

    resume_skill_tuples = _flatten_skills(resume_skills_dict)
    jd_skill_tuples = _flatten_skills(jd_skills_dict)

    # Fallback: if Ollama returned nothing, use simple keyword extraction
    if not jd_skill_tuples:
        import re as _re
        words = _re.findall(r"\b[A-Za-z][a-zA-Z+#.]{2,}\b", jd_full_text)
        seen: set[str] = set()
        for w in words:
            if w.lower() not in seen and len(seen) < 30:
                seen.add(w.lower())
                jd_skill_tuples.append((w, _categorize_skill(w)))

    # ── Stage 3: Semantic Matching ───────────────────────────────────────────
    matched, missing, extra = match_skills_semantic(
        resume_skill_tuples, jd_skill_tuples)

    total_jd_skills = len(jd_skill_tuples)

    # Calculate hard/soft skill match percentages
    hard_jd = [(s, c) for s, c in jd_skill_tuples if c != "soft"]
    soft_jd = [(s, c) for s, c in jd_skill_tuples if c == "soft"]
    hard_matched = [m for m in matched if m.category != "soft"]
    soft_matched = [m for m in matched if m.category == "soft"]

    hard_skill_match: float | None = None
    soft_skill_match: float | None = None
    if hard_jd:
        hard_skill_match = round(len(hard_matched) / len(hard_jd) * 100, 1)
    if soft_jd:
        soft_skill_match = round(len(soft_matched) / len(soft_jd) * 100, 1)

    # ── Stage 4: LLM Reranker ────────────────────────────────────────────────
    scores = await llm_rerank(jd_segments, resume_segments, matched, missing, total_jd_skills)

    # ── Stage 5: Gap Report + Roadmap ────────────────────────────────────────
    gap_report = await generate_gap_report(matched, missing, scores["overall_score"])
    roadmap = _build_roadmap(missing)

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
    )
