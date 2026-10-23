"""Discover actual links from publisher indexes; never invent article URLs."""

import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .network import fetch

INDEXES = [
    (("claude", "anthropic", "sonnet"), "https://www.anthropic.com/sitemap.xml", "sitemap"),
    (("deepseek",), "https://api-docs.deepseek.com/sitemap.xml", "news_sitemap"),
    (("qwen", "通义"), "https://qwenlm.github.io/blog/", "/blog/"),
    (("nvidia", "gr00t", "dgx", "cuda"), "https://developer.nvidia.com/blog/feed/", "feed"),
    (("smolvla", "hugging", "lerobot"), "https://huggingface.co/blog", "/blog/"),
]


def official(query):
    output = []
    for triggers, index_url, path in INDEXES:
        if not any(word in query.lower() for word in triggers):
            continue
        raw, _, final = fetch(index_url, limit=2_000_000, timeout=15)
        if path == "news_sitemap":
            root = ET.fromstring(raw)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [e.text for e in root.findall(".//s:loc", ns) if "/news/" in e.text]

            def heading(url):
                try:
                    page, _, _ = fetch(url, limit=500_000, timeout=12)
                    soup = BeautifulSoup(page, "html.parser")
                    h1 = soup.find("h1")
                    return dict(
                        url=url,
                        title=h1.get_text(" ", strip=True) if h1 else "",
                        snippet="",
                        provider="official",
                    )
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=3) as pool:
                output += [entry for entry in pool.map(heading, urls[-20:]) if entry]
        elif path == "sitemap":
            root = ET.fromstring(raw)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for entry in root.findall("s:url", ns):
                url = entry.findtext("s:loc", "", ns)
                if "/news/" in url:
                    slug = url.rsplit("/", 1)[-1]
                    title = slug.replace("-", " ")
                    title = re.sub(r"(\d) (\d)", r"\1.\2", title)
                    output.append(
                        dict(
                            url=url,
                            title=title,
                            snippet="",
                            provider="official",
                            title_origin="sitemap_slug",
                        )
                    )
        elif path == "feed":
            root = ET.fromstring(raw)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("a:entry", ns):
                link = next(
                    (
                        e.get("href")
                        for e in entry.findall("a:link", ns)
                        if e.get("rel") == "alternate"
                    ),
                    "",
                )
                if link:
                    output.append(
                        dict(
                            url=link,
                            title=entry.findtext("a:title", "", ns),
                            published_at=entry.findtext("a:published", "", ns),
                            provider="official",
                            snippet="",
                        )
                    )
        else:
            soup = BeautifulSoup(raw, "html.parser")
            for anchor in soup.select("a[href]"):
                url = urljoin(final, anchor["href"])
                if (
                    urlparse(url).hostname != urlparse(final).hostname
                    or path not in urlparse(url).path
                ):
                    continue
                title = anchor.get_text(" ", strip=True)
                if len(title) > 10 and url.rstrip("/") != index_url.rstrip("/"):
                    output.append(dict(url=url, title=title[:240], snippet="", provider="official"))
    return output
