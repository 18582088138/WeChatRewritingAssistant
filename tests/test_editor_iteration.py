"""Acceptance contracts for shared references, review caching and substantial revisions."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import agents, store, research_x
from backend.app import app
from backend.draft_presentation import clean_body, prose_length
from backend.platform_keywords import format_keywords
from backend.review_state import fingerprint
from backend.revisions import change_ratio


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.delenv("APP_TOKEN", raising=False)
    with TestClient(app) as client:
        yield client


def article():
    a = store.create("https://example.com/source", "独立素材测试")
    a.update(body="甲乙丙丁戊己庚辛壬癸" * 40, sources=[dict(title="原始报道", url=a["url"], text="有来源的技术说明。" * 100, images=[], videos=[], retrieved_at=store.now())])
    return store.save(a, snapshot=True)


def edit(client, a, body, **extra):
    response = client.patch(f"/api/articles/{a['id']}", json=dict(title=a["title"], body=body, summary="", keywords=["AI"], revision=a["revision"], **extra))
    assert response.status_code == 200, response.text
    return response.json()


def test_cumulative_versions_and_explicit_branch(client):
    a = article()
    original = a["body"]
    a = edit(client, a, "新" * 80 + original[80:])
    assert a["version_number"] == 1 and a["highlights"]
    a = edit(client, a, "新" * 120 + original[120:])
    assert a["version_number"] == 1  # exactly 30% remains in the current version
    a = edit(client, a, "新" * 124 + original[124:])
    assert a["version_number"] == 2
    a = edit(client, a, a["body"], new_version=True)
    assert a["version_number"] == 3
    versions = client.get(f"/api/articles/{a['id']}/versions").json()
    assert [v["version_number"] for v in versions] == [3, 2, 1]


def test_clean_reader_and_internal_evidence(client):
    a = article()
    raw = "技术事实。[S1]\n\n<!-- Agent 工作信息 -->\n\n说明。[^1]\n\n[^1]: 注释\n\n## 参考来源\n\n[原文](https://example.com/source)"
    a = edit(client, a, raw)
    assert a["body"] == "技术事实。\n\n说明。"
    assert "[S1]" in a["agent_evidence"]["body"]
    assert prose_length(raw) == prose_length(a["body"])
    rendered = client.get(f"/api/articles/{a['id']}/render").json()["html"]
    assert "Agent 工作信息" not in rendered and "参考来源" not in rendered


def test_review_cache_and_stale_record(client, monkeypatch):
    a = article()
    a["review"] = dict(score=90, verdict="已核对", issues=[], strengths=[], fact_checks=[], draft_revision=a["revision"], fingerprint=fingerprint(a))
    store.save(a, snapshot=True)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cached = client.post(f"/api/articles/{a['id']}/review", json={})
    assert cached.status_code == 202 and cached.json()["review"]["score"] == 90
    a = edit(client, a, "小改。" + a["body"])
    assert a["review"]["score"] == 90 and not a["review_current"]
    assert client.post(f"/api/articles/{a['id']}/review", json={}).status_code == 422


def image_bytes(color):
    stream = io.BytesIO()
    Image.new("RGB", (420, 320), color).save(stream, "PNG")
    return stream.getvalue()


def test_public_library_attach_and_immutable_historical_media(client):
    a, other = article(), article()
    public = client.post("/api/materials/public", files={"file": ("公共配图.png", image_bytes("red"), "image/png")}).json()
    assert len(public["assets"]) == 1
    shared = public["assets"][0]
    assert client.get(f"/api/articles/{other['id']}").json()["assets"] == []
    result = client.post(f"/api/articles/{a['id']}/materials/public", json=dict(asset_id=shared["id"])).json()
    a, asset = result["article"], result["asset"]
    video = store.folder(a["id"]) / "manual/videos/demo.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"0" * 100)
    a = client.get(f"/api/articles/{a['id']}").json()
    clip = next(x for x in a["assets"] if x["type"] == "video")
    body = a["body"] + f"\n\n![图](/api/articles/{a['id']}/assets/{asset['id']}/file)\n\n[视频：演示](/api/articles/{a['id']}/assets/{clip['id']}/file)"
    a = edit(client, a, body)
    assert a["version_number"] == 1
    a = edit(client, a, body, new_version=True)
    versions = client.get(f"/api/articles/{a['id']}/versions").json()
    old = versions[-1]
    old_asset = next(x for x in old["assets"] if x["id"] == asset["id"])
    archived = (store.folder(a["id"]) / old_asset["path"]).read_bytes()
    (store.folder(a["id"]) / asset["path"]).write_bytes(image_bytes("blue"))
    prefix = f"/api/articles/{a['id']}/versions/{old['version_id']}"
    assert client.get(prefix + f"/assets/{asset['id']}/file").content == archived
    rendered = client.get(prefix + "/preview").text
    assert "<img" in rendered and "<video" in rendered and "/versions/v0001/assets/" in rendered


def test_public_document_selection_deduplicates(client):
    a = article()
    public = client.post("/api/materials/public", files={"file": ("基础说明.md", ("基础知识与原始报道的边界。" * 10).encode(), "text/markdown")}).json()
    assert len(public["sources"]) == 1
    path = f"/api/articles/{a['id']}/materials/public"
    for _ in range(2):
        result = client.post(path, json=dict(source_index=0)).json()
        assert result["source_id"] == 2 and len(result["article"]["sources"]) == 2


def test_x_public_fallback_validates_identity_and_preserves_video(tmp_path, monkeypatch):
    tweet = dict(id="2113589307789512863", text="包含详细技术信息的中文长帖。" * 40, author=dict(screen_name="laobaishare", name="老白"), created_timestamp=1792753934, media=dict(all=[dict(type="video", thumbnail_url="https://pbs.twimg.com/thumb.jpg", variants=[dict(url="https://video.twimg.com/low.mp4", content_type="video/mp4", bitrate=1), dict(url="https://video.twimg.com/high.mp4", content_type="video/mp4", bitrate=2)])]))

    def fetch(url, **kwargs):
        if "syndication" in url:
            return b"{}", "application/json", url
        return json.dumps(dict(tweet=tweet)).encode(), "application/json", url

    monkeypatch.setattr(research_x, "fetch", fetch)
    source = research_x.extract_x("https://x.com/laobaishare/status/2113589307789512863?s=20", tmp_path)
    assert source["text"] == tweet["text"]
    assert source["videos"] == ["https://video.twimg.com/high.mp4"]
    assert source["published_at"].startswith("2026-10-23")
    assert source["quality"]["method"] == "x:fxtwitter"
    tweet["id"] = "123"
    with pytest.raises(ValueError, match="帖子 ID"):
        research_x.extract_x(source["url"], tmp_path)


def test_platform_tags():
    assert format_keywords(["AI", "大 模型"], "weibo") == "#AI# #大模型#"
    assert format_keywords(["AI", "大 模型"], "x") == "#AI #大模型"
    assert format_keywords(["AI", "大模型"], "wechat") == "AI，大模型"
    assert change_ratio("正文", "正文\n\n![图](https://example.com/1.jpg)") == 0


def test_word_document_import(client):
    a = article()
    stream = io.BytesIO()
    content = '公开基础资料需要保留技术条件和出处。' * 10
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + content + '</w:t></w:r></w:p></w:body></w:document>')
    response = client.post(f"/api/articles/{a['id']}/materials", files={'file': ('参考说明.docx', stream.getvalue())})
    assert response.status_code == 200
    assert response.json()['sources'][-1]['text'] == content


def test_manual_image_replacement_highlights_current_version(client):
    a = article()
    response = client.post(f"/api/articles/{a['id']}/materials", files={'file': ('配图.png', image_bytes('red'))})
    a = response.json()
    image = next(x for x in a['assets'] if x['type'] == 'image')
    body = a['body'] + f"\n\n![图](/api/articles/{a['id']}/assets/{image['id']}/file)"
    a = edit(client, a, body)
    (store.folder(a['id']) / image['path']).write_bytes(image_bytes('blue'))
    updated = client.get(f"/api/articles/{a['id']}").json()
    assert updated['version_number'] == a['version_number']
    assert image['id'] in updated['media_highlights']
    rendered = client.get(f"/api/articles/{a['id']}/render").json()['html']
    assert 'changed-block' in rendered
