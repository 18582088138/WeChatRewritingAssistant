"""Synchronize files copied or uploaded to a task's manual material folders."""

import hashlib
import re
from pathlib import Path

from PIL import Image

from . import store
from .archive import safe_name
from .research_download import video_format


def sync(article, root=None, persist=True):
    root = root or store.folder(article["id"])
    signatures = article.setdefault("manual_files", {})
    changed = False
    for path in sorted((root / "manual").rglob("*"))[:150]:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 25_000_000:
            continue
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if signatures.get(relative) == digest:
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                with Image.open(path) as image:
                    size, frames = image.size, getattr(image, "n_frames", 1)
                    image.verify()
                asset = dict(
                    type="image", width=size[0], height=size[1], animated=frames > 1
                )
            elif suffix in {".mp4", ".mov", ".webm"}:
                video_format(raw)
                asset = dict(type="video")
            elif suffix in {".md", ".txt", ".pdf", ".html", ".docx"}:
                if suffix == ".docx":
                    from .document_text import docx_text
                    text = docx_text(raw)
                elif suffix == ".pdf":
                    import pymupdf

                    with pymupdf.open(path) as document:
                        text = "\n".join(page.get_text() for page in document)
                elif suffix == ".html":
                    from bs4 import BeautifulSoup

                    text = BeautifulSoup(raw, "html.parser").get_text("\n", strip=True)
                else:
                    text = raw.decode("utf-8-sig")
                if len(text.strip()) < 30:
                    raise ValueError("参考文本至少 30 字符")
                link = re.search(r"原文链接[:：]\s*(https?://\S+)", text)
                source = dict(
                    title=path.stem,
                    text=text,
                    url=link[1] if link else "local://" + path.name,
                    images=[],
                    videos=[],
                    published_at="",
                    retrieved_at=store.now(),
                    manual_path=relative,
                    reference_role=dict(kind="manual", reason="用户补充"),
                    quality=dict(warnings=["用户补充，日期与出处需核对"]),
                )
                previous = next(
                    (s for s in article["sources"] if s.get("manual_path") == relative),
                    None,
                )
                if previous:
                    previous.update(source)
                else:
                    article["sources"].append(source)
                signatures[relative] = digest
                changed = True
                continue
            else:
                continue
            asset.update(
                id="manual-" + hashlib.sha256(relative.encode()).hexdigest()[:16],
                path=relative,
                alt=path.stem,
                sha256=digest,
                saved_sha256=digest,
                bytes=len(raw),
                approved=False,
                source_url="",
                attribution="",
                rights="用户补充素材，需确认授权与水印",
                watermark="unchecked",
            )
            previous = next(
                (a for a in article["assets"] if a["path"] == relative), None
            )
            if previous:
                previous.update(asset)
            else:
                article["assets"].append(asset)
            signatures[relative] = digest
            changed = True
        except Exception as exc:
            article.setdefault("material_warnings", {})[relative] = str(exc)[:180]
    from .video_posters import ensure_posters
    changed = ensure_posters(article, root) or changed
    if changed and persist:
        store.save(article, snapshot=bool(article.get("body")))
    return article


def upload(article_id, filename, raw, root=None, article=None):
    suffix = Path(filename).suffix.lower()
    category = (
        "images"
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        else "videos"
        if suffix in {".mp4", ".mov", ".webm"}
        else "texts"
    )
    if suffix not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".mp4",
        ".mov",
        ".webm",
        ".md",
        ".txt",
        ".html",
        ".pdf",
        ".docx",
    }:
        raise ValueError("不支持的素材格式")
    public = root is not None
    root = root or store.folder(article_id)
    name = safe_name(Path(filename).stem) + suffix
    path = root / "manual" / category / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        path = path.with_name(
            path.stem + "-" + hashlib.sha256(raw).hexdigest()[:8] + suffix
        )
    path.write_bytes(raw)
    return sync(article or store.read(article_id), root, persist=not public)
