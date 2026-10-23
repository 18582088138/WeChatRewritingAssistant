"""Place reference visuals in internal drafts; keep pending approval explicit."""

import re
import uuid

from PIL import Image, ImageDraw

from . import store
from .configuration import settings


def eligible(article):
    pending = settings("platforms")["include_pending_media_in_draft"]
    return [
        a
        for a in article["assets"]
        if a["type"] == "image"
        and not a["id"].startswith("card-")
        and (a.get("approved") or pending)
    ]


def fallback(article):
    from .render import font, wrap

    asset_id = "illustration-" + uuid.uuid4().hex[:12]
    image = Image.new("RGB", (1080, 1080), "#f4f0e8")
    draw = ImageDraw.Draw(image)
    draw.text(
        (70, 50),
        "技术要点 / " + str(len(article["sources"])) + " 个参考来源",
        font=font(28),
        fill="#3b705e",
    )
    size = 36
    while size > 26:
        lines = wrap(draw, article["title"], font(size), 940) + wrap(draw, article["summary"], font(size), 940)
        if 150 + len(lines) * (size + 12) <= 1000:
            break
        size -= 1
    y = 130
    for content, color in [(article["title"], "#20392f"), (article["summary"], "#46554f")]:
        for line in wrap(draw, content, font(size), 940):
            draw.text((70, y), line, font=font(size), fill=color)
            y += size + 12
        y += 20
    path = (
        store.folder(article["id"])
        / "generated"
        / "illustrations"
        / (asset_id + ".png")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    asset = dict(
        id=asset_id,
        type="image",
        path=path.relative_to(store.folder(article["id"])).as_posix(),
        alt=article["title"],
        approved=True,
        watermark="none",
        rights="本地原创文字信息图",
        source_url="",
        attribution="",
        width=1080,
        height=1080,
    )
    article["assets"].append(asset)
    return asset


def ensure_media(article):
    cfg = settings("generation")
    if not cfg["require_images"]:
        return
    assets = eligible(article)
    if not assets:
        assets = [fallback(article)]
    # Prefer captioned diagrams and charts over logos or decorative thumbnails.
    assets.sort(
        key=lambda a: (
            bool(a.get("caption") or a.get("alt")),
            a.get("width", 0) * a.get("height", 0),
        ),
        reverse=True,
    )
    body = article["body"]
    existing = set(re.findall(r"/assets/([^/]+)/file", body))
    count = len(re.findall(r"!\[[^]]*\]\(", body))
    required = min(cfg["min_images"], len(assets), cfg["max_images"])
    blocks = body.split("\n\n")
    prose_end = next((i for i, block in enumerate(blocks) if re.match(r"#{1,3}\s*(?:来源|参考|References)", block)), len(blocks))
    picks = [a for a in assets if a["id"] not in existing][: max(0, required - count)]
    for offset, asset in reversed(list(enumerate(picks))):
        caption = re.sub(
            r"[\[\]\n]", "", asset.get("caption") or asset.get("alt") or "参考资料配图"
        )[:180]
        mark = "（来源配图，授权与水印待确认）" if not asset.get("approved") else ""
        image = f"![{caption}](/api/articles/{article['id']}/assets/{asset['id']}/file)\n\n{caption}{mark}"
        index = max(
            1, min(prose_end, round(prose_end * (offset + 1) / (len(picks) + 1)))
        )
        blocks.insert(index, image)
    article["body"] = "\n\n".join(blocks)
