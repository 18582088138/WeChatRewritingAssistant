"""Public facade for extraction, search and saved media; implementations stay modular."""

import re
from pathlib import Path
from urllib.parse import urlparse

from . import store
from .network import fetch
from .research_download import download_assets as download_assets
from .research_html import extract_html
from .research_pdf import extract_pdf
from .research_quality import save_metadata
from .research_search import search as search
from .research_x import post_identity, extract_x


def extract(url, output: Path):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if post_identity(url):
        source = extract_x(url, output)
        source.update(requested_url=url, retrieved_at=store.now())
        (output / "text.txt").write_text(source["text"], encoding="utf8")
        save_metadata(source, output)
        return source
    raw, kind, final = fetch(url)
    requested_url = url
    # An arXiv abstract is not the technical report: follow the full-text representation.
    if (
        urlparse(final).hostname in {"arxiv.org", "www.arxiv.org"}
        and "/abs/" in urlparse(final).path
    ):
        identifier = urlparse(final).path.split("/abs/", 1)[1]
        (output / "landing.html").write_bytes(raw)
        try:
            raw, kind, final = fetch("https://arxiv.org/html/" + identifier)
        except Exception:
            raw, kind, final = fetch("https://arxiv.org/pdf/" + identifier)
    if "pdf" in kind or raw.startswith(b"%PDF"):
        (output / "source.pdf").write_bytes(raw)
        source = extract_pdf(raw, final, output)
    else:
        (output / "source.html").write_bytes(raw)
        source = extract_html(raw, final)
    source["text"] = re.sub(r"\n{3,}", "\n\n", source["text"]).strip()
    if len(source["text"]) < 150:
        raise ValueError("未能获取足够正文，来源可能需要登录或动态渲染。请粘贴原文导入。")
    source.update(
        url=final,
        requested_url=requested_url,
        retrieved_at=store.now(),
    )
    source["quality"]["full_text_chars"] = len(source["text"])
    (output / "text.txt").write_text(source["text"], encoding="utf-8")
    save_metadata(source, output)
    return source
