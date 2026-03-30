# Stage 3: BGE Fine-tuning for ResumeEZ
## Run these steps on your local machine

---

### Setup (one time)
```bash
pip install sentence-transformers torch scikit-learn
```

---

### Step 1 — Extract synonym pairs from ESCO
```bash
python3 01_extract_pairs.py
```
Output: `data/positive_pairs.jsonl` (126K pairs), `data/negative_pairs.jsonl` (750 pairs)
Time: ~30 seconds

---

### Step 2 — Fine-tune the BGE model
```bash
python3 02_train_embeddings.py
```
Output: `models/skill_embeddings/`
Time: ~5-10 min CPU, ~2 min GPU

---

### Step 3 — Verify the model improved
```bash
python3 03_verify_model.py
```
Compares base vs fine-tuned on synonym test cases. Should show improvement.

---

### Step 4 — Integrate into your pipeline
In `backend/src/services/ai_pipeline_service.py`, find line ~36:

```python
# BEFORE
_bge_model = SentenceTransformer("BAAI/bge-small-en-v1.5")

# AFTER
_bge_model = SentenceTransformer("./models/skill_embeddings")
```

Also find your `semantic_threshold` and lower it:
```python
# BEFORE
semantic_threshold = 0.75

# AFTER
semantic_threshold = 0.65
```

Then copy the `models/` folder into your backend directory:
```
backend/
  models/
    skill_embeddings/   ← paste here
  src/
    services/
      ai_pipeline_service.py
```

---

### Notes
- The ESCO files (skills_en.csv, digitalSkillsCollection_en.csv) need to be in the
  same directory as the scripts, OR update the paths at the top of 01_extract_pairs.py
- MAX_PAIRS in 02_train_embeddings.py is set to 20,000. 
  Raise to 50,000 if you have GPU for better accuracy.
- The manual tech synonym list in 01_extract_pairs.py is editable — 
  add any domain-specific aliases your users commonly submit.
