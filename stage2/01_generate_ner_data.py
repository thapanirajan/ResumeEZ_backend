"""
Step 1: Generate spaCy NER training data from ESCO datasets
Output: data/train.spacy, data/dev.spacy

Labels:
  TECHNICAL  → programming languages (Python, JavaScript, SQL)
  FRAMEWORK  → frameworks/libraries (React, FastAPI, Django)
  TOOL       → tools/platforms (Docker, Git, AWS)
  SOFT       → soft skills (communication, leadership)

Run: python3 01_generate_ner_data.py
"""

import csv
import json
import random
import os
import re

random.seed(42)

# ── CSV paths ──────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ESCO_DIR = os.path.join(_HERE, "ESCO dataset - v1.2.1 - classification - en - csv")
DIGITAL_SKILLS_CSV     = os.path.join(_ESCO_DIR, "digitalSkillsCollection_en.csv")
TRANSVERSAL_SKILLS_CSV = os.path.join(_ESCO_DIR, "transversalSkillsCollection_en.csv")

# ── Category mapping from ESCO broaderConceptPT → NER label ───────────────────
TECHNICAL_CATEGORIES = {
    "computer programming",
    "programming computer systems",
}

FRAMEWORK_CATEGORIES = {
    "software and applications development and analysis",
    "designing ict systems or applications",
}

TOOL_CATEGORIES = {
    "database and network design and administration",
    "managing, gathering and storing digital data",
    "setting up computer systems",
    "using computer aided design and drawing tools",
    "using digital tools for collaboration and productivity",
    "computer use",
    "audio-visual techniques and media production",
    "electronics and automation",
    "managing information",
    "operating audio-visual equipment",
    "using digital tools to control machinery",
}

# ── Known overrides (ESCO sometimes miscategorizes common tech skills) ─────────
LABEL_OVERRIDES = {
    # Force TECHNICAL
    "python": "TECHNICAL", "javascript": "TECHNICAL", "java": "TECHNICAL",
    "typescript": "TECHNICAL", "c++": "TECHNICAL", "c#": "TECHNICAL",
    "go": "TECHNICAL", "rust": "TECHNICAL", "ruby": "TECHNICAL",
    "php": "TECHNICAL", "scala": "TECHNICAL", "kotlin": "TECHNICAL",
    "swift": "TECHNICAL", "r": "TECHNICAL", "matlab": "TECHNICAL",
    "sql": "TECHNICAL", "html": "TECHNICAL", "css": "TECHNICAL",
    "bash": "TECHNICAL", "shell": "TECHNICAL", "perl": "TECHNICAL",
    "haskell": "TECHNICAL", "erlang": "TECHNICAL", "elixir": "TECHNICAL",
    # Force FRAMEWORK
    "react": "FRAMEWORK", "vue": "FRAMEWORK", "angular": "FRAMEWORK",
    "django": "FRAMEWORK", "flask": "FRAMEWORK", "fastapi": "FRAMEWORK",
    "spring": "FRAMEWORK", "express": "FRAMEWORK", "rails": "FRAMEWORK",
    "next.js": "FRAMEWORK", "nuxt": "FRAMEWORK", "laravel": "FRAMEWORK",
    "tensorflow": "FRAMEWORK", "pytorch": "FRAMEWORK", "keras": "FRAMEWORK",
    "scikit-learn": "FRAMEWORK", "pandas": "FRAMEWORK", "numpy": "FRAMEWORK",
    "spark": "FRAMEWORK", "hadoop": "FRAMEWORK",
    # Force TOOL
    "docker": "TOOL", "kubernetes": "TOOL", "git": "TOOL",
    "jenkins": "TOOL", "terraform": "TOOL", "ansible": "TOOL",
    "aws": "TOOL", "gcp": "TOOL", "azure": "TOOL",
    "postgresql": "TOOL", "mysql": "TOOL", "mongodb": "TOOL",
    "redis": "TOOL", "elasticsearch": "TOOL", "nginx": "TOOL",
    "linux": "TOOL", "jira": "TOOL", "figma": "TOOL",
}


