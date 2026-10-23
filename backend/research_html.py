"""Article-aware HTML extraction; keep tables, captions and publication metadata."""

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .research_media import discover_media
from .research_quality import quality

CONTENT_SELECTORS = [
    "#js_content",
    ".blog-content",
    ".entry-content",
    ".post-content",
    "article.ltx_document",
    "[itemprop=articleBody]",
    "article",
    "main",
    "body",
]
NOISE = "script,style,nav,footer,aside,form,.post-footer,.post-header,.comments,#comments,.social-share,.ltx_role_affiliation,[aria-hidden=true]"


def meta(soup, *names):
    for name in names:
        item = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if item and item.get("content"):
            return item["content"].strip()
    return ""


def article_data(soup):
    def objects(value):
        if isinstance(value, list):
            for item in value:
                yield from objects(item)
        elif isinstance(value, dict):
            if any(t in str(value.get("@type", "")) for t in ["Article", "BlogPosting"]):
                yield value
            yield from objects(value.get("@graph", []))

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from objects(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue


def extract_html(raw, final):
    soup = BeautifulSoup(raw, "html.parser")
    documents = list(article_data(soup))
    data = documents[0] if documents else {}
    h1 = soup.find("h1")
    title = (
        meta(soup, "og:title", "twitter:title")
        or data.get("headline")
        or (h1.get_text(" ", strip=True) if h1 else "")
        or (soup.title.get_text(" ", strip=True) if soup.title else urlparse(final).hostname)
    )
    published = meta(soup, "article:published_time", "date", "pubdate") or data.get(
        "datePublished", ""
    )
    if not published and soup.find("time"):
        published = soup.find("time").get("datetime", "")
    if not published and soup.select_one("#publish_time"):
        published = soup.select_one("#publish_time").get_text(" ", strip=True)
    selected = next((selector for selector in CONTENT_SELECTORS if soup.select_one(selector)), None)
    main = soup.select_one(selected) if selected else soup
    images, videos, embedded = discover_media(main, soup, final)
    for tag in main.select(NOISE):
        tag.decompose()
    if selected == ".blog-content":
        # Hugging Face wraps the author row above the actual article heading.
        first_heading = main.find(["h1", "h2"])
        if first_heading and first_heading.parent == main:
            for sibling in list(first_heading.previous_siblings):
                sibling.extract()
            images, videos, embedded = discover_media(main, soup, final)
    # Publisher link bars are sometimes paragraphs rather than semantic navigation.
    for paragraph in main.find_all("p"):
        links = paragraph.find_all("a")
        if (
            len(links) >= 3
            and sum(len(a.get_text(strip=True)) for a in links)
            >= len(paragraph.get_text(strip=True)) * 0.85
        ):
            paragraph.decompose()
    headings = [
        h.get_text(" ", strip=True) for h in main.select("h1,h2,h3,h4") if h.get_text(strip=True)
    ]
    for table in main.find_all("table"):
        lines = [
            " | ".join(cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"]))
            for row in table.find_all("tr")
        ]
        table.replace_with("\n" + "\n".join(line for line in lines if line) + "\n")
    for tag in main.find_all("br"):
        tag.replace_with("\n")
    for element in main.select("p,h1,h2,h3,h4,h5,h6,li,figcaption,pre,blockquote"):
        if not element.find(["p", "li", "pre"]):
            element.replace_with("\n" + element.get_text(" ", strip=True) + "\n")
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    warnings = []
    if selected in {"main", "body", None}:
        warnings.append("使用通用正文区域，可能残留导航或推荐内容，请核对")
    if data.get("articleBody") and len(data["articleBody"]) > len(text) * 1.2:
        text = data["articleBody"]
        warnings.append("使用页面结构化 articleBody，配图仍取自页面正文")
    if title and not text.startswith(title):
        text = title + "\n\n" + text
    gate_text = soup.get_text(" ", strip=True)[:3000].lower()
    if any(
        mark in gate_text
        for mark in [
            "verify you are human",
            "checking your browser",
            "enable javascript and cookies",
            "百度安全验证",
            "环境异常",
            "访问过于频繁",
        ]
    ):
        raise ValueError("来源返回验证或访问受限页面，未作为文章保存")
    author = meta(soup, "author") or data.get("author", "")
    if isinstance(author, dict):
        author = author.get("name", "")
    canonical = soup.find("link", rel="canonical")
    return dict(
        title=title[:240],
        text=text,
        images=images,
        videos=videos,
        embedded_media=embedded,
        published_at=published,
        author=author,
        headings=headings,
        canonical_url=urljoin(final, canonical["href"])
        if canonical and canonical.get("href")
        else final,
        quality=quality(
            text,
            "html:" + (selected or "document"),
            warnings,
            discovered_images=len(images),
            discovered_videos=len(videos),
            embedded_media=len(embedded),
        ),
    )
