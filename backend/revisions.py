"""User-visible versions, independent from optimistic concurrency revisions."""

import json
import re
import copy
import hashlib
import shutil
from difflib import SequenceMatcher

from .draft_presentation import clean_body


def prose(body):
    body = clean_body(body)
    return re.sub(r"!\[[^]]*\]\([^)]*\)|\[视频：[^]]*\]\([^)]*\)|<video\b.*?</video>", "", body, flags=re.S).strip()


def changes(before, after):
    return [dict(start=j1, end=j2, removed=i2-i1) for kind, i1, i2, j1, j2 in SequenceMatcher(None, before, after, autojunk=False).get_opcodes() if kind != "equal"]


def change_ratio(before, after):
    a, b = prose(before), prose(after)
    if not a:
        return 1.0 if b else 0.0
    matched = sum(block.size for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    total = max(len(a), len(b), 1)
    return (total - matched) / total


def initialize(article):
    article.setdefault("version_number", 1 if article.get("body") else 0)
    article.setdefault("version_baseline", article.get("body", ""))
    article.setdefault("highlights", [])
    article.setdefault("version_media_baseline", media_signatures(article))
    baseline = article["version_media_baseline"]
    article["media_highlights"] = [key for key, value in media_signatures(article).items() if key in baseline and baseline[key] != value]
    for key, value in media_signatures(article).items():
        baseline.setdefault(key, value)


def media_signatures(article):
    return {a["id"]: a.get("saved_sha256") or a.get("sha256") or a.get("path") for a in article.get("assets", [])}


def snapshot(article, target):
    initialize(article)
    if not article.get("body"):
        return
    force = article.pop("new_version_requested", False)
    ratio = change_ratio(article["version_baseline"], article["body"])
    if not article["version_number"] or force or ratio > 0.30:
        article["version_number"] += 1
        article["version_baseline"] = article["body"]
        article["version_media_baseline"] = media_signatures(article)
        article["media_highlights"] = []
        article["highlights"] = []
    article["change_ratio"] = change_ratio(article["version_baseline"], article["body"])
    article["highlights"] = changes(article["version_baseline"], article["body"])
    directory = target / "branches"
    directory.mkdir(exist_ok=True)
    path = directory / f"v{article['version_number']:04d}.json"
    temporary = path.with_suffix(".tmp")
    saved = copy.deepcopy(article)
    for asset in saved.get("assets", []):
        source = (target / asset["path"]).resolve()
        if source.is_relative_to(target.resolve()) and source.is_file():
            key = hashlib.sha256(source.read_bytes()).hexdigest()
            relative = "branches/media/" + key + source.suffix
            dest = target / relative
            dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                shutil.copy2(source, dest)
            asset["path"] = relative
    temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf8")
    temporary.replace(path)


def history(article, target):
    directory = target / "branches"
    if not directory.exists() and article.get("body"):
        # Existing timestamped snapshots stay intact as an internal audit archive.
        snapshot(article, target)
    return [dict(**json.loads(p.read_text(encoding="utf8")), version_id=p.stem) for p in sorted(directory.glob("*.json"), reverse=True)][:30]
