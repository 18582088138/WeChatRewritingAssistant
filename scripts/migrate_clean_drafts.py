"""Back up legacy human drafts before separating notes and citations from their body."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from backend import store
from backend.draft_presentation import clean_body


def migrate():
    count = 0
    for file in (store.DATA / "articles").glob("*/article.json"):
        raw = json.loads(file.read_text(encoding="utf8"))
        if raw.get("status") == "Process" or clean_body(raw.get("body", "")) == raw.get("body", ""):
            continue
        archive = file.parent / "drafts/internal/legacy-presentations"
        archive.mkdir(parents=True, exist_ok=True)
        backup = archive / ("revision-" + str(raw["revision"]) + ".json")
        if not backup.exists():
            backup.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf8")
        store.save(store.read(raw["id"]))
        count += 1
    return count


if __name__ == "__main__":
    print("Backed up and cleaned drafts:", migrate())
