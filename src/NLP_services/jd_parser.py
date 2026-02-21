"""
JDParser — converts raw Job Description text into a list of canonical skills.

Pipeline:
  1. Normalize text (lowercase, remove HTML, collapse whitespace)
  2. Run spaCy PhraseMatcher to find multi-word skill mentions in one pass
  3. Walk remaining tokens and try single-word ontology lookups
  4. For any term not found by exact lookup, try RapidFuzz fallback
  5. Deduplicate by canonical_id
  6. Detect JD sections (required / preferred) and tag each skill accordingly

The JDParser is instantiated ONCE at startup (after the ontology is loaded)
and reused across all requests as a module-level singleton.
"""
from __future__ import annotations

import hashlib
import re

import spacy
from spacy.matcher import PhraseMatcher

from src.NLP_services.ontology_service import OntologyService, SkillDict

try:
    _nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError(
        "spaCy model 'en_core_web_sm' not found.\n"
        "Run: python -m spacy download en_core_web_sm"
    )

# ── Boilerplate patterns to strip before skill extraction ─────────────────────
_BOILERPLATE = re.compile(
    r"(equal opportunity employer|affirmative action|we are an eoe"
    r"|apply now|about us|about the company|about the role intro)",
    re.IGNORECASE,
)

# ── Section header markers ─────────────────────────────────────────────────────
_REQUIRED_MARKERS = frozenset(
    ["required", "must have", "must-have", "essential", "mandatory", "requirements",
     "what you need", "you must have", "minimum qualifications", "basic qualifications"]
)
_PREFERRED_MARKERS = frozenset(
    ["preferred", "nice to have", "good to have", "bonus", "plus", "desirable",
     "desired", "ideally", "optional", "advantageous"]
)

# ── Singleton state ────────────────────────────────────────────────────────────
_parser_instance: "JDParser | None" = None


class JDParser:
    """
    Stateless after construction.  Build once, call `.parse()` per request.
    """

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology
        self._phrase_matcher = self._build_phrase_matcher()

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self, raw_jd: str) -> dict:
        """
        Main entry point.

        Returns:
          {
            "jd_hash":         str,           # SHA-256 of normalised text
            "canonical_skills": [SkillDict with extras],  # deduped, weighted
          }

        Each SkillDict is augmented with:
          - "match_type"    : "exact" | "fuzzy"
          - "confidence"    : float 0-1
          - "section"       : "required" | "preferred" | "general"
        """
        normalised = _normalise_text(raw_jd)
        jd_hash = hashlib.sha256(normalised.encode("utf-8")).hexdigest()

        section_map = _build_section_map(normalised)

        doc = _nlp(normalised)

        # Step 1: multi-word matches (high precision)
        matched_spans, span_positions = self._extract_multiword(doc)

        # Step 2: single-token fallback for positions not covered by spans
        single_candidates = self._extract_single_tokens(doc, span_positions)

        # Step 3: resolve all candidates to canonical skills
        all_raw = matched_spans + single_candidates
        canonical = self._resolve_and_deduplicate(all_raw, section_map, normalised)

        return {
            "jd_hash": jd_hash,
            "canonical_skills": canonical,
        }

    # ── Construction helpers ──────────────────────────────────────────────────

    def _build_phrase_matcher(self) -> PhraseMatcher:
        """
        Build a spaCy PhraseMatcher from all multi-word synonyms in the ontology.
        Uses LOWER attribute → case-insensitive matching.

        Single-word synonyms are handled by per-token dict lookup (faster).
        """
        matcher = PhraseMatcher(_nlp.vocab, attr="LOWER")
        multi_word_docs = [
            _nlp.make_doc(syn)
            for syn in self._ontology.get_all_synonyms()
            if len(syn.split()) > 1  # only multi-word
        ]
        if multi_word_docs:
            matcher.add("SKILLS", multi_word_docs)
        return matcher

    # ── Extraction steps ──────────────────────────────────────────────────────

    def _extract_multiword(
        self, doc
    ) -> tuple[list[str], set[int]]:
        """
        Run PhraseMatcher and return:
          - list of matched surface strings
          - set of token positions covered (to skip in single-token pass)

        Overlapping matches: keep longest.
        """
        matches = self._phrase_matcher(doc)
        # Sort by start, then by length descending (prefer longer)
        matches.sort(key=lambda m: (m[1], -(m[2] - m[1])))

        surface_strings: list[str] = []
        covered: set[int] = set()
        for _, start, end in matches:
            if any(i in covered for i in range(start, end)):
                continue  # skip overlapping shorter match
            surface_strings.append(doc[start:end].text)
            covered.update(range(start, end))

        return surface_strings, covered

    def _extract_single_tokens(
        self, doc, skip_positions: set[int]
    ) -> list[str]:
        """
        Walk tokens not already covered by phrase matches.
        Only consider NOUN / PROPN tokens that are not stop words.
        Also accept any token whose lemma or text exists in the synonym map.
        """
        candidates: list[str] = []
        for i, token in enumerate(doc):
            if i in skip_positions:
                continue
            if token.is_stop or token.is_punct or len(token.text) <= 2:
                continue
            text = token.text
            lemma = token.lemma_

            # Fast exact check first to avoid unnecessary candidates
            if (self._ontology.lookup(text) is not None
                    or self._ontology.lookup(lemma) is not None
                    or token.pos_ in ("NOUN", "PROPN")):
                candidates.append(text)

        return candidates

    # ── Resolution ────────────────────────────────────────────────────────────

    def _resolve_and_deduplicate(
        self,
        raw_terms: list[str],
        section_map: dict[str, str],
        jd_lower: str,
    ) -> list[dict]:
        """
        For each raw term:
          1. Try exact ontology lookup
          2. If not found, try fuzzy lookup (threshold 82)
          3. Annotate with section and confidence
          4. Deduplicate by canonical_id (keep first occurrence)
        """
        seen_ids: set[str] = set()
        result: list[dict] = []

        for term in raw_terms:
            skill, confidence, match_type = self._lookup(term)
            if skill is None:
                continue
            if skill["id"] in seen_ids:
                continue
            seen_ids.add(skill["id"])

            section = _detect_section(
                skill["canonical_name"].lower(), section_map, jd_lower
            )

            result.append({
                **skill,
                "match_type": match_type,
                "confidence": confidence,
                "section": section,
            })

        return result

    def _lookup(
        self, term: str
    ) -> tuple[SkillDict | None, float, str]:
        """
        Returns (skill_dict | None, confidence, match_type).
        """
        # Exact
        skill = self._ontology.lookup(term)
        if skill:
            return skill, 1.0, "exact"

        # Fuzzy fallback
        skill, confidence = self._ontology.fuzzy_lookup(term)
        if skill:
            return skill, confidence, "fuzzy"

        return None, 0.0, "none"


