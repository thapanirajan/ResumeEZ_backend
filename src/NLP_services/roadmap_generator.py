"""
RoadmapGenerator — converts missing skills into a structured, ordered
learning roadmap using a topological sort (Kahn's algorithm).

Algorithm
---------
1. BFS-expand missing skills with their prerequisites from the ontology
   dependency graph.  Skills already in the candidate's resume are NOT
   added as prerequisites (they're already known).

2. Topological sort (Kahn's algorithm) over the expanded skill set using
   the dependency graph.  This guarantees:
     - Deterministic ordering (for equal in-degree nodes, sort by name)
     - Prerequisites always appear before the skills that need them

3. Assign skills to three phases:
     Phase 1 (Core)      — prerequisite skills the candidate must learn first
     Phase 2 (Primary)   — directly missing, high-priority skills (priority_score ≥ 1.5)
     Phase 3 (Advanced)  — lower-priority / optional missing skills

4. Enrich each skill with subtopics from the ontology.
"""
from __future__ import annotations

from collections import deque

from src.NLP_services.ontology_service import OntologyService, SkillDict

# Phase boundary: missing skills with priority_score >= this threshold
# go to phase 2, others to phase 3.
_PHASE2_THRESHOLD = 1.5


class RoadmapGenerator:
    """Stateless after construction."""

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        missing_skills: list[dict],
        resume_skill_ids: set[str] | None = None,
    ) -> dict:
        """
        Parameters
        ----------
        missing_skills   : ranked missing skills from ScoringEngine
                           (must have: id, canonical_name, category,
                            priority_score, base_weight, domain)
        resume_skill_ids : set of canonical_ids already in the resume
                           → these are NOT added as prerequisite steps

        Returns
        -------
        {
          "phase_1_core":     [ RoadmapSkill, ... ]
          "phase_2_primary":  [ RoadmapSkill, ... ]
          "phase_3_advanced": [ RoadmapSkill, ... ]
        }

        RoadmapSkill = {
          name, canonical_id, category, domain,
          is_prerequisite, priority_score, subtopics: [str]
        }
        """
        if not missing_skills:
            return {
                "phase_1_core": [],
                "phase_2_primary": [],
                "phase_3_advanced": [],
            }

        known_ids = resume_skill_ids or set()

        # Step 1: expand with prerequisites (BFS)
        expanded = self._expand_with_prerequisites(missing_skills, known_ids)

        # Step 2: topological sort (Kahn's)
        ordered = self._topological_sort(expanded)

        # Step 3: assign to phases + enrich
        return self._assign_phases(
            ordered,
            originally_missing_ids={s["id"] for s in missing_skills},
            priority_map={s["id"]: s.get("priority_score", 0.0) for s in missing_skills},
        )

    # ── Step 1: BFS prerequisite expansion ───────────────────────────────────

    def _expand_with_prerequisites(
        self,
        missing_skills: list[dict],
        known_ids: set[str],
    ) -> dict[str, dict]:
        """
        BFS over the dependency graph starting from missing_skills.
        Adds new nodes when a prerequisite is:
          - not already known by the candidate
          - not already in the expansion set

        Returns {skill_id → skill_dict (with is_prerequisite flag)}.
        """
        all_ids: set[str] = {s["id"] for s in missing_skills}
        result: dict[str, dict] = {}

        for skill in missing_skills:
            entry = skill.copy()
            entry.setdefault("is_prerequisite", False)
            result[skill["id"]] = entry

        queue: deque[dict] = deque(missing_skills)

        while queue:
            current = queue.popleft()
            for prereq in self._ontology.get_prerequisites(current["id"]):
                pid = prereq["id"]
                if pid in known_ids or pid in all_ids:
                    continue
                all_ids.add(pid)
                prereq_entry = prereq.copy()
                prereq_entry["is_prerequisite"] = True
                prereq_entry.setdefault("priority_score", 0.0)
                result[pid] = prereq_entry
                queue.append(prereq_entry)

        return result

    # ── Step 2: Topological sort (Kahn's algorithm) ───────────────────────────

    def _topological_sort(self, skill_map: dict[str, dict]) -> list[dict]:
        """
        Kahn's algorithm over the subgraph induced by skill_map.

        For equal in-degree ties, skills are sorted alphabetically to
        guarantee a deterministic ordering across runs.
        """
        all_ids = set(skill_map.keys())
        in_degree: dict[str, int] = {sid: 0 for sid in all_ids}
        # graph: prerequisite → [skills that need it]
        graph: dict[str, list[str]] = {sid: [] for sid in all_ids}

        for sid in all_ids:
            for prereq in self._ontology.get_prerequisites(sid):
                pid = prereq["id"]
                if pid in all_ids:
                    graph[pid].append(sid)
                    in_degree[sid] += 1

        # Start with skills that have no prerequisites (in this subgraph)
        start_nodes = sorted(
            [sid for sid in all_ids if in_degree[sid] == 0],
            key=lambda sid: skill_map[sid]["canonical_name"],
        )
        queue: deque[str] = deque(start_nodes)
        ordered: list[dict] = []

        while queue:
            current_id = queue.popleft()
            ordered.append(skill_map[current_id])
            # Reduce in-degree of dependents; enqueue when they reach 0
            for dependent_id in sorted(
                graph[current_id],
                key=lambda sid: skill_map[sid]["canonical_name"],
            ):
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        return ordered

    # ── Step 3: Phase assignment + enrichment ─────────────────────────────────

    def _assign_phases(
        self,
        ordered: list[dict],
        originally_missing_ids: set[str],
        priority_map: dict[str, float],
    ) -> dict:
        phases: dict[str, list[dict]] = {
            "phase_1_core": [],
            "phase_2_primary": [],
            "phase_3_advanced": [],
        }

        for skill in ordered:
            sid = skill["id"]

            # Enrich with subtopics from ontology
            roadmap_skill = {
                "name": skill["canonical_name"],
                "canonical_id": sid,
                "category": skill.get("category", ""),
                "domain": skill.get("domain"),
                "is_prerequisite": skill.get("is_prerequisite", False),
                "priority_score": priority_map.get(sid, 0.0),
                "subtopics": self._ontology.get_subtopics(sid),
            }

            if skill.get("is_prerequisite", False):
                phases["phase_1_core"].append(roadmap_skill)
            elif priority_map.get(sid, 0.0) >= _PHASE2_THRESHOLD:
                phases["phase_2_primary"].append(roadmap_skill)
            else:
                phases["phase_3_advanced"].append(roadmap_skill)

        return phases
