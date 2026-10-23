"""Bound model context while retaining evidence from the full article, not just its opening."""

CONTEXT_BUDGET = 28_000


def evidence_text(source):
    text = source["text"]
    if len(text) <= CONTEXT_BUDGET:
        return text, False
    # Distribute evidence across the document; section labels make omissions explicit.
    size = 3_300
    offsets = {0, len(text) - size}
    offsets.update(round((len(text) - size) * index / 7) for index in range(1, 7))
    sections = []
    for offset in sorted(offsets):
        start = text.rfind("\n", max(0, offset - 150), offset) if offset else 0
        start = offset if start < 0 or offset == len(text) - size else start
        sections.append(
            f"[原文字符 {start}–{min(len(text), start + size)}]\n{text[start : start + size]}"
        )
    return "\n\n[中间内容省略，未提供部分不得据此推断]\n\n".join(sections), True


def source_context(article):
    result = []
    for index, source in enumerate(article["sources"]):
        text, sampled = evidence_text(source)
        result.append(
            dict(
                id=f"S{index + 1}",
                title=source["title"],
                url=source["url"],
                text=text,
                context_sampled=sampled,
                full_text_chars=len(source["text"]),
                published_at=source.get("published_at", ""),
                headings=source.get("headings", [])[:80],
                extraction_warnings=source.get("quality", {}).get("warnings", []),
            )
        )
    return result
