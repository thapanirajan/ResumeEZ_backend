"""
ScoringEngine — weighted skill gap scoring.

Formula
-------
  W_total     = Σ jd_skill.computed_weight   for all JD skills
  Raw_Score   = Σ match.weighted_score       for all matched skills
  Match_%     = min(Raw_Score / W_total, 1.0) × 100

computed_weight per JD skill:
  base_weight × freq_boost × section_boost

  freq_boost   = 1 + (min(freq, 3) - 1) × 0.1   → 1.0x … 1.2x
  section_boost:
    required  → 1.5×
    preferred → 0.8×
    general   → 1.0×

Missing skill priority_score:
  computed_weight × CATEGORY_MULTIPLIER
  Used for roadmap ordering and "top gaps" summary.
"""
from __future__ import annotations

# How much more important is each category vs. the base weight?
_CATEGORY_MULTIPLIER: dict[str, float] = {
    "language":    2.0,
    "framework":   1.7,
    "tool":        1.5,
    "cloud":       1.5,
    "database":    1.4,
    "api":         1.3,
    "ai_ml":       1.8,
    "methodology": 0.8,
    "soft":        0.5,
}

_HARD_CATEGORIES = frozenset(
    ["language", "framework", "tool", "cloud", "database", "api", "ai_ml", "methodology"]
)
_SOFT_CATEGORIES = frozenset(["soft"])

# Section importance boosts applied to computed_weight
_SECTION_BOOST: dict[str, float] = {
    "required":  1.5,
    "preferred": 0.8,
    "general":   1.0,
}


class ScoringEngine:
    """Pure math — no I/O."""

    # ── JD weight computation ─────────────────────────────────────────────────

    def compute_jd_weights(
        self, jd_skills: list[dict], jd_text_lower: str
    ) -> list[dict]:
        """
        Annotate each JD skill with `computed_weight`.
        Modifies the list in-place and returns it.
        """
        for skill in jd_skills:
            name_lower = skill["canonical_name"].lower()
            freq = min(jd_text_lower.count(name_lower), 3)
            # Frequency boost: 1× for freq=1, 1.1× for freq=2, 1.2× for freq=3
            freq_boost = 1.0 + max(freq - 1, 0) * 0.1
            section_boost = _SECTION_BOOST.get(skill.get("section", "general"), 1.0)
            skill["computed_weight"] = round(
                skill["base_weight"] * freq_boost * section_boost, 4
            )
        return jd_skills

    # ── Aggregate scoring ─────────────────────────────────────────────────────

    def compute_scores(
        self,
        matched: list[dict],
        jd_skills: list[dict],
    ) -> dict:
        """
        Returns:
          {
            "match_percentage" : float  (0-100, 1 decimal)
            "hard_skill_match" : float | None
            "soft_skill_match" : float | None
          }
        """
        W_total = sum(s["computed_weight"] for s in jd_skills)
        if W_total == 0:
            return {
                "match_percentage": 0.0,
                "hard_skill_match": None,
                "soft_skill_match": None,
            }

        raw_score = sum(m["weighted_score"] for m in matched)
        match_pct = min(raw_score / W_total, 1.0) * 100.0

        # Category-specific breakdowns
        hard_total = sum(
            s["computed_weight"] for s in jd_skills
            if s.get("category") in _HARD_CATEGORIES
        )
        soft_total = sum(
            s["computed_weight"] for s in jd_skills
            if s.get("category") in _SOFT_CATEGORIES
        )
        hard_matched = sum(
            m["weighted_score"] for m in matched
            if m.get("category") in _HARD_CATEGORIES
        )
        soft_matched = sum(
            m["weighted_score"] for m in matched
            if m.get("category") in _SOFT_CATEGORIES
        )

        return {
            "match_percentage": round(match_pct, 1),
            "hard_skill_match": (
                round(min(hard_matched / hard_total, 1.0) * 100.0, 1)
                if hard_total > 0 else None
            ),
            "soft_skill_match": (
                round(min(soft_matched / soft_total, 1.0) * 100.0, 1)
                if soft_total > 0 else None
            ),
        }

    # ── Missing skill ranking ─────────────────────────────────────────────────

    def rank_missing_skills(self, missing_skills: list[dict]) -> list[dict]:
        """
        Add `priority_score` to each missing skill and sort descending.
        priority_score = computed_weight × CATEGORY_MULTIPLIER
        """
        for skill in missing_skills:
            multiplier = _CATEGORY_MULTIPLIER.get(
                skill.get("category", ""), 1.0
            )
            skill["priority_score"] = round(
                skill["computed_weight"] * multiplier, 3
            )

        return sorted(
            missing_skills,
            key=lambda s: s["priority_score"],
            reverse=True,
        )

    # ── Gap report text ───────────────────────────────────────────────────────

    def generate_gap_report(
        self,
        match_pct: float,
        matched: list[dict],
        missing: list[dict],
        extra: list[dict],
    ) -> str:
        """
        Deterministic human-readable summary of the analysis.
        No LLM — pure rule-based text generation.
        """
        parts: list[str] = [f"Overall skill match: {match_pct:.1f}%."]

        total = len(matched) + len(missing)
        if total > 0:
            parts.append(
                f"Matched {len(matched)} of {total} required skills."
            )

        if missing:
            top_names = ", ".join(s["name"] for s in missing[:3])
            parts.append(f"Top skills to develop: {top_names}.")

        if extra:
            extra_names = ", ".join(s["name"] for s in extra[:3])
            parts.append(
                f"You bring additional skills beyond the JD: {extra_names}."
            )

        if match_pct >= 80:
            parts.append(
                "Strong alignment — you are a competitive candidate for this role."
            )
        elif match_pct >= 60:
            parts.append(
                "Good alignment — closing a few skill gaps will strengthen your application."
            )
        elif match_pct >= 40:
            parts.append(
                "Moderate alignment — significant preparation recommended before applying."
            )
        else:
            parts.append(
                "Low alignment — substantial skill building is needed for this role."
            )

        return " ".join(parts)
