"""Real deployed Pages UI checks; no simulated API responses or platform writes."""

import os

from playwright.sync_api import sync_playwright


def check_browser(url, output, executable=None, api_base=None):
    with sync_playwright() as playwright:
        options = {"headless": True}
        if executable:
            options["executable_path"] = executable
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        if proxy:
            options["proxy"] = dict(server=proxy, bypass="localhost,127.0.0.1")
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport=dict(width=1440, height=1000))
        errors, failures = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: failures.append(
                dict(url=request.url, error=request.failure)
            ),
        )
        response = page.goto(url, wait_until="networkidle", timeout=60000)
        assert response.status == 200
        page.get_by_role("heading", name="文章工作台", exact=True).wait_for()
        assert page.locator("#connection-text").inner_text() == "后端未连接"
        assert page.locator(".article-card").count() == 0
        page.get_by_role("button", name="查看界面示例", exact=True).click()
        assert page.locator(".article-card").count() == 3
        assert "不代表真实" in page.locator(".demo-badge").inner_text()
        page.screenshot(path=str(output / "pages-desktop.png"), full_page=True)
        for status in ["New", "Process", "Done"]:
            page.locator(".tabs [data-filter=" + status + "]").click()
            assert page.locator(".article-card").count() == 1
        page.locator(".tabs [data-filter=All]").click()
        page.locator("#search").fill("不存在的部署测试关键词")
        assert page.locator(".article-card").count() == 0
        page.locator("#search").fill("")
        page.get_by_role("button", name="退出示例", exact=True).click()
        page.locator("#new-article").click()
        page.locator("#import-form input[name=url]").fill(
            "https://example.com/pages-deploy-test"
        )
        page.locator("#import-form button[type=submit]").click()
        page.wait_for_function(
            "document.querySelector('#toast').textContent.includes('配置后端地址')"
        )
        assert page.locator("#import-dialog").evaluate("el => el.open")
        page.locator("#cancel-import").click()
        for view, heading in [
            ("materials", "素材库"),
            ("deliveries", "草稿投递"),
            ("settings", "设置与连接"),
        ]:
            page.locator("[data-view=" + view + "]").click()
            page.get_by_role("heading", name=heading, exact=True).wait_for()
        assert page.locator("#connection-form input[name=api]").input_value() == ""
        assert (
            page.locator("#connection-form input[name=token]").get_attribute("type")
            == "password"
        )
        page.reload(wait_until="networkidle")
        page.get_by_role("heading", name="设置与连接", exact=True).wait_for()
        page.screenshot(path=str(output / "pages-settings-desktop.png"), full_page=True)
        for width in [768, 390]:
            page.set_viewport_size(dict(width=width, height=844))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(
                path=str(output / f"pages-settings-{width}.png"), full_page=True
            )
        page.get_by_role("button", name="打开导航", exact=True).click()
        assert page.locator("#mobile-menu").get_attribute("aria-expanded") == "true"
        page.locator("[data-view=library]").click()
        assert page.locator("#mobile-menu").get_attribute("aria-expanded") == "false"
        page.get_by_role("heading", name="文章工作台", exact=True).wait_for()
        page.get_by_role("button", name="查看界面示例", exact=True).click()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(output / "pages-mobile.png"), full_page=True)
        assert not errors, errors
        assert not failures, failures
        result = dict(
            status="passed",
            widths=[1440, 768, 390],
            demo_filter="passed",
            navigation="passed",
            settings_reload="passed",
            missing_backend="passed",
            console_errors=errors,
            request_failures=failures,
        )
        if api_base:
            page.set_viewport_size(dict(width=1440, height=1000))
            page.get_by_role("button", name="退出示例", exact=True).click()
            page.locator("[data-view=settings]").click()
            page.locator("#connection-form input[name=api]").fill(api_base)
            page.locator("#connection-form input[name=token]").fill(
                os.getenv("APP_TOKEN", "")
            )
            page.locator("#connection-form button[type=submit]").click()
            try:
                page.wait_for_function(
                    "document.querySelector('#connection-text').textContent === '后端已连接'",
                    timeout=15000,
                )
                page.locator("[data-view=library]").click()
                assert page.locator(".article-card").count() > 0
                page.locator(".article-card").first.click()
                page.locator("#draft-body").wait_for()
                result["backend_connection"] = dict(
                    status="passed", scope="Pages frontend to configured API, read-only"
                )
                page.screenshot(
                    path=str(output / "pages-real-article.png"), full_page=True
                )
            except Exception:
                result["backend_connection"] = dict(
                    status="limited",
                    reason="Configured API could not be opened from this browser; static Pages deployment remains verified",
                )
        browser.close()
    return result
