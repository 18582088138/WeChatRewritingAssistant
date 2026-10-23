"""Preserve legacy material files and versions while adding title-based reference packages."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from backend import store
from backend.archive import material_folder, save_source_document
import shutil


def migrate():
    count = 0
    for article in store.listing():
        store.save(article)
        root = store.folder(article["id"])
        for index, source in enumerate(article["sources"], 1):
            target = material_folder(root, source, index)
            old = root / "materials" / f"source-{index}"
            if old.exists() and not target.exists():
                shutil.copytree(old, target)
            save_source_document(source, target)
            source["storage_dir"] = target.relative_to(root).as_posix()
        store.save(article)
        count += 1
    return count


if __name__ == "__main__":
    print("Migrated tasks:", migrate())
