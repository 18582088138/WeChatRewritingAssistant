import io

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import store
from backend.app import app
from backend.research import extract
from backend.research_context import evidence_text
from backend.research_download import download_assets, raster_image, video_format
from backend.research_html import extract_html
from backend.research_search import (
    bing,
    normalize_url,
    rank,
    search_with_report,
    source_identity,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.delenv("APP_TOKEN", raising=False)
    with TestClient(app) as client:
        yield client


def test_article_body_metadata_tables_lazy_images_and_embeds():
    raw = """<html><head><meta property="article:published_time" content="2025-04-29">
    <script type="application/ld+json">{"@type":"VideoObject","contentUrl":"https://cdn.example/demo.mov"}</script>
    </head><body><nav>导航干扰</nav><h1>模型发布</h1><div class="post-content">
    <header><h2>重要技术标题</h2></header><p>模型支持 <strong>工具调用</strong>，需要核对。</p>
    <table><tr><th>模型</th><th>分数</th></tr><tr><td>A</td><td>42</td></tr></table>
    <figure><img src="data:image/png;base64,x" data-src="/lazy.png" srcset="/small.png 300w, /large.png 1200w">
    <figcaption>真实评测图</figcaption></figure><video><source src="/demo.mp4"></video>
    <iframe src="https://www.youtube.com/embed/abc" title="演示"></iframe></div></body></html>"""
    source = extract_html(raw.encode(), "https://example.com/news")
    assert "导航干扰" not in source["text"] and "重要技术标题" in source["text"]
    assert "模型 | 分数" in source["text"] and "A | 42" in source["text"]
    assert source["published_at"] == "2025-04-29"
    assert source["images"][0]["url"] == "https://example.com/large.png"
    assert source["images"][0]["caption"] == "真实评测图"
    assert len(source["videos"]) == 2 and len(source["embedded_media"]) == 1


def test_long_text_saved_without_truncation(tmp_path, monkeypatch):
    body = "完整技术资料与参考证据。" * 8000 + "正文末尾唯一证据"
    monkeypatch.setattr(
        "backend.research.fetch",
        lambda url: (
            ("<article><h1>真实标题</h1><p>" + body + "</p></article>").encode(),
            "text/html",
            url,
        ),
    )
    source = extract("https://example.com/source", tmp_path)
    assert len(source["text"]) > 65000 and source["text"].endswith("正文末尾唯一证据")
    assert (tmp_path / "text.txt").read_text(encoding="utf8") == source["text"]
    context, sampled = evidence_text(source)
    assert sampled and "正文末尾唯一证据" in context and len(context) < 28000


def test_verification_page_rejected():
    with pytest.raises(ValueError, match="验证"):
        extract_html(b"<body>Verify you are human</body>", "https://example.com")


def test_media_download_fallback_dedup_and_video_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    article = store.create("https://example.com", "test")
    buffer = io.BytesIO()
    Image.new("RGBA", (500, 300), "#ff000080").save(buffer, "PNG")
    raw_image = buffer.getvalue()
    raw_video = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 30

    def fetch(url, **kwargs):
        if url.endswith("/bad"):
            raise ValueError("无效候选图片")
        return (
            (raw_video, "video/quicktime", url)
            if "/video" in url
            else (raw_image, "image/png", url)
        )

    monkeypatch.setattr("backend.research_download.fetch", fetch)
    source = dict(
        url=article["url"],
        quality={},
        images=[
            dict(
                url="https://example.com/bad",
                candidates=["https://example.com/bad", "https://example.com/good"],
            ),
            dict(url="https://example.com/duplicate"),
        ],
        videos=["https://example.com/video.mov", "https://example.com/stream.m3u8"],
    )
    assets = download_assets(source, article["id"], 1)
    assert [a["type"] for a in assets] == ["image", "video"]
    assert assets[0]["path"].endswith(".png") and assets[1]["path"].endswith(".mov")
    assert all(not a["approved"] for a in assets)
    assert [r["status"] for r in source["media_downloads"]] == [
        "saved",
        "skipped",
        "saved",
        "failed",
    ]
    assert (store.folder(article["id"]) / "materials/source-1/text/metadata.json").exists()
    with pytest.raises(ValueError):
        video_format(b"<html>forbidden</html>")


def test_search_filters_irrelevant_results_and_reports_fallback(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER", "free")
    monkeypatch.setattr("backend.research_discovery.official", lambda q: [])
    monkeypatch.setattr(
        "backend.research_search.bing",
        lambda q: [
            dict(title="NVIDIA drivers", url="https://nvidia.com/drivers"),
            dict(title="Qwen3 Technical Report", url="https://arxiv.org/abs/2505.09388"),
        ],
    )
    monkeypatch.setattr(
        "backend.research_search.arxiv",
        lambda q: [
            dict(
                title="Qwen3 Technical Report",
                url="https://arxiv.org/abs/2505.09388?utm_source=test",
            )
        ],
    )
    report = search_with_report("Qwen3 technical report")
    assert len(report["results"]) == 1 and len(report["attempts"]) == 3
    assert report["results"][0]["source_type"] == "primary"
    assert not rank([dict(title="NVIDIA drivers", url="https://nvidia.com")], "GR00T N1", 6)
    assert not rank(
        [dict(title="Qwen3 .8 release", url="https://github.com/qwen3.8", snippet="Qwen3")],
        "Qwen3",
        6,
    )
    assert not rank(
        [dict(title="Claude Haiku 4.5", url="https://anthropic.com/haiku")], "Claude Sonnet 4.5", 6
    )
    assert normalize_url("https://Example.com/news/?utm_source=x#top") == "https://example.com/news"


def test_search_gate_is_not_silent_success(monkeypatch):
    monkeypatch.setattr(
        "backend.research_search.fetch",
        lambda *a, **k: (b"<body>enable javascript</body>", "text/html", a[0]),
    )
    with pytest.raises(ValueError, match="自然结果"):
        bing("Qwen3")


def test_svg_charts_are_images_and_active_svg_rejected():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400"><rect width="600" height="400" fill="red"/></svg>'
    raster = raster_image(raw)
    with Image.open(io.BytesIO(raster)) as image:
        assert image.size == (600, 400)
    with pytest.raises(ValueError, match="外部资源"):
        raster_image(b'<svg><image href="https://example.com/tracker.png"/></svg>')
    with pytest.raises(ValueError, match="主动内容"):
        raster_image(b"<svg><script>alert(1)</script></svg>")
    source = extract_html(
        b'<article><object type="image/svg+xml" data="/chart.svg"></object></article>',
        "https://example.com",
    )
    assert len(source["images"]) == 1 and not source["embedded_media"]


def test_arxiv_representations_share_identity():
    assert source_identity("https://arxiv.org/pdf/2505.09388") == source_identity(
        "https://arxiv.org/abs/2505.09388v1"
    )


def test_gif_keeps_animation(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    article = store.create("https://example.com", "GIF source")
    buffer = io.BytesIO()
    frames = [Image.new("RGB", (500, 300), color) for color in ["red", "blue"]]
    frames[0].save(
        buffer, format="GIF", save_all=True, append_images=frames[1:], duration=100, loop=0
    )
    monkeypatch.setattr(
        "backend.research_download.fetch",
        lambda url, **kwargs: (buffer.getvalue(), "image/gif", url),
    )
    source = dict(
        url=article["url"], images=[dict(url="https://example.com/demo.gif")], videos=[], quality={}
    )
    assets = download_assets(source, article["id"], 1)
    assert assets[0]["animated"] and assets[0]["path"].endswith(".gif")
    with Image.open(store.folder(article["id"]) / assets[0]["path"]) as image:
        assert image.n_frames == 2


def test_research_api_auth_and_diagnostics(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.research.search_with_report",
        lambda q: dict(
            query=q,
            results=[],
            attempts=[dict(provider="bing", status="failed", reason="网络超时")],
            status="no_results",
        ),
    )
    assert client.get("/api/research/search?q=x").status_code == 422
    result = client.get("/api/research/search", params={"q": "Qwen3"}).json()
    assert result["status"] == "no_results" and result["attempts"][0]["reason"] == "网络超时"
    monkeypatch.setenv("APP_TOKEN", "test-token")
    assert client.get("/api/research/search?q=Qwen3").status_code == 401


def test_pdf_full_pages_and_vector_figures(tmp_path, monkeypatch):
    with pymupdf.open() as doc:
        doc.set_metadata({"title": "Full paper"})
        page = doc.new_page()
        page.insert_text((50, 50), "Technical evidence and figures. " * 8)
        for index in range(7):
            page.draw_rect(pymupdf.Rect(40 + index * 5, 100, 100 + index * 5, 200))
        last = doc.new_page()
        last.insert_text((50, 50), "Final appendix evidence. " * 10)
        raw = doc.tobytes()
    monkeypatch.setattr("backend.research.fetch", lambda url: (raw, "application/pdf", url))
    source = extract("https://example.com/paper.pdf", tmp_path)
    assert source["quality"]["extracted_pages"] == 2 and "Final appendix evidence" in source["text"]
    assert source["images"] and (tmp_path / source["images"][0]["local_file"]).exists()
