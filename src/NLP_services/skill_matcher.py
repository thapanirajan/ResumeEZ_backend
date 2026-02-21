"""
SkillMatchingEngine — compares canonical resume skills vs canonical JD skills.

By the time this module runs, both sides have already been resolved to
canonical IDs by JDParser and ResumeNormalizer.  Matching is therefore
a fast set intersection on UUIDs.

Output per matched skill includes an experience_multiplier so that a
candidate with 5 years of Python scores higher than one with 6 months.
"""
from __future__ import annotations

# ── Experience multiplier table ───────────────────────────────────────────────
#
# Rationale:
#   ≥ 5 yr → 1.2 : Senior — exceeds most JD requirements
#   ≥ 3 yr → 1.1 : Mid-level — solid match
#   ≥ 1 yr → 1.0 : Baseline expectation met
#   > 0 yr → 0.85: Some exposure, sub-optimal
#     0 yr → 0.70: Listed but no experience noted
#
_EXP_TABLE = [(5.0, 1.2), (3.0, 1.1), (1.0, 1.0), (0.01, 0.85)]
_EXP_DEFAULT = 0.70


def _experience_multiplier(years: float) -> float:
    for threshold, multiplier in _EXP_TABLE:
        if years >= threshold:
            return multiplier
    return _EXP_DEFAULT


class SkillMatchingEngine:
    """
    Pure in-memory comparison — no I/O, no external dependencies.
    Instantiate once and reuse across requests.
    """

    def match(
        self,
        resume_skills: list[dict],
        jd_skills: list[dict],
    ) -> dict:
        """
        Parameters
        ----------
        resume_skills : list of dicts from ResumeNormalizer
            Each dict must have at least: id, canonical_name, category,
            years (float), confidence (float)
        jd_skills : list of dicts from JDParser (already weight-enriched
            by ScoringEngine.compute_jd_weights)
            Each dict must have: id, canonical_name, category,
            computed_weight (float), confidence (float)

        Returns
        -------
        {
          "matched" : [ {name, canonical_id, match_type, confidence,
                         category, weighted_score, years} ]
          "missing" : [ {name, canonical_id, category, computed_weight,
                         confidence, section} ]   ← JD skills not found
          "extra"   : [ {name, canonical_id, category} ]   ← resume extras
        }
        """
        resume_by_id: dict[str, dict] = {s["id"]: s for s in resume_skills}
        jd_by_id: dict[str, dict] = {s["id"]: s for s in jd_skills}

        matched: list[dict] = []
        missing: list[dict] = []

        for jd_id, jd_skill in jd_by_id.items():
            if jd_id in resume_by_id:
                r_skill = resume_by_id[jd_id]
                exp_mult = _experience_multiplier(r_skill.get("years", 0.0))

                # Overall confidence = min of extraction confidence on both
                # sides (fuzzy on either side lowers the effective confidence)
                confidence = min(
                    r_skill.get("confidence", 1.0),
                    jd_skill.get("confidence", 1.0),
                )

                # Determine match type for transparency in the response
                r_type = r_skill.get("match_type", "exact")
                j_type = jd_skill.get("match_type", "exact")
                match_type = "exact" if (r_type == "exact" and j_type == "exact") else "fuzzy"

                weighted_score = (
                    jd_skill["computed_weight"] * confidence * exp_mult
                )

                matched.append({
                    "name": jd_skill["canonical_name"],
                    "canonical_id": jd_id,
                    "match_type": match_type,
                    "confidence": round(confidence, 3),
                    "category": jd_skill.get("category", ""),
                    "years": r_skill.get("years", 0.0),
                    "weighted_score": round(weighted_score, 4),
                })
            else:
                missing.append({
                    "name": jd_skill["canonical_name"],
                    "canonical_id": jd_id,
                    "category": jd_skill.get("category", ""),
                    "computed_weight": jd_skill["computed_weight"],
                    "confidence": jd_skill.get("confidence", 1.0),
                    "section": jd_skill.get("section", "general"),
                    "base_weight": jd_skill.get("base_weight", 1.0),
                    "domain": jd_skill.get("domain"),
                })

        matched_ids = {m["canonical_id"] for m in matched}
        extra = [
            {
                "name": s["canonical_name"],
                "canonical_id": s["id"],
                "category": s.get("category", ""),
            }
            for s in resume_skills
            if s["id"] not in jd_by_id and s["id"] not in matched_ids
        ]

        return {"matched": matched, "missing": missing, "extra": extra}
