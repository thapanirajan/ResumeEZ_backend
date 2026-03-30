"""
Step 2: Fine-tune BAAI/bge-small-en-v1.5 on ESCO synonym pairs
Output: models/skill_embeddings/  (drop-in replacement for your current BGE model)

Usage: python3 02_train_embeddings.py
Time:  ~5-10 min on CPU, ~2 min on GPU
"""

import json
import random
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_MODEL     = "BAAI/bge-small-en-v1.5"   # same model your pipeline uses now
OUTPUT_PATH    = "./models/skill_embeddings"
EPOCHS         = 4        # reduced: 10 epochs with 26:1 imbalance caused collapse
BATCH_SIZE     = 64
WARMUP_STEPS   = 100
MAX_PAIRS      = 5000     # fewer positives to improve positive:negative ratio

random.seed(42)

# ── Hard negatives: clearly different tech skills (must score LOW) ─────────────
HARD_NEGATIVES = [
    # Different languages
    ("Python", "Kubernetes"),
    ("Java", "Docker"),
    ("JavaScript", "PostgreSQL"),
    ("Go", "React"),
    ("Rust", "TensorFlow"),
    ("C++", "MongoDB"),
    # Frontend vs backend
    ("React", "Angular"),
    ("Vue.js", "Django"),
    ("Next.js", "FastAPI"),
    ("Svelte", "Spring Boot"),
    ("React", "Express.js"),
    # Frontend vs infra
    ("React", "Terraform"),
    ("Angular", "Kubernetes"),
    ("Vue.js", "AWS"),
    # Backend vs data
    ("Django", "scikit-learn"),
    ("FastAPI", "TensorFlow"),
    ("Node.js", "PyTorch"),
    # Infra vs data
    ("Kubernetes", "pandas"),
    ("Docker", "NumPy"),
    ("Terraform", "Machine Learning"),
    ("AWS", "Natural Language Processing"),
    # DB vs ML
    ("PostgreSQL", "Computer Vision"),
    ("MongoDB", "Deep Learning"),
    ("Redis", "scikit-learn"),
    # Hard: same ecosystem, not synonyms
    ("React", "Redux"),
    ("Python", "Django"),
    ("JavaScript", "Node.js"),
    ("SQL", "NoSQL"),
    ("Docker", "Kubernetes"),
    ("Git", "GitHub Actions"),
    ("AWS", "Azure"),
    ("GCP", "Azure"),
    # Soft skill vs tech
    ("communication", "Python"),
    ("leadership", "Docker"),
    ("project management", "React"),
    ("teamwork", "Kubernetes"),
]

# ── Load pairs ─────────────────────────────────────────────────────────────────
def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]

positive = load_jsonl("data/positive_pairs.jsonl")
negative = load_jsonl("data/negative_pairs.jsonl")

# Fix: tech_vs_tech negatives in the file use label 0.2 — relabel to 0.0
# (React vs Angular are NOT synonyms regardless of same domain)
for p in negative:
    if p.get("source") == "tech_vs_tech":
        p["label"] = 0.0

# Sample positives down to MAX_PAIRS
# Prioritise: manual tech pairs first (most relevant to your pipeline)
manual   = [p for p in positive if "manual" in p["source"]]
esco     = [p for p in positive if "esco"   in p["source"]]

random.shuffle(esco)
selected_positive = manual + esco[:MAX_PAIRS - len(manual)]

# Combine file negatives + hard negatives
hard_neg_pairs = [
    {"sentence1": s1, "sentence2": s2, "label": 0.0, "source": "hard_negative"}
    for s1, s2 in HARD_NEGATIVES
]
# Add both directions
hard_neg_pairs += [
    {"sentence1": s2, "sentence2": s1, "label": 0.0, "source": "hard_negative_rev"}
    for s1, s2 in HARD_NEGATIVES
]
selected_negative = negative + hard_neg_pairs

all_pairs = selected_positive + selected_negative
random.shuffle(all_pairs)

print(f"Training on {len(all_pairs)} pairs")
print(f"  Positive (manual tech): {len(manual)}")
print(f"  Positive (ESCO):        {len(selected_positive) - len(manual)}")
print(f"  Negative:               {len(selected_negative)}")

# ── Build InputExamples ────────────────────────────────────────────────────────
train_examples = [
    InputExample(texts=[p["sentence1"], p["sentence2"]], label=float(p["label"]))
    for p in all_pairs
]

# ── Load base model ────────────────────────────────────────────────────────────
print(f"\nLoading base model: {BASE_MODEL}")
model = SentenceTransformer(BASE_MODEL)

# ── Train ──────────────────────────────────────────────────────────────────────
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=BATCH_SIZE)
train_loss = losses.CosineSimilarityLoss(model)

print(f"Training for {EPOCHS} epochs...")
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=EPOCHS,
    warmup_steps=WARMUP_STEPS,
    output_path=OUTPUT_PATH,
    show_progress_bar=True,
)

print(f"\n✅ Model saved to {OUTPUT_PATH}")
print("\nNext step — in ai_pipeline_service.py change line ~36:")
print('  BEFORE: _bge_model = SentenceTransformer("BAAI/bge-small-en-v1.5")')
print('  AFTER:  _bge_model = SentenceTransformer("./models/skill_embeddings")')
print("\nAlso lower semantic_threshold from 0.75 → 0.65")
