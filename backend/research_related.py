"""Source-grounded queries and cited links for Chinese industry articles."""

import re
from urllib.parse import urlparse

from .research_search import search_with_report, source_identity


def queries(source):
    text = source["title"] + "\n" + source["text"][:12000]
    names = re.findall(
        r"(?i)\b(?:MiniMax\s+H\d+|Claude\s+(?:Opus|Sonnet|Haiku)\s+\d+(?:\.\d+)?|FLASepformer|JAEC|SmolVLA|DeepSeek[ -]V\d+(?:\.\d+)?|Qwen\d+(?:\.\d+)?(?:-VL)?)\b",
        text,
    )
    names = list(dict.fromkeys(name.strip() for name in names))
    return names[:3] if names else [source["title"][:120]]


def related_report(source):
    reports, candidates = [], []
    for query in queries(source):
        if query.upper() == "JAEC":
            query = "JAEC site:modelscope.cn"
        report = search_with_report(query)
        reports.append(report)
        candidates += report["results"]
    references = list(source.get("links", []))
    references += [
        dict(
            url=url.rstrip(".,，。)）\"'"),
            title="原文引用链接",
            origin="text_reference",
        )
        for url in re.findall(r"https?://[^\s<>\[\]\"']+", source["text"])
    ]
    selected, seen = [], {source_identity(source["url"])}
    for item in references + candidates:
        url = item["url"]
        host = urlparse(url).hostname or ""
        if ".git@" in url or "/api/" in urlparse(url).path and "FilePath=" in url:
            continue
        if (
            not host
            or host.endswith("qpic.cn")
            or host == "mp.weixin.qq.com"
            and "/s/" not in urlparse(url).path
        ):
            continue
        if re.search(r"\.(?:png|jpg|gif|mp4|mov|wav)(?:\?|$)", url):
            continue
        identity = source_identity(url)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(item)
    return dict(
        query=source["title"],
        queries=[r["query"] for r in reports],
        results=selected[:10],
        attempts=[a for r in reports for a in r["attempts"]],
        query_reports=reports,
        reference_links=references,
        status="ok" if selected else "no_results",
        warnings=[] if selected else ["未找到关联来源，保留主文来源并建议人工补充"],
    )
