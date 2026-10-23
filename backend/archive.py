"""Title-based task folders, safe filenames and original source documents."""

import json
import re
import shutil
from pathlib import Path


def safe_name(title, fallback="未命名文章"):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")[:90] or fallback
    if name.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *("COM" + str(n) for n in range(1, 10)),
        *("LPT" + str(n) for n in range(1, 10)),
    }:
        name = "_" + name
    return name


def locate(data, article_id):
    root = data / "articles"
    legacy = root / article_id
    if legacy.exists():
        return legacy
    for file in root.glob("*/article.json"):
        try:
            if json.loads(file.read_text(encoding="utf8")).get("id") == article_id:
                return file.parent
        except (OSError, ValueError):
            continue
    return legacy


def title_folder(data, current, article):
    sources = article.get("sources", [])
    title = article.get("archive_title") or (sources[0]["title"] if sources else "")
    if not title:
        return current
    article["archive_title"] = title
    if current.name != article["id"]:
        return current
    target = data / "articles" / safe_name(title)
    if target.exists() and target != current:
        target = target.with_name(target.name + " · " + article["id"][:8])
    if current.exists():
        if (current / "article.json").exists():
            backup = data / "backups" / "title-migration" / article["id"]
            if not backup.exists():
                shutil.copytree(current, backup)
        current.rename(target)
    else:
        target.mkdir(parents=True, exist_ok=True)
    return target


def source_document(source):
    return (
        f"原文链接：{source['url']}\n\n"
        f"发布日期：{source.get('published_at') or '未知'}　作者：{source.get('author') or '未知'}\n\n"
        f"# {source['title']}\n\n{source['text']}\n"
    )


def material_folder(article_root, source, index):
    if source.get("storage_dir"):
        return article_root / source["storage_dir"]
    parent = article_root / ("source" if index == 1 else "references")
    target = parent / safe_name(source["title"])
    if target.exists() and index > 1:
        original = target / (safe_name(source["title"]) + ".md")
        if not original.exists() or source["url"] not in original.read_text(encoding="utf8")[:500]:
            target = target.with_name(target.name + f" · S{index}")
    return target


def save_source_document(source, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (safe_name(source["title"]) + ".md")).write_text(
        source_document(source), encoding="utf8"
    )


def attach_source(article_id, source, index, temporary):
    from . import store

    root = store.folder(article_id)
    target = material_folder(root, source, index)
    target.mkdir(parents=True, exist_ok=True)
    temporary = root / temporary
    if temporary.exists() and temporary != target / "text":
        shutil.move(str(temporary), str(target / "text"))
    source["storage_dir"] = target.relative_to(root).as_posix()
    save_source_document(source, target)
