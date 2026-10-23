"""Keep every writer response for inspection, including rejected length attempts."""

import json
from . import store


def save_attempt(article_id, result, phase):
    root = store.folder(article_id) / "generated" / "attempts"
    root.mkdir(parents=True, exist_ok=True)
    name = store.now().replace(":", "-") + "-" + phase
    (root / (name + ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    if isinstance(result, dict) and isinstance(result.get("body"), str):
        (root / (name + ".md")).write_text(result["body"], encoding="utf8")
