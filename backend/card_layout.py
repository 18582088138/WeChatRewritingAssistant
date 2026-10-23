"""Short 3:4 editorial pages with contextual images and readable typography."""

import re
from PIL import Image, ImageDraw, ImageOps
from . import store
from .configuration import settings


def editorial_pages(article, eligible, cfg):
    pages = [dict(title=article["title"], text=article["summary"], asset=eligible[0] if eligible else None)]
    heading, buffer = "关键解读", ""

    def flush():
        nonlocal buffer
        if buffer:
            pages.append(dict(title=heading, text=buffer, asset=None))
            buffer = ""

    for block in article["body"].split("\n\n"):
        if block.startswith("##"):
            flush()
            heading = block.lstrip("# ").strip()
            continue
        image_id = re.search(r"/assets/([^/]+)/file", block)
        visual = next((a for a in eligible if image_id and a["id"] == image_id[1]), None)
        text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", block)
        text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1", text)
        text = re.sub(r"[*`#]", "", text).strip()
        if visual:
            flush()
            pages.append(dict(title=heading, text=text[:160], asset=visual))
            text = text[160:]
        while text:
            capacity = cfg["card_chars"] - len(buffer) - (2 if buffer else 0)
            if capacity < 40:
                flush()
                continue
            end = min(len(text), capacity)
            if end < len(text):
                boundaries = [m.end() for m in re.finditer(r"[。！？；\n]", text[:end]) if m.end() > end // 2]
                end = boundaries[-1] if boundaries else end
            buffer += ("\n\n" if buffer else "") + text[:end]
            text = text[end:]
            if text:
                flush()
    flush()
    return pages


def cards(article):
    from .render import font, wrap

    cfg = settings("platforms")
    width, height = cfg["card_width"], cfg["card_height"]
    root = store.folder(article["id"]) / "generated" / f"cards-r{article['revision']}"
    root.mkdir(parents=True, exist_ok=True)
    eligible = [
        a
        for a in article["assets"]
        if a["type"] == "image" and not a["id"].startswith("card-")
    ]
    pages = editorial_pages(article, eligible, cfg)
    assets = []
    for index, page in enumerate(pages):
        image = Image.new("RGB", (width, height), "#f4f0e8")
        draw = ImageDraw.Draw(image)
        draw.text((75, 65), "科技观察 / 有据可查", font=font(26), fill="#3b705e")
        draw.text(
            (width - 215, 65),
            f"{index + 1:02d} / {len(pages):02d}",
            font=font(26),
            fill="#56675c",
        )
        y = 145
        title_size = 50 if not index else 42
        for line in wrap(draw, page["title"], font(title_size), width - 150):
            draw.text((75, y), line, font=font(title_size), fill="#20392f")
            y += title_size + 20
        y += 30
        visual = page["asset"]
        if visual:
            with Image.open(store.folder(article["id"]) / visual["path"]) as original:
                photo = ImageOps.contain(original.convert("RGB"), (width - 150, 400))
                image.paste(photo, ((width - photo.width) // 2, y))
            y += photo.height + 35
        size = 34
        text_lines = wrap(draw, page["text"], font(size), width - 150)
        while (
            y + len(text_lines) * (size + 16) > height - 145
            and size > cfg["minimum_font_size"]
        ):
            size -= 1
            text_lines = wrap(draw, page["text"], font(size), width - 150)
        if y + len(text_lines) * (size + 16) > height - 145:
            raise ValueError("卡片内容超出可读排版容量，请减少 card_chars 或缩短标题")
        for line in text_lines:
            draw.text((75, y), line, font=font(size), fill="#46554f")
            y += size + 16
        draw.text(
            (75, height - 80),
            "SIGNAL STUDIO / 科技内容工作台",
            font=font(22),
            fill="#66796d",
        )
        path = root / f"{index + 1:02d}.png"
        image.save(path)
        approved = not visual or visual.get("approved", False)
        assets.append(
            dict(
                id=f"card-r{article['revision']}-{index}",
                type="image",
                path=path.relative_to(store.folder(article["id"])).as_posix(),
                alt=page["title"],
                approved=approved,
                rights="本地排版；内含来源图待确认" if not approved else "本地排版生成",
                watermark="unchecked" if not approved else "none",
                source_url=visual.get("source_url", "") if visual else "",
                attribution=visual.get("attribution", "") if visual else "",
                derived_from=visual["id"] if visual else None,
                width=width,
                height=height,
            )
        )
    return assets
