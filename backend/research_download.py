"""Bounded media downloads with per-item diagnostics, format validation and provenance."""

import hashlib
import io
import re
from urllib.parse import urlparse

import pymupdf
from PIL import Image, ImageOps

from . import store
from .network import fetch
from .research_quality import failure_reason, save_metadata
from .configuration import settings


def video_format(raw):
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return ".mov" if raw[8:12] == b"qt  " else ".mp4"
    if raw.startswith(b"\x1aE\xdf\xa3"):
        return ".webm"
    raise ValueError("响应不是可识别的视频文件（可能是错误页或播放列表）")


def raster_image(raw):
    if b"<svg" in raw[:2000].lower():
        # Reject active/external SVG resources; render locally into a raster asset.
        lowered = raw.lower()
        if any(
            mark in lowered
            for mark in [
                b"<script",
                b"<!entity",
                b"<foreignobject",
                b"@import",
                b"url(http",
            ]
        ):
            raise ValueError("SVG 含主动内容或外部资源，未渲染")
        if re.search(rb'(?:href|src)\s*=\s*["\']\s*(?!#|data:)[^"\']+', lowered):
            raise ValueError("SVG 含外部资源，未渲染")
        with pymupdf.open(stream=raw, filetype="svg") as document:
            page = document[0]
            if page.rect.width * page.rect.height > 30_000_000:
                raise ValueError("SVG 尺寸超过上限")
            return page.get_pixmap(alpha=False).tobytes("png")
    Image.open(io.BytesIO(raw)).verify()
    return raw


def download_assets(source, article_id, source_number, article_root=None):
    result, reports, hashes = [], [], set()
    base = article_root or store.folder(article_id)
    root = base / source.get(
        "storage_dir", f"materials/source-{source_number}"
    )
    cfg = settings("research")
    image_limit = cfg["image_limit"]
    video_limit = cfg["video_limit"]
    for index, item in enumerate(source.get("images", [])):
        report = dict(type="image", url=item["url"], status="skipped")
        if sum(a["type"] == "image" for a in result) >= image_limit or index >= 60:
            report["reason"] = f"超过单来源图片上限 {image_limit}"
            reports.append(report)
            continue
        try:
            candidates = item.get("candidates", [item["url"]])
            if item.get("local_file"):
                local = (root / "text" / item["local_file"]).resolve()
                if local.parent != (root / "text").resolve():
                    raise ValueError("无效的 PDF 页面素材路径")
                raw, final = local.read_bytes(), item["url"]
            else:
                last_error = None
                for candidate in candidates[:4]:
                    try:
                        raw, _, final = fetch(
                            candidate,
                            limit=cfg["image_bytes"],
                            referer=source["url"],
                            timeout=15,
                        )
                        raw = raster_image(raw)
                        break
                    except Exception as exc:
                        last_error = exc
                else:
                    raise last_error or ValueError("没有有效图片地址")
            digest = hashlib.sha256(raw).hexdigest()
            if digest in hashes:
                report["reason"] = "重复图片内容"
                reports.append(report)
                continue
            with Image.open(io.BytesIO(raw)) as opened:
                if (
                    opened.width < 300
                    or opened.height < 180
                    or opened.width * opened.height > 30_000_000
                ):
                    raise ValueError("图片尺寸过小或超过 3000 万像素上限")
                image = ImageOps.exif_transpose(opened)
                animated = getattr(opened, "is_animated", False)
                suffix = (
                    ".gif"
                    if animated and opened.format == "GIF"
                    else ".png"
                    if image.mode in {"RGBA", "LA", "P"}
                    else ".jpg"
                )
                path = root / "images" / f"{index}{suffix}"
                path.parent.mkdir(parents=True, exist_ok=True)
                if suffix == ".gif":
                    path.write_bytes(raw)
                elif suffix == ".png":
                    image.save(path, "PNG")
                else:
                    image.convert("RGB").save(path, "JPEG", quality=92)
                width, height = image.size
            hashes.add(digest)
            result.append(
                dict(
                    id=f"s{source_number}-image-{index}",
                    type="image",
                    path=path.relative_to(base).as_posix(),
                    source_url=final,
                    attribution=source["url"],
                    alt=item.get("alt", ""),
                    caption=item.get("caption", ""),
                    width=width,
                    height=height,
                    approved=False,
                    rights="来源图片，需确认授权与水印",
                    watermark="unchecked",
                    sha256=digest,
                    saved_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    bytes=path.stat().st_size,
                    animated=animated,
                )
            )
            report.update(
                status="saved", width=width, height=height, bytes=path.stat().st_size
            )
        except Exception as exc:
            report.update(status="failed", reason=failure_reason(exc))
        reports.append(report)
    for index, url in enumerate(source.get("videos", [])):
        report = dict(type="video", url=url, status="skipped")
        if index >= video_limit:
            report["reason"] = f"超过单来源视频上限 {video_limit}"
            reports.append(report)
            continue
        try:
            if urlparse(url).path.lower().endswith((".m3u8", ".mpd")):
                raise ValueError("流媒体播放列表仅保留来源，当前不下载分段视频")
            raw, mime, final = fetch(url, limit=cfg["video_bytes"], referer=source["url"])
            suffix = video_format(raw)
            path = root / "videos" / f"{index}{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            result.append(
                dict(
                    id=f"s{source_number}-video-{index}",
                    alt=source.get("title", "参考资料") + f" · 视频 {index + 1}",
                    type="video",
                    path=path.relative_to(base).as_posix(),
                    source_url=final,
                    attribution=source["url"],
                    approved=False,
                    rights="来源视频，需确认授权",
                    watermark="unchecked",
                    bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    content_type=mime,
                )
            )
            report.update(status="saved", bytes=len(raw), format=suffix)
        except Exception as exc:
            report.update(status="failed", reason=failure_reason(exc))
            source.setdefault("embedded_media", []).append(dict(url=url, type="download_failed", reason=report["reason"]))
        reports.append(report)
    source["media_downloads"] = reports
    source["quality"]["saved_images"] = sum(a["type"] == "image" for a in result)
    source["quality"]["saved_videos"] = sum(a["type"] == "video" for a in result)
    save_metadata(source, root / "text")
    return result
