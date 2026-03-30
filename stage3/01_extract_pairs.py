"""
Step 1: Extract synonym pairs from ESCO dataset
Output: data/positive_pairs.jsonl, data/negative_pairs.jsonl
"""

import csv
import json
import random
import os

os.makedirs("data", exist_ok=True)

# ── 1. Load digital skills URIs (tech filter) ─────────────────────────────────
digital_uris = set()
with open("/mnt/user-data/uploads/digitalSkillsCollection_en.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        digital_uris.add(row["conceptUri"].strip())

print(f"Digital skill URIs loaded: {len(digital_uris)}")

# ── 2. Extract preferredLabel + altLabels from skills_en.csv ──────────────────
all_skills = []       # (uri, preferredLabel, [altLabels])
tech_skills = []      # same but only digital/tech skills

with open("/mnt/user-data/uploads/skills_en.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        uri = row["conceptUri"].strip()
        preferred = row["preferredLabel"].strip()
        alt_raw = row["altLabels"].strip()
        alts = [a.strip() for a in alt_raw.split("\n") if a.strip()] if alt_raw else []

        entry = (uri, preferred, alts)
        all_skills.append(entry)
        if uri in digital_uris:
            tech_skills.append(entry)

print(f"Total skills: {len(all_skills)}")
print(f"Tech/digital skills: {len(tech_skills)}")

# ── 3. Generate positive pairs ─────────────────────────────────────────────────
# For each skill: (preferredLabel, altLabel) = positive pair
# Also: (altLabel1, altLabel2) = positive pair (same skill, different names)

positive_pairs = []

for uri, preferred, alts in all_skills:
    # preferred ↔ each alt
    for alt in alts:
        positive_pairs.append({
            "sentence1": preferred,
            "sentence2": alt,
            "label": 1.0,
            "source": "esco_preferred_alt"
        })
    # alt ↔ alt (all combinations, capped at 3 to avoid explosion)
    if len(alts) >= 2:
        pairs = [(alts[i], alts[j]) for i in range(len(alts)) for j in range(i+1, len(alts))]
        for a, b in pairs[:3]:
            positive_pairs.append({
                "sentence1": a,
                "sentence2": b,
                "label": 1.0,
                "source": "esco_alt_alt"
            })

print(f"ESCO positive pairs: {len(positive_pairs)}")

# ── 4. Add manual tech synonym pairs (ESCO misses abbreviations) ───────────────
manual_synonyms = [
    # Programming languages
    ("JS", "JavaScript"),
    ("JS", "ECMAScript"),
    ("TS", "TypeScript"),
    ("Py", "Python"),
    ("C#", "C Sharp"),
    ("Golang", "Go"),
    ("Kotlin", "Kotlin/JVM"),
    # Databases
    ("Postgres", "PostgreSQL"),
    ("Postgres", "pg"),
    ("MongoDB", "Mongo"),
    ("MySQL", "My SQL"),
    ("MSSQL", "Microsoft SQL Server"),
    ("SQLite", "SQLite3"),
    ("Redis", "Redis Cache"),
    ("Elasticsearch", "Elastic Search"),
    ("ElasticSearch", "ES"),
    # Cloud & DevOps
    ("k8s", "Kubernetes"),
    ("K8s", "Kubernetes"),
    ("AWS", "Amazon Web Services"),
    ("GCP", "Google Cloud Platform"),
    ("GCP", "Google Cloud"),
    ("Azure", "Microsoft Azure"),
    ("CI/CD", "Continuous Integration and Deployment"),
    ("CI/CD", "Continuous Integration/Continuous Deployment"),
    ("IaC", "Infrastructure as Code"),
    ("TF", "Terraform"),
    # Frameworks & Libraries
    ("React", "ReactJS"),
    ("React", "React.js"),
    ("Next", "Next.js"),
    ("NextJS", "Next.js"),
    ("Vue", "Vue.js"),
    ("VueJS", "Vue.js"),
    ("Node", "Node.js"),
    ("NodeJS", "Node.js"),
    ("Express", "ExpressJS"),
    ("Express", "Express.js"),
    ("FastAPI", "Fast API"),
    ("DRF", "Django REST Framework"),
    ("Spring Boot", "SpringBoot"),
    # ML / AI
    ("ML", "Machine Learning"),
    ("DL", "Deep Learning"),
    ("AI", "Artificial Intelligence"),
    ("NLP", "Natural Language Processing"),
    ("CV", "Computer Vision"),
    ("LLM", "Large Language Model"),
    ("Gen AI", "Generative AI"),
    ("RAG", "Retrieval Augmented Generation"),
    ("RL", "Reinforcement Learning"),
    ("PyTorch", "Py Torch"),
    ("TensorFlow", "Tensorflow"),
    ("TF", "TensorFlow"),
    ("HuggingFace", "Hugging Face"),
    ("sklearn", "scikit-learn"),
    ("scikit learn", "scikit-learn"),
    # Data
    ("ETL", "Extract Transform Load"),
    ("ELT", "Extract Load Transform"),
    ("BI", "Business Intelligence"),
    ("DW", "Data Warehouse"),
    ("EDA", "Exploratory Data Analysis"),
    ("Pandas", "pandas"),
    ("NumPy", "numpy"),
    # DevTools
    ("Git", "GitHub"),
    ("Git", "Version Control"),
    ("Docker", "Containerization"),
    ("REST", "RESTful API"),
    ("REST API", "RESTful API"),
    ("GraphQL", "Graph QL"),
    ("gRPC", "GRPC"),
    # Soft Skills
    ("comm", "communication"),
    ("collab", "collaboration"),
    ("PM", "Project Management"),
    ("Agile", "Agile Methodology"),
    ("Scrum", "Scrum Methodology"),
]

for s1, s2 in manual_synonyms:
    positive_pairs.append({
        "sentence1": s1,
        "sentence2": s2,
        "label": 1.0,
        "source": "manual_tech"
    })
    # Add reverse too
    positive_pairs.append({
        "sentence1": s2,
        "sentence2": s1,
        "label": 1.0,
        "source": "manual_tech_reverse"
    })

print(f"Total positive pairs (with manual): {len(positive_pairs)}")

# ── 5. Generate negative pairs ─────────────────────────────────────────────────
# Strategy: pair skills from DIFFERENT skill groups = not synonyms
# Use tech vs non-tech as a clean separation, then random cross-pairs

tech_labels = [preferred for _, preferred, _ in tech_skills]
all_labels = [preferred for _, preferred, _ in all_skills if preferred not in tech_labels]

random.seed(42)
negative_pairs = []

# Hard negatives: tech skill vs non-tech skill (clearly different domains)
non_tech_sample = random.sample(all_labels, min(1000, len(all_labels)))
tech_sample = random.sample(tech_labels, min(1000, len(tech_labels)))

for t, nt in zip(tech_sample[:500], non_tech_sample[:500]):
    negative_pairs.append({
        "sentence1": t,
        "sentence2": nt,
        "label": 0.0,
        "source": "tech_vs_nontecht"
    })

# Semi-hard negatives: two different tech skills (similar domain, not synonyms)
shuffled_tech = tech_labels.copy()
random.shuffle(shuffled_tech)
for i in range(0, min(500, len(shuffled_tech) - 1), 2):
    if shuffled_tech[i] != shuffled_tech[i+1]:
        negative_pairs.append({
            "sentence1": shuffled_tech[i],
            "sentence2": shuffled_tech[i+1],
            "label": 0.2,   # not 0.0 — same domain, just different tools
            "source": "tech_vs_tech"
        })

print(f"Negative pairs: {len(negative_pairs)}")

# ── 6. Save to JSONL ────────────────────────────────────────────────────────────
with open("data/positive_pairs.jsonl", "w") as f:
    for p in positive_pairs:
        f.write(json.dumps(p) + "\n")

with open("data/negative_pairs.jsonl", "w") as f:
    for p in negative_pairs:
        f.write(json.dumps(p) + "\n")

print("\n✅ Done!")
print(f"  data/positive_pairs.jsonl → {len(positive_pairs)} pairs")
print(f"  data/negative_pairs.jsonl → {len(negative_pairs)} pairs")
print(f"  Total training examples: {len(positive_pairs) + len(negative_pairs)}")
