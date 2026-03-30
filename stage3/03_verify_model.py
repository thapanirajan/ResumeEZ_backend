"""
Step 3: Verify the fine-tuned model
Run AFTER 02_train_embeddings.py completes.

Tests that known synonyms score high and non-synonyms score low.
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def test_model(model, name):
    print(f"\n{'='*50}")
    print(f"Model: {name}")
    print(f"{'='*50}")

    test_cases = [
        # Should be HIGH (synonyms)
        ("JS",              "JavaScript",          "synonym",  True),
        ("k8s",             "Kubernetes",          "synonym",  True),
        ("Postgres",        "PostgreSQL",          "synonym",  True),
        ("ML",              "Machine Learning",    "synonym",  True),
        ("Node",            "Node.js",             "synonym",  True),
        ("React",           "ReactJS",             "synonym",  True),
        ("sklearn",         "scikit-learn",        "synonym",  True),
        ("manage staff",    "coordinate duties of staff",  "esco_alt", True),

        # Should be LOW (different skills)
        ("Python",          "Kubernetes",          "different", False),
        ("React",           "Angular",             "similar_domain", False),
        ("SQL",             "project management",  "different", False),
        ("Docker",          "communicate clearly", "different", False),
    ]

    correct = 0
    for s1, s2, case_type, expect_high in test_cases:
        e1 = model.encode([s1])
        e2 = model.encode([s2])
        score = float(cosine_similarity(e1, e2)[0][0])
        threshold = 0.65
        predicted_match = score >= threshold
        correct_prediction = predicted_match == expect_high
        status = "✅" if correct_prediction else "❌"
        print(f"{status} [{case_type:14s}] '{s1}' ↔ '{s2}': {score:.3f}")
        if correct_prediction:
            correct += 1

    print(f"\nAccuracy: {correct}/{len(test_cases)} ({correct/len(test_cases)*100:.0f}%)")
    return correct / len(test_cases)

# ── Compare base vs fine-tuned ─────────────────────────────────────────────────
print("Loading models...")
base_model    = SentenceTransformer("BAAI/bge-small-en-v1.5")
finetuned     = SentenceTransformer("./models/skill_embeddings")

base_acc     = test_model(base_model, "BAAI/bge-small-en-v1.5 (base)")
finetuned_acc = test_model(finetuned,  "Fine-tuned skill_embeddings")

print(f"\n{'='*50}")
print(f"Base model accuracy:       {base_acc*100:.0f}%")
print(f"Fine-tuned model accuracy: {finetuned_acc*100:.0f}%")
print(f"Improvement:               +{(finetuned_acc - base_acc)*100:.0f}%")

if finetuned_acc >= base_acc:
    print("\n✅ Fine-tuned model is better or equal. Safe to deploy.")
    print('\nIn ai_pipeline_service.py update:')
    print('  _bge_model = SentenceTransformer("./models/skill_embeddings")')
    print('  semantic_threshold = 0.65   # was 0.75')
else:
    print("\n⚠️  Fine-tuned model is worse. Try: more epochs or larger MAX_PAIRS in train script.")
