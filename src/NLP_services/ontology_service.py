"""
OntologyService — in-memory singleton that caches the entire skill ontology
after the first DB load at application startup.

All lookups are O(1) dictionary operations after load.
This class is the single gateway between raw text terms and canonical skills.
"""
from __future__ import annotations

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.skill_ontology_model import (
    SkillDependency,
    SkillOntology,
    SkillSubtopic,
    SkillSynonym,
)

# ──────────────────────────────────────────────────────────────────────────────
# Type alias used throughout the NLP pipeline
# ──────────────────────────────────────────────────────────────────────────────
SkillDict = dict  # {id, canonical_name, category, domain, base_weight}


class OntologyService:
    """
    Loaded once at startup, then used read-only during every request.

    Internal data structures:
      _synonym_map   : {lowercase_synonym -> SkillDict}
      _skills_by_id  : {str(uuid)         -> SkillDict}
      _prerequisites  : {str(uuid)         -> [str(uuid), ...]}
      _subtopics     : {str(uuid)         -> [str, ...]}
      _synonym_list  : flat list of all synonym strings (for rapidfuzz pool)
    """

    _instance: "OntologyService | None" = None

    def __init__(self) -> None:
        self._synonym_map: dict[str, SkillDict] = {}
        self._skills_by_id: dict[str, SkillDict] = {}
        self._prerequisites: dict[str, list[str]] = {}
        self._subtopics: dict[str, list[str]] = {}
        self._synonym_list: list[str] = []
        self.ontology_version: str = "1.0"
        self.is_loaded: bool = False

    # ── Singleton access ──────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "OntologyService":
        if cls._instance is None:
            cls._instance = OntologyService()
        return cls._instance

    # ── Startup loader ────────────────────────────────────────────────────────

    async def load(self, db: AsyncSession) -> None:
        """
        Pull every active skill + synonyms + subtopics from PostgreSQL into
        memory.  Dependencies are loaded in a separate query.

        Called once inside FastAPI's lifespan after `create_all`.
        """
        # ── 1. Skills ──────────────────────────────────────────────────────
        skill_rows = (
            await db.execute(
                select(SkillOntology).where(SkillOntology.is_active.is_(True))
            )
        ).scalars().all()

        for skill in skill_rows:
            sid = str(skill.id)
            skill_dict: SkillDict = {
                "id": sid,
                "canonical_name": skill.canonical_name,
                "category": skill.category,
                "domain": skill.domain,
                "base_weight": skill.base_weight,
            }
            self._skills_by_id[sid] = skill_dict

            # Canonical name is always a valid lookup term
            self._synonym_map[skill.canonical_name.lower()] = skill_dict

        # ── 2. Synonyms ────────────────────────────────────────────────────
        syn_rows = (await db.execute(select(SkillSynonym))).scalars().all()
        for syn in syn_rows:
            sid = str(syn.skill_id)
            if sid in self._skills_by_id:
                self._synonym_map[syn.synonym.lower()] = self._skills_by_id[sid]

        # ── 3. Dependencies ───────────────────────────────────────────────
        dep_rows = (await db.execute(select(SkillDependency))).scalars().all()
        for dep in dep_rows:
            sid = str(dep.skill_id)
            pid = str(dep.prerequisite_id)
            if sid not in self._prerequisites:
                self._prerequisites[sid] = []
            self._prerequisites[sid].append(pid)

        # ── 4. Subtopics ───────────────────────────────────────────────────
        sub_rows = (
            await db.execute(
                select(SkillSubtopic).order_by(SkillSubtopic.order_index)
            )
        ).scalars().all()
        for sub in sub_rows:
            sid = str(sub.skill_id)
            if sid not in self._subtopics:
                self._subtopics[sid] = []
            self._subtopics[sid].append(sub.subtopic)

        # ── 5. Build rapidfuzz pool ────────────────────────────────────────
        self._synonym_list = list(self._synonym_map.keys())

        self.is_loaded = True

    # ── Lookup methods ────────────────────────────────────────────────────────

    def lookup(self, term: str) -> SkillDict | None:
        """
        O(1) exact lookup (case-insensitive).
        Returns canonical SkillDict or None.
        """
        return self._synonym_map.get(term.strip().lower())

    def fuzzy_lookup(
        self, term: str, threshold: int = 82
    ) -> tuple[SkillDict | None, float]:
        """
        Fuzzy lookup using RapidFuzz token_set_ratio against the full synonym
        pool.  Returns (SkillDict | None, confidence 0-1).

        token_set_ratio handles:
          - "Machine Learning" vs "ML Engineering"
          - "NodeJS" vs "Node.js" (already synonym-mapped, but edge cases)
          - Typos up to ~18% character error rate

        Threshold 82 chosen empirically:
          - "Python" vs "PyTorch" → ~60  ✗ (correctly rejected)
          - "Node.js" vs "NodeJS"  → ~95  ✓ (synonym already covers, fallback)
          - "Postgres" vs "PostgreSQL" → ~85 ✓
        """
        if not self._synonym_list:
            return None, 0.0

        result = process.extractOne(
            term.strip().lower(),
            self._synonym_list,
            scorer=fuzz.token_set_ratio,
        )
        if result is None:
            return None, 0.0

        best_match, score, _ = result
        if score >= threshold:
            return self._synonym_map.get(best_match), score / 100.0
        return None, 0.0

    def get_skill(self, skill_id: str) -> SkillDict | None:
        return self._skills_by_id.get(skill_id)

    def get_prerequisites(self, skill_id: str) -> list[SkillDict]:
        """Return list of prerequisite SkillDicts for the given skill."""
        prereq_ids = self._prerequisites.get(skill_id, [])
        return [
            self._skills_by_id[pid]
            for pid in prereq_ids
            if pid in self._skills_by_id
        ]

    def get_subtopics(self, skill_id: str) -> list[str]:
        return self._subtopics.get(skill_id, [])

    def get_all_synonyms(self) -> list[str]:
        """All synonym strings — used by JDParser to build PhraseMatcher."""
        return self._synonym_list.copy()

    def get_all_skills(self) -> list[SkillDict]:
        return list(self._skills_by_id.values())

    def skill_count(self) -> int:
        return len(self._skills_by_id)
