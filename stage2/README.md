# Stage 2: NER Skill Extraction for ResumeEZ

Replaces 2 Ollama qwen3:8b calls (~6-16 seconds) with a local spaCy NER
model (~100ms total). Same output format, zero changes to calling code.

---

## Setup (one time)

```bash
pip install spacy
python -m spacy download en_core_web_sm
```

---

## Run in order

### Step 1 — Generate training data from ESCO
```bash
# Make sure these two files are in the same folder:
#   digitalSkillsCollection_en.csv
#   transversalSkillsCollection_en.csv
python3 01_generate_ner_data.py
```
Output: `data/train.spacy` (5,100 records), `data/dev.spacy` (900 records)
Time: ~30 seconds

---

### Step 2 — Generate spaCy config
```bash
python3 02_init_config.py
```
Output: `config.cfg`

---

### Step 3 — Train the NER model
```bash
python3 03_train_ner.py
```
Output: `models/skill_ner/model-best/`
Time: ~10-15 min CPU, ~3 min GPU

---

### Step 4 — Verify it works
```bash
python3 04_verify_ner.py
```
Should show ✅ for Python→TECHNICAL, FastAPI→FRAMEWORK, Docker→TOOL, AWS→TOOL

---

### Step 5 — Integrate into pipeline

**Copy the model:**
```bash
cp -r models/skill_ner/ /path/to/your/backend/models/skill_ner/
```

**Update ai_pipeline_service.py:**

1. Add these at the top of the file (after existing imports):
```python
_ner_model = None

def _get_ner_model():
    global _ner_model
    if _ner_model is None:
        import spacy
        _MODEL_PATH = os.path.join(os.path.dirname(__file__), "../../../models/skill_ner/model-best")
        if os.path.isdir(_MODEL_PATH):
            _ner_model = spacy.load(_MODEL_PATH)
        else:
            _ner_model = spacy.blank("en")
    return _ner_model
```

2. Replace the entire `extract_skills_from_text()` function with the
   version from `extract_skills_v2.py`

That's it. No other changes needed.

---

## How it improves over time

When you collect `pipeline_logs.jsonl` (from training_logger.py per the roadmap),
re-run training with real data mixed in:

```python
# In 01_generate_ner_data.py, add at the bottom:
import json
real_records = []
with open("../backend/training_data/pipeline_logs.jsonl") as f:
    for line in f:
        log = json.loads(line)
        # Convert log to NER format using text_to_ner_format() from roadmap
        ...
all_records = all_records + real_records  # real data improves accuracy
```

300 real records → model improves significantly. 1000 real records → production ready.

---

## Model labels

| spaCy Label | Pipeline key  | Examples                        |
|-------------|---------------|---------------------------------|
| TECHNICAL   | technical     | Python, JavaScript, SQL         |
| FRAMEWORK   | frameworks    | React, FastAPI, Django          |
| TOOL        | tools         | Docker, AWS, PostgreSQL         |
| SOFT        | soft          | communication, leadership       |