def get_label(preferred_label: str, broader: str) -> str:
    """Determine NER label for a digital skill."""
    lower = preferred_label.lower().strip()

    # Check overrides first
    if lower in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[lower]

    # Check broader category
    for cat in broader.split("|"):
        cat = cat.strip().lower()
        if cat in TECHNICAL_CATEGORIES:
            return "TECHNICAL"
        if cat in FRAMEWORK_CATEGORIES:
            return "FRAMEWORK"
        if cat in TOOL_CATEGORIES:
            return "TOOL"

    # Default: TOOL (safe fallback for digital skills)
    return "TOOL"


# ── Load skills ────────────────────────────────────────────────────────────────
print("Loading ESCO skills...")

digital_skills: list[tuple[str, str]] = []  # (name, label)
with open(DIGITAL_SKILLS_CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        name = row["preferredLabel"].strip()
        broader = row.get("broaderConceptPT", "")
        # Skip multi-word action phrases (keep nouns/tools, skip "use X", "manage Y")
        if len(name.split()) <= 4 and not name.lower().startswith(("use ", "manage ", "develop ", "implement ", "design ", "create ", "define ", "operate ", "apply ")):
            label = get_label(name, broader)
            digital_skills.append((name, label))

soft_skills: list[str] = []
with open(TRANSVERSAL_SKILLS_CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        name = row["preferredLabel"].strip()
        # Keep short, clear soft skill names
        if len(name.split()) <= 4:
            soft_skills.append(name)

print(f"  Digital skills loaded: {len(digital_skills)}")
print(f"  Soft skills loaded:    {len(soft_skills)}")

# Label distribution
from collections import Counter
label_counts = Counter(l for _, l in digital_skills)
print(f"  Label distribution: {dict(label_counts)}")

# ── Extra manually curated tech skills not in ESCO ────────────────────────────
extra_skills: list[tuple[str, str]] = [
    # TECHNICAL
    ("Python", "TECHNICAL"), ("JavaScript", "TECHNICAL"), ("TypeScript", "TECHNICAL"),
    ("Java", "TECHNICAL"), ("C++", "TECHNICAL"), ("C#", "TECHNICAL"),
    ("Go", "TECHNICAL"), ("Rust", "TECHNICAL"), ("Ruby", "TECHNICAL"),
    ("PHP", "TECHNICAL"), ("Scala", "TECHNICAL"), ("Kotlin", "TECHNICAL"),
    ("Swift", "TECHNICAL"), ("SQL", "TECHNICAL"), ("HTML", "TECHNICAL"),
    ("CSS", "TECHNICAL"), ("Bash", "TECHNICAL"), ("R", "TECHNICAL"),
    # FRAMEWORK
    ("React", "FRAMEWORK"), ("Vue.js", "FRAMEWORK"), ("Angular", "FRAMEWORK"),
    ("Next.js", "FRAMEWORK"), ("Django", "FRAMEWORK"), ("Flask", "FRAMEWORK"),
    ("FastAPI", "FRAMEWORK"), ("Spring Boot", "FRAMEWORK"), ("Express.js", "FRAMEWORK"),
    ("TensorFlow", "FRAMEWORK"), ("PyTorch", "FRAMEWORK"), ("scikit-learn", "FRAMEWORK"),
    ("Pandas", "FRAMEWORK"), ("NumPy", "FRAMEWORK"), ("Laravel", "FRAMEWORK"),
    ("Ruby on Rails", "FRAMEWORK"), ("ASP.NET", "FRAMEWORK"), ("Keras", "FRAMEWORK"),
    ("LangChain", "FRAMEWORK"), ("Celery", "FRAMEWORK"),
    # TOOL
    ("Docker", "TOOL"), ("Kubernetes", "TOOL"), ("Git", "TOOL"),
    ("GitHub", "TOOL"), ("GitLab", "TOOL"), ("Jenkins", "TOOL"),
    ("Terraform", "TOOL"), ("Ansible", "TOOL"), ("AWS", "TOOL"),
    ("GCP", "TOOL"), ("Azure", "TOOL"), ("PostgreSQL", "TOOL"),
    ("MySQL", "TOOL"), ("MongoDB", "TOOL"), ("Redis", "TOOL"),
    ("Elasticsearch", "TOOL"), ("NGINX", "TOOL"), ("Linux", "TOOL"),
    ("Jira", "TOOL"), ("Figma", "TOOL"), ("Postman", "TOOL"),
    ("VS Code", "TOOL"), ("Grafana", "TOOL"), ("Prometheus", "TOOL"),
    ("RabbitMQ", "TOOL"), ("Kafka", "TOOL"), ("FAISS", "TOOL"),
    ("Ollama", "TOOL"), ("Hugging Face", "TOOL"), ("spaCy", "TOOL"),
    # SOFT
    ("communication", "SOFT"), ("leadership", "SOFT"), ("teamwork", "SOFT"),
    ("problem solving", "SOFT"), ("collaboration", "SOFT"), ("time management", "SOFT"),
    ("critical thinking", "SOFT"), ("adaptability", "SOFT"), ("creativity", "SOFT"),
    ("attention to detail", "SOFT"), ("project management", "SOFT"),
    ("analytical thinking", "SOFT"), ("decision making", "SOFT"),
    ("conflict resolution", "SOFT"), ("presentation", "SOFT"),
]

# Merge all skills
all_tech_skills = digital_skills + extra_skills
soft_skill_list = soft_skills + [s for s, l in extra_skills if l == "SOFT"]
soft_skill_list = list(set(soft_skill_list))

print(f"\nTotal tech skills for NER training: {len(all_tech_skills)}")
print(f"Total soft skills for NER training: {len(soft_skill_list)}")

# ── Sentence templates ─────────────────────────────────────────────────────────
# Each template has a {SKILL} placeholder — we'll fill it and record the span

RESUME_TEMPLATES = [
    "Proficient in {SKILL} with hands-on project experience.",
    "Strong experience with {SKILL} in production environments.",
    "Worked extensively with {SKILL} during internship.",
    "Built and maintained systems using {SKILL}.",
    "Developed backend APIs using {SKILL}.",
    "Used {SKILL} to implement data pipelines.",
    "Delivered features using {SKILL} across 3 projects.",
    "Experienced with {SKILL} and related tooling.",
    "Hands-on experience in {SKILL}.",
    "{SKILL} — 2 years of professional experience.",
    "Led a team using {SKILL} for a large-scale product.",
    "Expertise in {SKILL}, {SKILL2}, and related technologies.",
    "Skilled in {SKILL} for cloud-native deployments.",
    "Implemented CI/CD workflows with {SKILL}.",
    "Deep understanding of {SKILL} internals and best practices.",
    "Contributed to open-source projects using {SKILL}.",
    "Automated workflows using {SKILL} and shell scripting.",
    "Core stack: {SKILL}, {SKILL2}, and {SKILL3}.",
    "Technical skills: {SKILL}, {SKILL2}.",
    "Languages: {SKILL}, {SKILL2}.",
    "Tools and technologies: {SKILL}, {SKILL2}, {SKILL3}.",
    "Familiar with {SKILL} through coursework and side projects.",
    "Deployed applications on {SKILL}.",
    "Managed infrastructure with {SKILL}.",
]

JD_TEMPLATES = [
    "The ideal candidate should have experience with {SKILL}.",
    "You will be working with {SKILL} on a daily basis.",
    "Required: proficiency in {SKILL}.",
    "Experience with {SKILL} is mandatory.",
    "Must have knowledge of {SKILL}.",
    "We are looking for someone skilled in {SKILL}.",
    "Hands-on experience with {SKILL} required.",
    "Strong command of {SKILL} is essential.",
    "{SKILL} is a core part of our tech stack.",
    "You will use {SKILL} to build scalable services.",
    "We expect familiarity with {SKILL} and {SKILL2}.",
    "Technical requirements: {SKILL}, {SKILL2}, and {SKILL3}.",
    "Nice to have: experience with {SKILL}.",
    "Bonus: {SKILL} knowledge.",
    "2+ years of {SKILL} experience preferred.",
    "Daily responsibilities include working with {SKILL}.",
]

SOFT_RESUME_TEMPLATES = [
    "Demonstrated strong {SKILL} in cross-functional team settings.",
    "Known for excellent {SKILL} and attention to detail.",
    "Developed {SKILL} through leading a team of 5 engineers.",
    "Applied {SKILL} to resolve complex stakeholder issues.",
    "Praised for {SKILL} in peer reviews.",
    "Strong {SKILL} skills developed across 3 years.",
]

SOFT_JD_TEMPLATES = [
    "Excellent {SKILL} skills are required.",
    "We value candidates who demonstrate strong {SKILL}.",
    "Must possess strong {SKILL} and interpersonal abilities.",
    "The role demands {SKILL} and the ability to work independently.",
    "Good {SKILL} is essential for this position.",
]


def make_span(text: str, skill: str) -> tuple[int, int] | None:
    """Find skill's character span in text (case-insensitive)."""
    idx = text.lower().find(skill.lower())
    if idx >= 0:
        return (idx, idx + len(skill))
    return None


def generate_records(
    skills: list[tuple[str, str]],
    soft_skills: list[str],
    n_records: int = 5000,
) -> list[dict]:
    """Generate synthetic NER training records."""
    records = []
    all_templates = RESUME_TEMPLATES + JD_TEMPLATES
    soft_templates = SOFT_RESUME_TEMPLATES + SOFT_JD_TEMPLATES

    # Single-skill sentences
    for _ in range(n_records // 2):
        skill_name, label = random.choice(skills)
        template = random.choice(all_templates)
        if "{SKILL2}" in template or "{SKILL3}" in template:
            continue  # Skip multi-skill templates here
        text = template.replace("{SKILL}", skill_name)
        span = make_span(text, skill_name)
        if span:
            records.append({
                "text": text,
                "entities": [(*span, label)]
            })

    # Multi-skill sentences (2-3 skills)
    for _ in range(n_records // 4):
        skill1_name, label1 = random.choice(skills)
        skill2_name, label2 = random.choice(skills)
        if skill1_name == skill2_name:
            continue
        template = random.choice([t for t in all_templates if "{SKILL2}" in t])
        text = template.replace("{SKILL}", skill1_name).replace("{SKILL2}", skill2_name)
        if "{SKILL3}" in text:
            skill3_name, label3 = random.choice(skills)
            text = text.replace("{SKILL3}", skill3_name)
            span1, span2 = make_span(text, skill1_name), make_span(text, skill2_name)
            span3 = make_span(text, skill3_name)
            entities = [e for e in [
                (*span1, label1) if span1 else None,
                (*span2, label2) if span2 else None,
                (*span3, label3) if span3 else None,
            ] if e]
        else:
            span1 = make_span(text, skill1_name)
            span2 = make_span(text, skill2_name)
            entities = [e for e in [
                (*span1, label1) if span1 else None,
                (*span2, label2) if span2 else None,
            ] if e]

        if entities:
            # Check no overlapping spans
            spans_sorted = sorted(entities, key=lambda x: x[0])
            valid = True
            for i in range(len(spans_sorted) - 1):
                if spans_sorted[i][1] > spans_sorted[i+1][0]:
                    valid = False
                    break
            if valid:
                records.append({"text": text, "entities": entities})

    # Soft skill sentences
    for _ in range(n_records // 4):
        skill_name = random.choice(soft_skills)
        template = random.choice(soft_templates)
        text = template.replace("{SKILL}", skill_name)
        span = make_span(text, skill_name)
        if span:
            records.append({
                "text": text,
                "entities": [(*span, "SOFT")]
            })

    random.shuffle(records)
    return records


print("\nGenerating training records...")
all_records = generate_records(all_tech_skills, soft_skill_list, n_records=6000)
print(f"Generated {len(all_records)} records")

# ── Convert to spaCy binary format ────────────────────────────────────────────
import spacy
from spacy.tokens import DocBin

nlp = spacy.blank("en")

def records_to_docbin(records: list[dict]) -> DocBin:
    db = DocBin()
    skipped = 0
    for record in records:
        doc = nlp.make_doc(record["text"])
        ents = []
        for start, end, label in record["entities"]:
            span = doc.char_span(start, end, label=label)
            if span is not None:
                ents.append(span)
            else:
                skipped += 1
        doc.ents = ents
        db.add(doc)
    if skipped:
        print(f"  Skipped {skipped} misaligned spans (tokenization boundary)")
    return db

# 85/15 train/dev split
random.shuffle(all_records)
split = int(len(all_records) * 0.85)
train_records = all_records[:split]
dev_records = all_records[split:]

print(f"\nConverting to spaCy format...")
train_db = records_to_docbin(train_records)
dev_db = records_to_docbin(dev_records)

train_db.to_disk("data/train.spacy")
dev_db.to_disk("data/dev.spacy")

print(f"\n✅ Done!")
print(f"  data/train.spacy → {len(train_records)} records")
print(f"  data/dev.spacy   → {len(dev_records)} records")
print(f"\nNext: run python3 02_init_config.py, then python3 03_train_ner.py")