# ── Singleton factory ─────────────────────────────────────────────────────────

def get_jd_parser() -> JDParser:
    """Return the singleton JDParser, built from the loaded OntologyService."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = JDParser(OntologyService.get_instance())
    return _parser_instance


def rebuild_jd_parser() -> None:
    """
    Call this after a hot-reload of the ontology (e.g. version bump).
    Rebuilds the PhraseMatcher from the updated synonym pool.
    """
    global _parser_instance
    _parser_instance = JDParser(OntologyService.get_instance())


# ── Text normalisation ────────────────────────────────────────────────────────

def _normalise_text(text: str) -> str:
    """
    Clean raw JD text before NLP processing.
    Preserves characters that are meaningful in tech skill names:
      - "+" in "C++", "Google+"
      - "." in "Node.js", ".NET"
      - "#" in "C#"
      - "/" for paths/acronyms
    """
    if not text:
        return ""

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove boilerplate
    text = _BOILERPLATE.sub(" ", text)

    # Lowercase
    text = text.lower()

    # Collapse unicode whitespace + excessive newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Section detection ─────────────────────────────────────────────────────────

def _build_section_map(jd_lower: str) -> dict[str, str]:
    """
    Walk lines and build a map: {line_content → section_label}.
    section_label ∈ {"required", "preferred", "general"}

    Only changes section when a short line (<60 chars) matches a marker.
    """
    section_map: dict[str, str] = {}
    current_section = "general"

    for line in jd_lower.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if len(stripped) < 60:
            if any(m in stripped for m in _REQUIRED_MARKERS):
                current_section = "required"
            elif any(m in stripped for m in _PREFERRED_MARKERS):
                current_section = "preferred"

        section_map[stripped] = current_section

    return section_map


def _detect_section(
    skill_lower: str,
    section_map: dict[str, str],
    jd_lower: str,
) -> str:
    """
    Find the first line in the JD that contains the skill name and return
    its section label.  Falls back to 'general'.
    """
    for line, section in section_map.items():
        if skill_lower in line:
            return section
    return "general"
