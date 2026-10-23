import io
import re
import zipfile
from pathlib import Path

import bleach
import markdown
from PIL import Image, ImageDraw, ImageFont

from . import store

TAGS = [
    "p",
    "br",
    "h2",
    "h3",
    "h4",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "img",
    "video",
    "code",
    "pre",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
]
STYLES = {
    "p": "margin:0 0 20px;line-height:1.9;color:#293344;",
    "h2": "font-size:23px;margin:34px 0 18px;color:#172733;",
    "h3": "font-size:19px;margin:26px 0 14px;",
    "blockquote": "border-left:3px solid #138a72;padding:12px 20px;background:#eff8f4;",
    "img": "max-width:100%;height:auto;border-radius:10px;",
    "a": "color:#138a72;",
    "li": "line-height:1.9;margin-bottom:8px;",
    "table": "width:100%;border-collapse:collapse;",
    "th": "border:1px solid #dbe5e0;padding:8px;",
    "td": "border:1px solid #dbe5e0;padding:8px;",
}


def html(body):
    safe = bleach.clean(
        markdown.markdown(body, extensions=["tables", "fenced_code"]),
        tags=TAGS,
        attributes={
            "a": ["href", "title"],
            "img": ["src", "alt"],
            "video": ["src", "controls"],
        },
        protocols=["http", "https"],
        strip=True,
    )
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(safe, "html.parser")
    for link in soup.find_all("a"):
        if link.get_text().startswith("视频：") and re.fullmatch(
            r"/api/articles/[a-f0-9]{32}/assets/[^/]+/file", link.get("href", "")
        ):
            video = soup.new_tag("video", src=link["href"], controls="")
            video["style"] = "max-width:100%;height:auto"
            link.replace_with(video)
    for tag in soup.find_all(True):
        if tag.name in STYLES:
            tag["style"] = STYLES[tag.name]
        if tag.name == "a":
            tag["rel"] = "noopener noreferrer"
            tag["target"] = "_blank"
    return str(soup)


def document(article):
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
        + bleach.clean(article["title"], tags=[], strip=True)
        + '</title><body style="max-width:720px;margin:40px auto;padding:24px;font-family:system-ui,sans-serif;background:#fafcfb"><h1>'
        + bleach.clean(article["title"], tags=[], strip=True)
        + "</h1>"
        + html(article["body"])
        + "</body></html>"
    )


def font(size):
    for file in [
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(file).exists():
            return ImageFont.truetype(file, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, max_width):
    lines, line = [], ""
    for char in text:
        measured = 0 if char == "\n" else draw.textlength(line + char, font=face)
        closing = char in "，。！？；：、,.!?;:）】》”’%"
        if char != "\n" and closing and line and measured <= max_width + face.size:
            line += char
        elif char == "\n" or measured > max_width:
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    return lines


def cards(article):
    from .card_layout import cards as create_cards
    return create_cards(article)


def export_zip(article, platform):
    stream = io.BytesIO()
    body = article["body"]
    if platform in ("xiaohongshu", "weibo", "x"):
        text = article["title"] + "\n\n" + re.sub(r"!\[[^]]*\]\([^)]*\)", "", body)
        text = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
        text = re.sub(r"[*`#]", "", text)
        text += "\n\n" + " ".join("#" + k for k in article["keywords"])
    else:
        text = body
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("draft.md", "# " + article["title"] + "\n\n" + body)
        archive.writestr("caption.txt", text)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(document(article), "html.parser")
        for image in soup.find_all(["img", "video"]):
            match = re.fullmatch(
                r"/api/articles/" + article["id"] + r"/assets/([^/]+)/file",
                image.get("src", ""),
            )
            if match:
                asset = next(
                    (
                        a
                        for a in article["assets"]
                        if a["id"] == match[1] and a["approved"]
                    ),
                    None,
                )
                if asset:
                    image["src"] = "assets/" + asset["id"] + Path(asset["path"]).suffix
                else:
                    image.decompose()
        archive.writestr("preview.html", str(soup))
        archive.writestr(
            "README.txt",
            "这是发布素材包。请在对应平台创建草稿，检查字数、分段、图文、来源与授权后保存。\n组图为 1080×1440 PNG。X 长文需要对应账号权限，普通帖子请按实际限额拆分。\n未调用任何直接发布接口。",
        )
        import json

        archive.writestr(
            "sources.json",
            json.dumps(
                [
                    dict(
                        id=f"S{i + 1}",
                        title=s["title"],
                        url=s["url"],
                        retrieved_at=s["retrieved_at"],
                    )
                    for i, s in enumerate(article["sources"])
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
        for asset in article["assets"]:
            if asset.get("approved"):
                path = store.folder(article["id"]) / asset["path"]
                archive.write(path, "assets/" + asset["id"] + path.suffix)
    return stream.getvalue()
