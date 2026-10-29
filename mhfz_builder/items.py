"""Portable item metadata from the existing CQ editor, never guessed model IDs."""
import json
import re
from importlib.resources import files

ITEM_DATA = json.loads(files("mhfz_builder").joinpath("data/items.json").read_text(encoding="utf-8"))
ITEMS = ITEM_DATA["items"]


def normalize(text):
    value = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return re.sub(r'\bshl\b', 'shell', value)


def mentioned_items(text, limit=100):
    """Return exact normalized name matches; ambiguity is kept for review."""
    haystack = " " + normalize(text) + " "
    found = []
    for key, name in ITEMS.items():
        normalized = normalize(name)
        if len(normalized) >= 4 and " " + normalized + " " in haystack:
            found.append({"item": int(key), "name": name})
    if len(found) > limit:
        raise ValueError("Too many matching item names; use a more specific reward request")
    return found
