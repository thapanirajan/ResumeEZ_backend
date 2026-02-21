"""
ResumeNormalizer — extracts a canonical skill list from the flexible
resume_data JSONB stored in the Resume model.

Because resume_data has no enforced schema (candidates build resumes via the
UI and the JSON shape varies), this module tries multiple known structures:

  Pattern A:  resume_data.skills = ["Python", "Docker"]
  Pattern B:  resume_data.skills = [{"name": "Python", "years": 3}, ...]
  Pattern C:  resume_data.experience[].skills = ["Python", ...]
  Pattern D:  resume_data.experience[].technologies = ["Docker", ...]
  Pattern E:  resume_data.sections[].{title:"Skills"}.items = [...]
  Pattern F:  resume_data.technicalSkills / resume_data.technical_skills
  Pattern G:  free-text scan of resume_data.summary / resume_data.about

Each extracted raw term is resolved against the ontology (exact, then fuzzy).
Duplicate canonical_ids are merged, keeping the max years_of_experience.
"""
from __future__ import annotations

import re

from src.NLP_services.ontology_service import OntologyService, SkillDict

# Regex to extract years of experience from strings like "5 years", "3+ yr"
_YEARS_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)

_SKILL_SECTION_KEYWORDS = frozenset(
    ["skill", "tech", "technolog", "tool", "language", "framework",
     "competenc", "proficien", "expertise"]
)


class ResumeNormalizer:
    """
    Stateless after construction.  Instantiate once (or per request — it's cheap).
    """

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology

    # ── Public API ────────────────────────────────────────────────────────────

    def extract(self, resume_data: dict) -> list[dict]:
        """
        Returns a deduplicated list of dicts:
          {
            "canonical_id"  : str,
            "canonical_name": str,
            "category"      : str,
            "domain"        : str | None,
            "base_weight"   : float,
            "years"         : float,        # 0 if unknown
            "match_type"    : "exact" | "fuzzy",
            "confidence"    : float,
          }
        """
        if not resume_data or not isinstance(resume_data, dict):
            return []

        raw_entries = self._gather_raw_entries(resume_data)
        return self._resolve_and_deduplicate(raw_entries)

    # ── Gathering raw skill strings ───────────────────────────────────────────

    def _gather_raw_entries(self, data: dict) -> list[dict]:
        """
        Returns list of {"name": str, "years": float} from all known patterns.
        """
        raw: list[dict] = []

        # ── Pattern A/B: top-level `skills` key ───────────────────────────
        raw.extend(self._from_skills_key(data.get("skills") or []))
        raw.extend(self._from_skills_key(data.get("Skills") or []))

        # ── Pattern F: alternative naming conventions ─────────────────────
        raw.extend(self._from_skills_key(data.get("technicalSkills") or []))
        raw.extend(self._from_skills_key(data.get("technical_skills") or []))
        raw.extend(self._from_skills_key(data.get("softSkills") or []))
        raw.extend(self._from_skills_key(data.get("soft_skills") or []))
        raw.extend(self._from_skills_key(data.get("tools") or []))
        raw.extend(self._from_skills_key(data.get("technologies") or []))

        # ── Pattern C/D: experience[].skills / experience[].technologies ──
        for exp_key in ("experience", "workExperience", "work_experience",
                        "employment", "jobs", "positions"):
            raw.extend(self._from_experience(data.get(exp_key) or []))

        # ── Pattern E: sections array with a skill-related title ──────────
        raw.extend(self._from_sections(data.get("sections") or []))

        # ── Pattern G: free-text summary scan ─────────────────────────────
        for text_key in ("summary", "about", "objective", "profile", "bio"):
            raw.extend(self._from_free_text(data.get(text_key) or ""))

        return raw

    def _from_skills_key(self, skills: list) -> list[dict]:
        result = []
        for item in skills:
            if isinstance(item, str) and item.strip():
                result.append({"name": item.strip(), "years": 0.0})
            elif isinstance(item, dict):
                name = (
                    item.get("name") or item.get("skill")
                    or item.get("title") or item.get("label") or ""
                )
                if not name.strip():
                    continue
                years = self._parse_years(
                    item.get("years") or item.get("experience")
                    or item.get("yearsOfExperience") or 0
                )
                result.append({"name": name.strip(), "years": years})
        return result

    def _from_experience(self, experience: list) -> list[dict]:
        result = []
        for job in experience:
            if not isinstance(job, dict):
                continue
            for key in ("skills", "technologies", "tools", "tech_stack",
                        "techStack", "languages"):
                items = job.get(key) or []
                result.extend(self._from_skills_key(items))
        return result

    def _from_sections(self, sections: list) -> list[dict]:
        result = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            title = str(section.get("title") or section.get("name") or "").lower()
            if not any(kw in title for kw in _SKILL_SECTION_KEYWORDS):
                continue
            for content_key in ("items", "content", "data", "list", "skills"):
                items = section.get(content_key) or []
                result.extend(self._from_skills_key(
                    items if isinstance(items, list) else []
                ))
        return result

    def _from_free_text(self, text: str) -> list[dict]:
        """
        Last-resort: scan a free-text field for known ontology terms.
        Lower confidence — only accepts exact ontology matches (no fuzzy here
        to avoid false positives from natural language).
        """
        if not text or not isinstance(text, str):
            return []
        result = []
        text_lower = text.lower()
        for synonym in self._ontology.get_all_synonyms():
            if f" {synonym} " in f" {text_lower} ":
                skill = self._ontology.lookup(synonym)
                if skill:
                    result.append({"name": synonym, "years": 0.0})
        return result

    # ── Resolution & deduplication ────────────────────────────────────────────

    def _resolve_and_deduplicate(self, raw_entries: list[dict]) -> list[dict]:
        """
        Resolve each raw entry to a canonical skill, then merge duplicates
        by keeping the maximum years_of_experience seen for that skill.
        """
        merged: dict[str, dict] = {}  # canonical_id → resolved dict

        for entry in raw_entries:
            name = entry["name"]
            years = entry["years"]

            skill, confidence, match_type = self._lookup(name)
            if skill is None:
                continue

            cid = skill["id"]
            if cid in merged:
                # Keep the highest years seen
                merged[cid]["years"] = max(merged[cid]["years"], years)
            else:
                merged[cid] = {
                    **skill,
                    "years": years,
                    "match_type": match_type,
                    "confidence": confidence,
                }

        return list(merged.values())

    def _lookup(self, term: str) -> tuple[SkillDict | None, float, str]:
        # Exact
        skill = self._ontology.lookup(term)
        if skill:
            return skill, 1.0, "exact"
        # Fuzzy
        skill, confidence = self._ontology.fuzzy_lookup(term)
        if skill:
            return skill, confidence, "fuzzy"
        return None, 0.0, "none"

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_years(value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = _YEARS_RE.search(value)
            if match:
                return float(match.group(1))
        return 0.0
