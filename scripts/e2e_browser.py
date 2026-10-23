"""Real desktop/mobile editing, paragraph rewrite, image replacement and export checks."""

import io
import zipfile

from PIL import Image
from playwright.sync_api import sync_playwright


def browser_checks(base, token, api, result, output):
    article_id = result["article_id"]
    route = "/api/articles/" + article_id
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True,
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script(
            'sessionStorage.setItem("signal.token", ' + repr(token) + ")"
        )
        page.goto(base + "/#article/" + article_id, wait_until="networkidle")
        page.locator("#draft-body").wait_for()
        page.get_by_role("button", name="来源与素材", exact=True).click()
        page.locator(".source-item").first.wait_for()
        page.get_by_text("查看已保存全文", exact=True).first.click()
        assert (
            result["source_title"]
            in page.locator(".source-full-text").first.inner_text()
        )
        page.screenshot(
            path=str(output / (result["name"] + "-sources.png")), full_page=True
        )
        # Only local test illustrations are approved; original third-party assets remain pending.
        ids = []
        for color in ["#4c7363", "#c2a274"]:
            buffer = io.BytesIO()
            Image.new("RGB", (800, 600), color).save(buffer, "PNG")
            article = api.call(
                "POST",
                route + "/assets",
                files={"file": ("e2e-local.png", buffer.getvalue(), "image/png")},
            )
            asset = article["assets"][-1]
            api.call(
                "PATCH",
                route + "/assets/" + asset["id"],
                json={"approved": True, "alt": "E2E 本地测试配图"},
            )
            ids.append(asset["id"])
        page.reload(wait_until="networkidle")
        page.locator("#draft-body").wait_for()
        title = page.locator("#draft-title").input_value()
        page.locator("#draft-title").fill(title + " · E2E编辑")
        before = api.call("GET", route)["revision"]
        page.get_by_role("button", name="保存修改", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#toast').textContent.includes('修改已保存')"
        )
        current = api.call("GET", route)
        assert current["revision"] > before and current["review"] is None
        # Exercise real model-backed selected-paragraph rewriting through the UI.
        body = page.locator("#draft-body").input_value()
        start = body.find("\n\n") + 2
        end = body.find("\n\n", start)
        assert 0 <= start < end
        page.locator("#draft-body").evaluate(
            '(el, bounds) => { el.focus(); el.setSelectionRange(...bounds); el.dispatchEvent(new Event("select")); }',
            [start, end],
        )
        page.get_by_role("button", name="重写选中段落", exact=False).click()
        page.wait_for_function(
            "document.querySelector('#toast').textContent.includes('段落已重写')",
            timeout=240000,
        )
        rewritten = api.call("GET", route)
        assert rewritten["body"] != body and rewritten["review"] is None
        assert rewritten["body"].startswith(body[:start]) and rewritten[
            "body"
        ].endswith(body[end:])
        # Insert then replace local approved imagery using the actual picker.
        page.locator("#draft-body").evaluate(
            'el => {el.focus();el.setSelectionRange(0,0);el.dispatchEvent(new Event("select"));}'
        )
        page.get_by_role("button", name="插入 / 替换图片", exact=False).click()
        page.locator('[data-pick="' + ids[0] + '"]').click()
        first_image = page.locator("#draft-body").input_value().split(")")[0] + ")"
        page.locator("#draft-body").evaluate(
            '(el, end) => {el.focus();el.setSelectionRange(0,end);el.dispatchEvent(new Event("select"));}',
            len(first_image),
        )
        page.get_by_role("button", name="插入 / 替换图片", exact=False).click()
        page.locator('[data-pick="' + ids[1] + '"]').click()
        page.get_by_role("button", name="保存修改", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#toast').textContent.includes('修改已保存')"
        )
        assert (
            ids[1] in api.call("GET", route)["body"]
            and ids[0] not in api.call("GET", route)["body"]
        )
        page.get_by_role("button", name="图文预览", exact=True).click()
        page.locator(".preview-prose img").wait_for()
        page.wait_for_function(
            "document.querySelector('.preview-prose img').naturalWidth > 0"
        )
        page.get_by_role("button", name="修订记录", exact=True).click()
        page.locator(".version").first.wait_for()
        page.get_by_role("button", name="文案编辑", exact=True).click()
        page.get_by_role("button", name="生成 3:4 组图", exact=False).click()
        page.wait_for_function(
            "document.querySelector('#toast').textContent.includes('组图已生成')",
            timeout=60000,
        )
        page.screenshot(
            path=str(output / (result["name"] + "-cards.png")), full_page=True
        )
        with page.expect_download() as download:
            page.get_by_role("button", name="下载图文包", exact=True).click()
        download.value.save_as(str(output / (result["name"] + "-browser.zip")))
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(
            path=str(output / (result["name"] + "-mobile.png")), full_page=True
        )
        assert not errors, errors
        browser.close()
    options = dict(
        provider="deepseek",
        platform="wechat",
        word_count=result.get("target_word_count", 1200),
        research=False,
    )
    api.call("POST", route + "/review", json=options)
    final = api.idle(article_id)
    assert final["review"]["draft_revision"] == final["revision"]
    for platform in ["wechat", "x", "xiaohongshu", "weibo"]:
        raw = api.call("GET", route + "/export/" + platform)
        (output / (result["name"] + "-" + platform + ".zip")).write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            assert {"draft.md", "preview.html", "caption.txt", "sources.json"}.issubset(
                archive.namelist()
            )
            assert any(path.endswith(".png") for path in archive.namelist())
    deliveries = api.call(
        "POST",
        route + "/deliver",
        json={"platforms": ["wechat", "x", "xiaohongshu", "weibo"]},
    )
    assert deliveries[0]["status"] == "failed" and all(
        item["status"] == "export_ready" for item in deliveries[1:]
    )
    return dict(
        save="passed",
        paragraph_rewrite="passed",
        image_replace="passed",
        preview="passed",
        versions=len(api.call("GET", route + "/versions")),
        cards="passed",
        desktop="passed",
        mobile="passed",
        exports="passed",
        deliveries=deliveries,
        final_review_score=final["review"]["score"],
        final_review_issues=final["review"]["issues"],
        console_errors=errors,
    )


def revised_preview_checks(base, token, result, output):
    """Check final revised content and loaded images at desktop, tablet and phone widths."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True,
        )
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script(
            'sessionStorage.setItem("signal.token", ' + repr(token) + ")"
        )
        page.goto(base + "/#article/" + result["article_id"], wait_until="networkidle")
        page.get_by_role("button", name="图文预览", exact=True).click()
        page.locator(".preview-prose").wait_for()
        page.wait_for_function(
            "Array.from(document.querySelectorAll('.preview-prose img')).every(i => i.complete && i.naturalWidth > 0)"
        )
        for width in [1440, 768, 390]:
            page.set_viewport_size(dict(width=width, height=900))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(
                path=str(output / f"{result['name']}-revised-preview-{width}.png"),
                full_page=True,
            )
        assert not errors, errors
        image_count = page.locator(".preview-prose img").count()
        browser.close()
    return dict(
        widths=[1440, 768, 390],
        loaded_images=image_count,
        console_errors=errors,
        status="passed",
    )
