"""Admission of fetched references by event relevance and publication window."""

from datetime import datetime
import re
from urllib.parse import urlparse

from .configuration import settings


def published(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def classify(primary, candidate, entities):
    cfg = settings("research")
    original_date, date = (
        published(primary.get("published_at")),
        published(candidate.get("published_at")),
    )
    normalize = lambda text: re.sub(r"[\s_-]+", "", text.lower())
    haystack = normalize(candidate["title"] + "\n" + candidate["text"][:28000])
    matched = [e for e in entities if normalize(e) in haystack]
    if not matched:
        return dict(accepted=False, reason="正文没有匹配核心事件实体")
    host = urlparse(candidate["url"]).hostname or ""
    background = host in {"arxiv.org", "www.arxiv.org"} or any(
        term in candidate["title"].lower()
        for term in ["technical report", "科普", "原理", "tutorial"]
    )
    difference = (date - original_date).days if original_date and date else None
    if difference is not None and abs(difference) <= cfg["window_days"]:
        return dict(
            accepted=True,
            kind="event_reference",
            days_from_news=difference,
            entities=matched,
        )
    if background and cfg["allow_background"]:
        return dict(
            accepted=True,
            kind="background",
            days_from_news=difference,
            entities=matched,
            reason="直接相关的论文或基础资料，日期未知或时间窗口外补充",
        )
    return dict(
        accepted=False,
        days_from_news=difference,
        reason="发布日期未知" if difference is None else "超过新闻前后时间窗口",
    )
