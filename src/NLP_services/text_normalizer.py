import re


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    # 1. Lowercase
    text = text.lower()

    # 2. Remove extra white space
    re.sub(r"\s+", " ", text)

    # 3. Remove special characters
    text = re.sub(r"[^a-z0-9+.\s]", " ", text)

    # 4. Trim
    return  text.strip()

