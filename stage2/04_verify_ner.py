"""
Step 4: Verify the trained NER model
Run AFTER 03_train_ner.py completes.

Tests the model on realistic resume and JD text samples.
"""

import spacy

MODEL_PATH = "./models/skill_ner/model-best"

print(f"Loading model from {MODEL_PATH}...")
nlp = spacy.load(MODEL_PATH)

# ── Test samples ───────────────────────────────────────────────────────────────
RESUME_SAMPLE = """
Senior Software Engineer with 5 years of experience. Built microservices 
using Python and FastAPI, deployed on AWS with Docker and Kubernetes.
Managed PostgreSQL databases and Redis caching layers. Strong experience 
with React for frontend development and TypeScript. Used Git for version 
control and Jenkins for CI/CD pipelines. Excellent communication skills 
and strong teamwork in cross-functional teams.
"""

JD_SAMPLE = """
We are looking for a backend engineer with strong Python skills. 
The ideal candidate should have experience with Django or FastAPI frameworks.
Must have hands-on experience with Docker and Kubernetes for container 
orchestration. Knowledge of PostgreSQL and MongoDB is required.
AWS cloud experience is mandatory. Experience with React is a plus.
Strong communication skills and ability to work collaboratively.
"""

SKILLS_SECTION = """
Technical Skills: Python, JavaScript, TypeScript, SQL
Frameworks: React, Next.js, FastAPI, Django  
Tools: Docker, Git, AWS, PostgreSQL, Redis, Kubernetes
Soft Skills: leadership, communication, problem solving
"""

def test_text(text: str, label: str):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    doc = nlp(text)

    result = {"TECHNICAL": [], "FRAMEWORK": [], "TOOL": [], "SOFT": []}
    for ent in doc.ents:
        if ent.label_ in result:
            if ent.text.strip() not in result[ent.label_]:
                result[ent.label_].append(ent.text.strip())

    for label, skills in result.items():
        if skills:
            print(f"  {label:12s}: {', '.join(skills)}")

    total = sum(len(v) for v in result.values())
    print(f"\n  Total skills extracted: {total}")
    return result


r1 = test_text(RESUME_SAMPLE, "RESUME TEXT")
r2 = test_text(JD_SAMPLE, "JOB DESCRIPTION")
r3 = test_text(SKILLS_SECTION, "SKILLS SECTION")

# ── Verify output matches pipeline's expected format ──────────────────────────
def to_pipeline_format(ner_result: dict) -> dict:
    """Convert NER labels back to pipeline's expected keys."""
    return {
        "technical":  ner_result.get("TECHNICAL", []),
        "frameworks": ner_result.get("FRAMEWORK", []),
        "tools":      ner_result.get("TOOL", []),
        "soft":       ner_result.get("SOFT", []),
    }

print("\n\n" + "="*55)
print("  Pipeline format output (what your code receives)")
print("="*55)
import json
print(json.dumps(to_pipeline_format(r1), indent=2))

# ── Key assertions ─────────────────────────────────────────────────────────────
print("\n\n" + "="*55)
print("  Key assertions")
print("="*55)

checks = [
    ("Python in TECHNICAL",    "Python"     in r1.get("TECHNICAL", [])),
    ("FastAPI in FRAMEWORK",   "FastAPI"    in r1.get("FRAMEWORK", [])),
    ("Docker in TOOL",         "Docker"     in r1.get("TOOL", [])),
    ("AWS in TOOL",            "AWS"        in r1.get("TOOL", [])),
    ("React in FRAMEWORK",     "React"      in r1.get("FRAMEWORK", [])),
    ("PostgreSQL in TOOL",     "PostgreSQL" in r1.get("TOOL", [])),
]

passed = 0
for name, result in checks:
    status = "✅" if result else "❌"
    print(f"  {status} {name}")
    if result:
        passed += 1

print(f"\n  Passed: {passed}/{len(checks)}")

if passed >= 4:
    print("\n✅ Model is working well. Ready to integrate into pipeline.")
    print("\n  Copy models/skill_ner/ into your backend:")
    print("  backend/models/skill_ner/model-best/")
else:
    print("\n⚠️  Model needs improvement.")
    print("  Try: increase --training.max_epochs to 30 in 03_train_ner.py")
    print("  Or:  add more records in 01_generate_ner_data.py (raise n_records to 10000)")
