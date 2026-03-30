"""
Step 2: Generate spaCy training config for NER
Run: python3 02_init_config.py

This creates config.cfg which 03_train_ner.py uses.
Downloads en_core_web_md on first run (~45MB — has GloVe word vectors).
en_core_web_md is required; en_core_web_sm has NO static vectors and won't work.
"""

import subprocess
import sys
import re

# ── Step 1: Ensure en_core_web_md is available (has GloVe static vectors) ──────
print("Checking en_core_web_md...")
check = subprocess.run(
    [sys.executable, "-c", "import en_core_web_md"],
    capture_output=True
)
if check.returncode != 0:
    print("Downloading en_core_web_md (~45MB, one-time)...")
    dl = subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_md"])
    if dl.returncode != 0:
        print("ERROR: Failed to download en_core_web_md")
        sys.exit(1)
    print("Downloaded.\n")
else:
    print("Already installed.\n")

# ── Step 2: Generate base config ────────────────────────────────────────────────
cmd = [
    sys.executable, "-m", "spacy", "init", "config",
    "config.cfg",
    "--lang", "en",
    "--pipeline", "ner",
    "--optimize", "efficiency",
    "--force",
]

print("Generating spaCy config...")
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)
    sys.exit(1)

# ── Step 3: Patch config to use en_core_web_md's GloVe vectors ─────────────────
# en_core_web_md has 685K GloVe vectors — critical for the blank model to learn
# skill names without pre-training. en_core_web_sm has NO vectors and will crash.
print("Patching config.cfg to use en_core_web_md static vectors...")
with open("config.cfg", "r") as f:
    cfg = f.read()

cfg = re.sub(r'^vectors\s*=\s*null', 'vectors = "en_core_web_md"', cfg, flags=re.MULTILINE)
cfg = cfg.replace("include_static_vectors = false", "include_static_vectors = true")

with open("config.cfg", "w") as f:
    f.write(cfg)

print("✅ config.cfg created with en_core_web_md vectors")
print("\nNext: python3 03_train_ner.py")
