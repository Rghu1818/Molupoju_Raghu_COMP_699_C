from typing import List, Dict
import re


def clean_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def to_documents(posts: List[Dict]) -> List[str]:
    return [clean_text(p.get("title", "")) for p in posts]
