"""
Stage 2 NER replacement for ai_pipeline_service.py
===================================================
Replaces the Ollama-based extract_skills_from_text() with a
local spaCy NER model. Same input/output signature. No async needed.

INTEGRATION:
  1. Copy this block into ai_pipeline_service.py
  2. Replace the old extract_skills_from_text() function entirely
  3. Copy models/skill_ner/ into backend/models/skill_ner/

Speed: ~3-8 seconds per call (×2) → ~50ms per call (×2)
"""

import os
import re

# ─── NER model singleton (same lazy-load pattern as _bge_model) ───────────────
_ner_model = None


def _get_ner_model():
    """Load spaCy NER model once, reuse forever."""
    global _ner_model
    if _ner_model is None:
        import spacy
        # Look for fine-tuned model first, fall back gracefully
        _MODEL_PATH = os.path.join(
            os.path.dirname(__file__),
            "../../../models/skill_ner/model-best"
        )
        if os.path.isdir(_MODEL_PATH):
            _ner_model = spacy.load(_MODEL_PATH)
        else:
            # Fallback: blank model (will use regex fallback below)
            _ner_model = spacy.blank("en")
            print(f"[WARNING] NER model not found at {_MODEL_PATH}. Using regex fallback.")
    return _ner_model


# ─── Label → pipeline key mapping ────────────────────────────────────────────
_LABEL_TO_KEY = {
    "TECHNICAL": "technical",
    "FRAMEWORK": "frameworks",
    "TOOL":      "tools",
    "SOFT":      "soft",
}

# ─── Regex fallback (same as old code's fallback) ────────────────────────────
_KNOWN_SOFT_SKILLS = {
    "communication", "leadership", "teamwork", "collaboration",
    "problem solving", "time management", "adaptability", "creativity",
    "critical thinking", "attention to detail", "project management",
    "analytical thinking", "decision making", "conflict resolution",
    "presentation", "mentoring", "coaching", "organization",
}


def _regex_fallback(text: str) -> dict[str, list[str]]:
    """Simple regex extraction when NER model is unavailable."""
    words = re.findall(r"\b[A-Z][a-zA-Z+#.]{2,}\b", text)
    soft = [w for w in words if w.lower() in _KNOWN_SOFT_SKILLS]
    tech = [w for w in words if w.lower() not in _KNOWN_SOFT_SKILLS]
    return {
        "technical":  list(dict.fromkeys(tech[:15])),
        "frameworks": [],
        "tools":      [],
        "soft":       list(dict.fromkeys(soft[:10])),
    }


# ─── REPLACEMENT FUNCTION ─────────────────────────────────────────────────────
# DROP THIS IN — it's async to match the original signature,
# but does no I/O (runs fully locally in ~50ms)

async def extract_skills_from_text(
    text: str,
    context: str = "resume"
) -> dict[str, list[str]]:
    """
    Extract categorized skills using local spaCy NER model.
    Replaces Ollama-based version. Same signature, same output format.

    Returns:
        {
            "technical":  ["Python", "SQL", ...],
            "frameworks": ["FastAPI", "React", ...],
            "tools":      ["Docker", "AWS", ...],
            "soft":       ["communication", ...],
        }
    """
    if not text.strip():
        return {"technical": [], "frameworks": [], "tools": [], "soft": []}

    nlp = _get_ner_model()

    # Blank model means NER isn't loaded — use regex fallback
    if not nlp.pipe_names:
        return _regex_fallback(text)

    # Run NER on first 2000 chars (same limit as old Ollama prompt)
    doc = nlp(text[:2000])

    result: dict[str, list[str]] = {
        "technical":  [],
        "frameworks": [],
        "tools":      [],
        "soft":       [],
    }

    seen: set[str] = set()
    for ent in doc.ents:
        key = _LABEL_TO_KEY.get(ent.label_)
        if key is None:
            continue
        name = ent.text.strip()
        name_lower = name.lower()
        if name_lower not in seen and len(name) > 1:
            seen.add(name_lower)
            result[key].append(name)

    # If NER found nothing (edge case), try regex as safety net
    total = sum(len(v) for v in result.values())
    if total == 0:
        return _regex_fallback(text)

    return result


# ─── WHAT TO CHANGE IN ai_pipeline_service.py ────────────────────────────────
"""
CHANGES NEEDED (2 things):

1. Add _get_ner_model() and updated extract_skills_from_text() above
   (replace the entire old extract_skills_from_text function)

2. Remove the Ollama import dependency for Stage 2 — the function
   no longer calls _call_ollama(), so if Stage 4 and 5 also get
   replaced later, you can remove _call_ollama() entirely.

FILE STRUCTURE after integration:
  backend/
    models/
      skill_ner/
        model-best/        ← copy from stage2/models/skill_ner/model-best/
          config.cfg
          meta.json
          ner/
          ...
      skill_embeddings/    ← from Stage 3
    src/
      services/
        ai_pipeline_service.py   ← updated

NO OTHER CHANGES NEEDED. The function signature is identical.
The pipeline calls it the same way:
    resume_skills_dict = await extract_skills_from_text(resume_full_text, context="resume")
    jd_skills_dict     = await extract_skills_from_text(jd_full_text, context="job description")
"""
