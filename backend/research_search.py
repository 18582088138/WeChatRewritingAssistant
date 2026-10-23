"""Search organic results, rank topical matches and fall back to paper search."""

import base64
import os
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from .network import fetch
from .research_quality import failure_reason

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "introducing",
    "introduction",
    "official",
    "announcement",
    "paper",
    "technical",
    "report",
    "model",
    "models",
    "new",
    "news",
    "think",
    "deeper",
    "act",
    "faster",
}
PRIMARY_HOSTS = {
    "arxiv.org",
    "nvidia.com",
    "nvidia.cn",
    "anthropic.com",
    "openai.com",
    "qwenlm.github.io",
    "huggingface.co",
    "deepseek.com",
    "api-docs.deepseek.com",
    "github.com",
}


def normalize_url(url):
    parsed = urlparse(url)
    query = [
        (k, v)
        for k, values in parse_qs(parsed.query).items()
        for v in values
        if not k.startswith("utm_") and k not in {"fbclid", "gclid"}
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(query),
            "",
        )
    )


def source_identity(url):
    parsed = urlparse(url)
    if parsed.hostname in {"arxiv.org", "www.arxiv.org"}:
        match = re.search(r"/(?:abs|pdf|html)/(\d{4}\.\d+)", parsed.path)
        if match:
            return "arxiv:" + match[1]
    return normalize_url(url)


def decode_bing(url):
    if "/ck/a" in url:
        value = parse_qs(urlparse(url).query).get("u", [""])[0]
        if value.startswith("a1"):
            try:
                return base64.urlsafe_b64decode(value[2:] + "=" * (-len(value[2:]) % 4)).decode()
            except (ValueError, UnicodeError):
                return ""
    return url


def tokens(query):
    return (
        set(
            re.findall(
                r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*|\d+(?:\.\d+)+|[\u4e00-\u9fff]{2,}", query.lower()
            )
        )
        - STOPWORDS
    )


def contains(term, text):
    if re.search("[\u4e00-\u9fff]", term):
        return term in text
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9.]|-[0-9])", text))


def rank(results, query, limit):
    query_tokens = tokens(query)
    # Names containing model versions are stronger signals than generic industry words.
    identifiers = {t for t in query_tokens if any(c.isdigit() for c in t)}
    output, seen = [], set()
    for result in results:
        url = result["url"]
        if urlparse(url).scheme not in {"http", "https"}:
            continue
        key = normalize_url(url)
        if key in seen:
            continue
        seen.add(key)
        haystack = (result["title"] + " " + result.get("snippet", "") + " " + url).lower()
        matched = [t for t in query_tokens if contains(t, haystack)]
        if query_tokens and not matched:
            continue
        title_url = (result["title"] + " " + url).lower()
        if identifiers and not all(contains(t, title_url) for t in identifiers):
            continue
        if identifiers and any(
            t in query_tokens and not contains(t, title_url)
            for t in {"sonnet", "opus", "haiku", "terminus"}
        ):
            continue
        compact_title = re.sub(r"\s+([.-])", r"\1", result["title"].lower())
        if identifiers and any(
            re.search(re.escape(t) + r"\.[0-9]", compact_title) for t in identifiers
        ):
            continue
        if result.get("provider") == "arxiv" and not any(
            contains(t, result["title"].lower()) for t in query_tokens
        ):
            continue
        if len(matched) / max(1, len(query_tokens)) < 0.5:
            continue
        host = urlparse(url).hostname or ""
        primary = any(host == h or host.endswith("." + h) for h in PRIMARY_HOSTS)
        result.update(
            relevance=round(len(matched) / max(1, len(query_tokens)), 3),
            source_type="primary" if primary else "web",
        )
        output.append(result)
    output.sort(
        key=lambda r: (
            r["relevance"]
            + (0.4 if r["source_type"] == "primary" else 0)
            + (0.2 if r["title"].lower().startswith(tuple(query_tokens)) else 0)
        ),
        reverse=True,
    )
    return output[:limit]


def bing(query):
    # Quote the core entity for queries with explicit model versions.
    match = re.search(
        r"(?i)(claude\s+(?:sonnet|opus|haiku)\s+\d+(?:\.\d+)*|deepseek[ -]+v\d+(?:\.\d+)*[ -]+\w+)",
        query,
    )
    if match:
        query = '"' + match[0] + '"'
    raw, _, _ = fetch(
        "https://www.bing.com/search?" + urlencode({"q": query, "setlang": "en-us", "cc": "us"}),
        limit=2_000_000,
        timeout=15,
    )
    soup = BeautifulSoup(raw, "html.parser")
    results = []
    for block in soup.select("li.b_algo"):
        anchor = block.select_one("h2 a[href]")
        if anchor:
            summary = block.select_one(".b_caption p")
            results.append(
                dict(
                    url=decode_bing(anchor["href"]),
                    title=anchor.get_text(" ", strip=True),
                    snippet=summary.get_text(" ", strip=True) if summary else "",
                    provider="bing",
                )
            )
    if not results:
        raise ValueError("搜索页没有可解析的自然结果（可能为验证页或版式变化）")
    return results


def arxiv(query):
    terms = sorted(tokens(query))
    english = [t for t in terms if re.match("[a-z]", t)]
    strong = [t for t in english if any(c.isdigit() for c in t)]
    terms = strong or english[:3]
    if not terms:
        return []
    expression = " AND ".join('ti:"' + term + '"' for term in terms)
    raw, _, _ = fetch(
        "https://export.arxiv.org/api/query?"
        + urlencode({"search_query": expression, "max_results": 6}),
        limit=2_000_000,
        timeout=15,
    )
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    return [
        dict(
            url=e.findtext("a:id", "", ns).replace("http://", "https://"),
            title=" ".join(e.findtext("a:title", "", ns).split()),
            snippet=" ".join(e.findtext("a:summary", "", ns).split())[:600],
            published_at=e.findtext("a:published", "", ns),
            provider="arxiv",
            source_type="primary",
        )
        for e in root.findall("a:entry", ns)
    ]


def search_with_report(query, limit=6):
    query = query.strip()[:240]
    if not query:
        raise ValueError("请输入搜索关键词")
    results, attempts = [], []
    from .research_discovery import official
    from .research_provider import deepseek_search

    providers = [("bing", bing), ("official", official), ("arxiv", arxiv)]
    if os.getenv("DEEPSEEK_API_KEY") and os.getenv("SEARCH_PROVIDER", "free") == "deepseek":
        providers.insert(0, ("deepseek", deepseek_search))
    for index, (name, provider) in enumerate(providers):
        if index and name != "official" and len(rank(results, query, limit)) >= 3:
            break
        try:
            found = provider(query)
            accepted = rank(found, query, limit)
            attempts.append(
                dict(
                    provider=name,
                    status="ok" if accepted else "no_relevant_results",
                    discovered=len(found),
                    accepted=len(accepted),
                )
            )
            results += found
        except Exception as exc:
            attempts.append(dict(provider=name, status="failed", reason=failure_reason(exc)))
    selected = rank(results, query, limit)
    return dict(
        query=query,
        results=selected,
        attempts=attempts,
        status="ok" if selected else "no_results",
        warnings=[] if selected else ["未检索到相关来源；请换用模型名称等关键词或手动补充链接"],
    )


def search(query):
    report = search_with_report(query)
    if not report["results"]:
        raise ValueError(report["warnings"][0])
    return report["results"]
