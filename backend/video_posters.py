"""Generate a local poster frame for a downloaded clip when FFmpeg is available."""

import hashlib
import shutil
import subprocess

from PIL import Image


def ensure_posters(article, root):
    executable = shutil.which("ffmpeg")
    if not executable:
        return False
    changed = False
    for video in list(article["assets"]):
        if video["type"] != "video":
            continue
        path = (root / video["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            continue
        key = hashlib.sha256(path.read_bytes()).hexdigest()[:20]
        asset_id = "poster-" + key
        if video.get("poster_asset_id") == asset_id and any(a["id"] == asset_id for a in article["assets"]):
            continue
        relative = "generated/video-posters/" + key + ".jpg"
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not destination.exists():
                subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file,pipe", "-ss", "0.1", "-i", str(path), "-frames:v", "1", "-vf", "scale=960:-2", "-y", str(destination)], timeout=25, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with Image.open(destination) as image:
                image.verify()
                width, height = image.size
            if not any(a["id"] == asset_id for a in article["assets"]):
                article["assets"].append(dict(id=asset_id, type="image", path=relative, alt="视频封面 · " + video.get("alt", "演示"), approved=video.get("approved", False), width=width, height=height, derived_from=video["id"], role="video-poster", rights=video.get("rights", "参考视频封面"), watermark=video.get("watermark", "unchecked"), attribution=video.get("attribution", ""), sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))
            video["poster_asset_id"] = asset_id
            changed = True
        except (OSError, ValueError, subprocess.SubprocessError):
            article.setdefault("material_warnings", {})[video["path"]] = "视频封面提取失败，保留原视频文件"
    return changed


def attach_posters(content, article):
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup.find_all("video"):
        match = re.fullmatch(r"/api/articles/" + article["id"] + r"/assets/([^/]+)/file", tag.get("src", ""))
        asset = next((a for a in article["assets"] if match and a["id"] == match[1]), None)
        if asset and asset.get("poster_asset_id"):
            tag["poster"] = f"/api/articles/{article['id']}/assets/{asset['poster_asset_id']}/file"
        tag["preload"] = "metadata"
    return str(soup)
