import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_competitor_brands() -> list:
    """Load competitor brand data."""
    path = DATA_DIR / "competitor_brands.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("competitors", [])
    return []


def detect_competitor_mentions(text: str) -> list:
    """Scan text for competitor brand mentions.

    Returns list of dicts: [{"brand": "Tiger Brokers", "matched_alias": "老虎證券"}, ...]
    """
    if not text:
        return []

    brands = load_competitor_brands()
    mentions = []
    text_lower = text.lower()

    for brand in brands:
        all_names = [brand["name"]] + brand.get("aliases", [])
        for name in all_names:
            if name.lower() in text_lower:
                mentions.append({
                    "brand": brand["name"],
                    "matched_alias": name,
                })
                break  # Only count each brand once

    return mentions
