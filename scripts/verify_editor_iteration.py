"""Real local GUI acceptance in an isolated data directory (server on port 8001)."""

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
OUT = ROOT / "test-results/editor-iteration"
OUT.mkdir(parents=True, exist_ok=True)
TOKEN = os.getenv("APP_TOKEN", "")
HEADERS = {"Authorization": "Bearer " + TOKEN} if TOKEN else {}
client = httpx.Client(base_url="http://127.0.0.1:8001", trust_env=False, timeout=240, headers=HEADERS)
production = httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, headers=HEADERS)


def call(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main():
    for service in (production, client):
        for attempt in range(30):
            try:
                if service.get('/api/health', timeout=1).is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError('本地验收服务未启动，请先启动 8000 与隔离的 8001 服务')
    source = production.get("/api/articles/6de439746fc54eeb9a9e4aa2c45c745c").json()
    title = "交互实测·MiniMax 技术解读"
    a = call("POST", "/api/articles", json=dict(url=source["url"], title=title, text=source["sources"][0]["text"]))
    route = "/api/articles/" + a["id"]
    root = Path(call("GET", route)["storage_path"])
    original_root = Path(source["storage_path"])
    image = next(x for x in source["assets"] if x["type"] == "image" and not x["id"].startswith("card-"))
    video = [x for x in source["assets"] if x["type"] == "video"][-1]
    for item, name in [(image, "本篇配图.jpg"), (video, "本篇演示.mp4")]:
        call("POST", route + "/materials", files={"file": (name, (original_root / item["path"]).read_bytes())})
    call("POST", "/api/materials/public", files={"file": ("公共配图.jpg", (original_root / image["path"]).read_bytes())})
    call("POST", "/api/materials/public", files={"file": ("公共技术说明.md", ("参考资料应区分厂商主张、评测结果与实际使用条件。" * 30).encode())})
    call("POST", route + "/materials", files={"file": ("另一份参考说明.md", source["sources"][1]["text"].encode())})
    a = call("GET", route)
    own_image = next(x for x in a["assets"] if x["type"] == "image" and x.get("role") != "video-poster")
    own_video = next(x for x in a["assets"] if x["type"] == "video")
    body = "## 从流程变化理解新模型\n\n" + "模型发布带来的变化需要结合输入条件、处理链路和公开测试理解，不能直接把单项评测推广到所有任务。" * 12
    body += f"\n\n![参考配图]({route}/assets/{own_image['id']}/file)\n\n## 实际使用仍需验证\n\n" + "工具调用的稳定性还取决于工具定义、上下文质量与任务复杂度。" * 10
    body += f"\n\n[视频：官方演示]({route}/assets/{own_video['id']}/file)"
    a = call("PATCH", route, json=dict(title=title, body=body, summary="将公开技术细节放回实际使用条件中理解。", keywords=["AI", "大模型"], revision=a["revision"]))
    errors, review_requests = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: review_requests.append(r.url) if r.url.endswith("/review") else None)
        page.add_init_script('sessionStorage.setItem("signal.token", ' + json.dumps(TOKEN) + ')')
        page.goto("http://127.0.0.1:8001/#article/" + a["id"], wait_until="networkidle")
        page.locator("#draft-reading img").wait_for()
        assert page.locator("#draft-body").count() == 0
        page.wait_for_function("document.querySelector('#draft-reading img').naturalWidth>0")
        page.wait_for_function("document.querySelector('#draft-reading video').readyState>=1")
        page.locator('#draft-reading video').evaluate("el=>{el.muted=true;el.play()}")
        page.wait_for_function("document.querySelector('#draft-reading video').currentTime>0.1 && !document.querySelector('#draft-reading video').error")
        page.locator('#draft-reading video').evaluate("el=>el.pause()")
        assert page.locator(".source-textbox textarea").input_value().count("https://") >= 1
        settings_y = page.locator("#word-count").bounding_box()["y"]
        review_y = page.locator(".review-scroll").bounding_box()["y"]
        assert settings_y < review_y
        page.screenshot(path=str(OUT / "reader-desktop.png"), full_page=True)
        page.locator('#open-references').click()
        page.locator('#reference-source').select_option(label='公共 · 公共技术说明')
        page.locator('#reference-text').evaluate("el=>{el.focus();el.setSelectionRange(0,160)}")
        page.locator('#add-selection').click()
        page.wait_for_function("document.querySelector('.reference-basket').textContent.includes('[S3]')")
        with page.expect_response(lambda r: r.url.endswith('/fuse'), timeout=240000) as fused:
            page.locator('#fuse-selections').click()
        assert fused.value.ok, fused.value.text()
        page.locator('#references-dialog').wait_for(state='hidden')
        assert len(call('GET',route)['sources']) == 3
        page.locator("#draft-reading").dblclick(position=dict(x=50, y=30))
        page.locator("#draft-body").wait_for()
        page.locator("#draft-body").evaluate("el=>{const start=el.value.indexOf('模型发布');el.focus();el.setSelectionRange(start,start+115);el.dispatchEvent(new Event('select'))}")
        before = call("GET", route)
        with page.expect_response(lambda r: r.url.endswith("/paragraph"), timeout=240000) as generated:
            page.locator("#rewrite-selection").click()
        assert generated.value.ok, generated.value.text()
        page.locator("#rewrite-dialog[open]").wait_for()
        proposal = generated.value.json()
        assert call("GET", route)["body"] == before["body"]
        page.locator("#proposal-text").fill(proposal["text"] + " 使用时仍应核对具体条件。")
        page.screenshot(path=str(OUT / "rewrite-comparison.png"), full_page=True)
        with page.expect_response(lambda r: r.url.endswith("/paragraph/apply")) as applied:
            page.mouse.click(5, 5)
        assert applied.value.ok, applied.value.text()
        page.locator("#draft-reading").wait_for()
        page.locator(".changed-block").first.wait_for()
        assert call("GET", route)["version_number"] == before["version_number"]
        page.locator("#open-references").click()
        page.locator("#reference-scope").select_option("all")
        labels = page.locator("#reference-source").inner_text()
        assert "公共技术说明" in labels and "另一份参考说明" in labels
        page.locator("[data-reference-kind=image]").click()
        shared_picture = page.locator('.reference-media-grid article').filter(has=page.locator('img[alt="公共配图"]'))
        assert shared_picture.count() == 1
        shared_picture.locator('[data-reference-media]').click()
        with page.expect_response(lambda r: r.url.endswith(route) and r.request.method=='PATCH') as saved_image:
            page.locator("#save-draft").click()
        assert saved_image.value.ok, saved_image.value.text()
        page.locator("#draft-reading").wait_for()
        page.locator("#keyword-platform").select_option("weibo")
        assert page.locator("#formatted-keywords").input_value() == "#AI# #大模型#"
        page.locator("#keyword-platform").select_option("x")
        assert page.locator("#formatted-keywords").input_value() == "#AI #大模型"
        page.locator('[data-editor-tab="versions"]').click()
        with page.expect_popup() as opened:
            page.locator("[data-version]").first.click()
        historical = opened.value
        historical.locator("img").first.wait_for()
        historical.wait_for_function("document.querySelector('img').naturalWidth>0 && document.querySelector('video').readyState>=1")
        historical.close()
        page.locator('[data-editor-tab="edit"]').click()
        for width in [768, 390]:
            page.set_viewport_size(dict(width=width, height=1000 if width == 768 else 844))
            page.wait_for_timeout(300)
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
            page.screenshot(path=str(OUT / f"reader-{width}.png"), full_page=True)
        page.locator("#open-references").click()
        assert not page.locator(".desktop-fusion").is_visible()
        page.locator("#close-references").click()
        assert not errors, errors
        browser.close()
    saved = call("GET", route)
    report = dict(status="passed", article_id=a["id"], real_llm_paragraph=True, reading_default=True, media_loaded=True, shared_library=True, history_media_loaded=True, outside_click_saves=True, local_change_same_version=True, platform_keywords=True, viewport_widths=[1440, 768, 390], review_requests_on_open=len(review_requests), console_errors=errors, source_count=len(saved["sources"]))
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
