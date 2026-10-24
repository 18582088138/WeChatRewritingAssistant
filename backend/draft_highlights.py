"""Highlight changed blocks in the reader without altering Markdown content."""

from .render import html


def highlighted(article):
    blocks, offset, result = article["body"].split("\n\n"), 0, []
    for block in blocks:
        end = offset + len(block)
        changed = any((h["start"] < end and h["end"] > offset) or (h["start"] == h["end"] and offset <= h["start"] <= end) for h in article.get("highlights", []))
        changed = changed or any(f"/assets/{key}/file" in block for key in article.get("media_highlights", []))
        content = html(block)
        result.append('<div class="changed-block" title="本版本中有修改">' + content + '</div>' if changed else content)
        offset = end + 2
    return "\n".join(result)
