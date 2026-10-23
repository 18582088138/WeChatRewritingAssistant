"""DeepSeek's documented Search/Fetch tools; credentials stay server-side."""

import os

import httpx

from .network import validate_url


def tool_request(name, payload):
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise ValueError("DeepSeek Search/Fetch 未配置密钥")
    base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    with httpx.Client(timeout=40) as client:
        response = client.post(
            base + "/v1/tools/" + name, headers={"Authorization": "Bearer " + key}, json=payload
        )
    if response.status_code >= 400:
        raise ValueError(f"DeepSeek {name} HTTP {response.status_code}：接口不可用或账号受限")
    return response.json()


def deepseek_search(query):
    response = tool_request("search", {"query": query[:128], "count": 10, "need_content": False})
    return [
        dict(
            url=item["url"],
            title=item.get("title", ""),
            snippet=item.get("snippet") or item.get("summary", ""),
            published_at=item.get("date") or "",
            provider="deepseek",
            provider_score=item.get("rerank_score"),
            authority=item.get("authority"),
        )
        for item in response.get("results", [])
        if item.get("url")
    ]


def deepseek_fetch(url):
    validate_url(url)
    page = tool_request("fetch", {"url": url})
    if len(page.get("content", "").strip()) < 150:
        raise ValueError("DeepSeek Fetch 没有返回足够正文")
    return page
