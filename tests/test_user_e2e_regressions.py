import json
import io
import zipfile

from fastapi.testclient import TestClient

from backend import agents
from backend import store
from backend.app import app
from backend.network import source_headers
from backend.research_html import extract_html
from backend.research_related import queries, related_report
from backend.research_search import rank


def test_wechat_request_headers_and_metadata():
    assert source_headers("https://mp.weixin.qq.com/s/abc")["User-Agent"].startswith(
        "Mozilla/"
    )
    assert "User-Agent" not in source_headers("https://example.com")
    html = """<meta property="og:title" content="中文语音模型发布"><h1 id="activity-name">中文语音模型发布</h1>
    <a id="js_name">魔搭社区</a><em id="publish_time"></em>
    <script>var info = {create_time: '2026-09-10 15:28'};</script>
    <div id="js_content"><p>JAEC 每帧 10 ms，算法延迟 22 ms。</p><img data-src="https://mmbiz.qpic.cn/image.png"></div>"""
    source = extract_html(html.encode(), "https://mp.weixin.qq.com/s/abc")
    assert source["published_at"] == "2026-09-10T15:28:00+08:00"
    assert source["author"] == "魔搭社区" and source["images"][0]["url"].endswith(
        "image.png"
    )


def test_related_queries_separate_entities_and_filter_code_urls(monkeypatch):
    source = dict(
        title="Qwen Audio 开源两款模型",
        url="https://example.com/news",
        text="FLASepformer 与 JAEC。 https://arxiv.org/abs/2508.19528 "
        'https://github.com/modelscope/modelscope.git@master" '
        "https://modelscope.cn/api/v1/model?FilePath=example.wav'",
        links=[],
    )
    assert queries(source) == ["FLASepformer", "JAEC"]
    monkeypatch.setattr(
        "backend.research_related.search_with_report",
        lambda q: dict(query=q, results=[], attempts=[]),
    )
    report = related_report(source)
    assert [r["url"] for r in report["results"]] == ["https://arxiv.org/abs/2508.19528"]


def test_length_retries_include_measured_budget(monkeypatch):
    long = dict(title="测试", summary="摘要", keywords=["AI"], body="正文。" * 1000)
    short = dict(title="测试", summary="摘要", keywords=["AI"], body="简洁。" * 150)
    calls = []
    responses = iter([long, long, short])

    def complete(system, payload, provider):
        calls.append(payload)
        return next(responses)

    monkeypatch.setattr(agents, "complete", complete)
    article = dict(id="a" * 32, sources=[], assets=[], body="")
    result = agents.RewritingAgent().run(
        article, dict(provider="deepseek", word_count=600)
    )
    assert result["body"] == short["body"] and len(calls) == 3
    assert (
        calls[-1]["measured_prose_chars"] == 3000
        and calls[-1]["maximum_prose_chars"] == 720
    )


def test_article_links_remain_serializable_after_paragraph_cleanup():
    html = b'<article><p>Article body.</p><p><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a></p></article>'
    source = extract_html(html, "https://example.com/news")
    restored = json.loads(json.dumps(source))
    assert [link["url"] for link in restored["links"]] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_search_site_constraint_rejects_same_acronym_other_domain():
    candidates = [
        dict(
            url="https://www.aec.go.jp/en/", title="JAEC Japan Atomic Energy Commission"
        ),
        dict(
            url="https://www.modelscope.cn/models/iic/speech_jaec_aec_16k",
            title="JAEC speech model",
        ),
    ]
    results = rank(candidates, "JAEC site:modelscope.cn", 10)
    assert [r["url"] for r in results] == [candidates[1]["url"]]


def test_regenerating_cards_keeps_images_already_embedded_in_draft(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.delenv("APP_TOKEN", raising=False)
    article = store.create("https://example.com/news", "科技简报")
    article.update(
        body="## 观察\n\n有来源的行业分析。[S1]", summary="模型发布", keywords=["AI"]
    )
    article["sources"] = [
        dict(title="发布说明", url=article["url"], retrieved_at=store.now())
    ]
    store.save(article)
    route = "/api/articles/" + article["id"]
    with TestClient(app) as client:
        first = client.post(route + "/cards").json()
        embedded = first["assets"][0]
        first["body"] = (
            f"![图文]({route}/assets/{embedded['id']}/file)\n\n" + first["body"]
        )
        first["revision"] += 1
        store.save(first)
        regenerated = client.post(route + "/cards").json()
        assert embedded["id"] in [a["id"] for a in regenerated["assets"]]
        repeated = client.post(route + "/cards").json()
        ids = [a["id"] for a in repeated["assets"]]
        assert len(ids) == len(set(ids))
        raw = client.get(route + "/export/wechat").content
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            image = "assets/" + embedded["id"] + ".png"
            assert image in archive.namelist()
            assert image in archive.read("preview.html").decode("utf8")
