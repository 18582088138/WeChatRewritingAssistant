"""Exercise a separately hosted frontend against an API-only backend."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(url, process):
    for _ in range(100):
        assert process.poll() is None, "Test server exited unexpectedly"
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"Server did not start: {url}")


def main():
    api_port, web_port = free_port(), free_port()
    api_url, web_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{web_port}"
    processes = []
    with tempfile.TemporaryDirectory(prefix="signal-separation-") as data:
        env = dict(
            os.environ,
            SERVE_FRONTEND="false",
            DATA_DIR=data,
            CORS_ORIGINS=web_url,
            APP_TOKEN="separation-test-token",
        )
        try:
            for args in [
                [
                    "-m",
                    "uvicorn",
                    "backend.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                ["-m", "http.server", str(web_port), "--bind", "127.0.0.1", "--directory", "web"],
            ]:
                processes.append(
                    subprocess.Popen(
                        [sys.executable, *args],
                        cwd=ROOT,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )
            ready(api_url + "/api/health", processes[0])
            ready(web_url, processes[1])
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
                    headless=True,
                )
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(web_url, wait_until="networkidle")
                page.get_by_role("button", name="设置与连接", exact=True).click()
                page.locator("input[name=api]").fill(api_url)
                page.locator("input[name=token]").fill(env["APP_TOKEN"])
                page.locator("#connection-form").evaluate("form => form.requestSubmit()")
                page.wait_for_function(
                    "document.querySelector('#connection-text').textContent === '后端已连接'"
                )
                assert page.request.get(api_url + "/").status == 404
                assert page.request.get(api_url + "/app.js").status == 404
                assert page.request.get(api_url + "/api/articles").status == 401
                assert (
                    page.evaluate(
                        "async () => (await import('./core/api.js')).api('/api/articles')"
                    )
                    == []
                )
                page.get_by_role("button", name="文章工作台", exact=True).click()
                page.get_by_role("heading", name="文章工作台", exact=True).wait_for()
                assert not errors, errors
                browser.close()
            print(
                "Separated hosting passed: static frontend, API-only backend, CORS and token authentication."
            )
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
