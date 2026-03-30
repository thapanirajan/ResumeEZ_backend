"""
Step 3: Train spaCy NER model using Python API directly
(bypasses CLI training loop which has issues on Windows with long paths)

Run: python3 03_train_ner.py
Output: models/skill_ner/model-best/
Time:   ~5-10 min on CPU
"""

import random
import os
import spacy
from spacy.training import Example
from spacy.tokens import DocBin
from spacy.scorer import Scorer

random.seed(42)
os.makedirs("models/skill_ner/model-best", exist_ok=True)
os.makedirs("models/skill_ner/model-last", exist_ok=True)

# ── Load .spacy data ────────────────────────────────────────────────────────────
def load_data(path: str, nlp) -> list[Example]:
    db = DocBin().from_disk(path)
    docs = list(db.get_docs(nlp.vocab))
    examples = []
    for doc in docs:
        entities = [(e.start_char, e.end_char, e.label_) for e in doc.ents]
        ex = Example.from_dict(nlp.make_doc(doc.text), {"entities": entities})
        examples.append(ex)
    return examples


def evaluate(nlp, dev_data: list[Example]) -> dict:
    scorer = Scorer()
    preds = []
    for ex in dev_data:
        pred_doc = nlp(ex.reference.text)
        preds.append(Example(pred_doc, ex.reference))
    return scorer.score(preds)


# ── Build blank NER model ───────────────────────────────────────────────────────
print("Building model...")
nlp = spacy.blank("en")
ner = nlp.add_pipe("ner", last=True)
for label in ["TECHNICAL", "FRAMEWORK", "TOOL", "SOFT"]:
    ner.add_label(label)

# ── Load data ───────────────────────────────────────────────────────────────────
print("Loading training data...")
train_data = load_data("data/train.spacy", nlp)
dev_data   = load_data("data/dev.spacy",   nlp)
print(f"  Train: {len(train_data)} examples")
print(f"  Dev:   {len(dev_data)} examples")

if len(train_data) == 0:
    print("ERROR: No training examples. Run 01_generate_ner_data.py first.")
    raise SystemExit(1)

# Count entities in training data
n_ents = sum(len(ex.reference.ents) for ex in train_data)
print(f"  Training entities: {n_ents}")

# ── Hyperparams ─────────────────────────────────────────────────────────────────
EPOCHS     = 40
BATCH_SIZE = 32
DROP       = 0.3
EVAL_EVERY = 3     # evaluate every N epochs
PATIENCE   = 5     # stop if no improvement for N eval cycles

# ── Initialize ──────────────────────────────────────────────────────────────────
optimizer = nlp.initialize(lambda: iter(train_data))

print(f"\nTraining for up to {EPOCHS} epochs (batch={BATCH_SIZE}, dropout={DROP})")
print(f"{'Epoch':>6} {'NER Loss':>10} {'ENTS_F':>8} {'ENTS_P':>8} {'ENTS_R':>8}  Status")
print("─" * 60)

best_f = 0.0
no_improve = 0

for epoch in range(1, EPOCHS + 1):
    # ── Train one epoch ─────────────────────────────────────────────────────────
    random.shuffle(train_data)
    losses = {}
    for batch in spacy.util.minibatch(train_data, size=BATCH_SIZE):
        nlp.update(batch, sgd=optimizer, drop=DROP, losses=losses)

    # ── Evaluate every EVAL_EVERY epochs ────────────────────────────────────────
    if epoch % EVAL_EVERY == 0 or epoch == 1:
        scores = evaluate(nlp, dev_data)
        f = scores.get("ents_f", 0.0)
        p = scores.get("ents_p", 0.0)
        r = scores.get("ents_r", 0.0)
        loss = losses.get("ner", 0.0)

        if f > best_f:
            best_f = f
            no_improve = 0
            nlp.to_disk("models/skill_ner/model-best")
            status = "✓ best"
        else:
            no_improve += 1
            status = f"  ({no_improve}/{PATIENCE} patience)"

        print(f"{epoch:>6} {loss:>10.1f} {f:>8.3f} {p:>8.3f} {r:>8.3f}  {status}")

        if no_improve >= PATIENCE:
            print(f"\nEarly stop: no improvement for {PATIENCE} eval cycles.")
            break
    else:
        loss = losses.get("ner", 0.0)
        print(f"{epoch:>6} {loss:>10.1f}")

# ── Save final model ────────────────────────────────────────────────────────────
nlp.to_disk("models/skill_ner/model-last")

print(f"\nBest ENTS_F: {best_f:.3f}")
if best_f >= 0.6:
    print("✅ Training successful! Run python3 04_verify_ner.py")
elif best_f > 0:
    print("⚠️  Model partially learned. Try raising EPOCHS or BATCH_SIZE.")
    print("   Run python3 04_verify_ner.py to check.")
else:
    print("❌ Model didn't learn. Check that 01_generate_ner_data.py was run first.")
