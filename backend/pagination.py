"""Paginate rendered blocks without cutting image tags or losing text."""

from bs4 import BeautifulSoup
from .configuration import settings


def paginate(html):
    maximum = settings("platforms")["preview_chars"]
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    for tag in list(soup.contents):
        if not getattr(tag, "name", None):
            continue
        if (
            tag.name == "p"
            and not tag.find(["img", "a", "code", "strong", "em"])
            and len(tag.get_text()) > maximum
        ):
            text = tag.get_text()
            for offset in range(0, len(text), maximum):
                part = soup.new_tag("p")
                part.string = text[offset : offset + maximum]
                blocks.append(part)
        else:
            blocks.append(tag)
    pages, current, count = [], [], 0
    for tag in blocks:
        length = len(tag.get_text()) + (
            240 if tag.find(["img", "video"]) or tag.name in {"img", "video"} else 0
        )
        if current and count + length > maximum:
            heading = current.pop() if current[-1].name in {"h2", "h3", "h4"} else None
            if current:
                pages.append("".join(str(t) for t in current))
            current = [heading] if heading else []
            count = len(heading.get_text()) if heading else 0
        current.append(tag)
        count += length
    if current:
        pages.append("".join(str(t) for t in current))
    return pages or ["<p>暂无正文</p>"]
