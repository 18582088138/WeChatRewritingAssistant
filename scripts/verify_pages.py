"""Verify actual Pages bytes, MIME types, workflow results and desktop/mobile UI."""

import argparse
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from pages_browser import check_browser
from pages_actions import check_workflows

ROOT = Path(__file__).resolve().parents[1]
REPO = "18582088138/WeChatRewritingAssistant"
DEFAULT_URL = "https://18582088138.github.io/WeChatRewritingAssistant/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "test-results/pages-deployment"
    )
    parser.add_argument(
        "--browser-executable",
        default="C:/Program Files/Google/Chrome/Application/chrome.exe"
        if os.name == "nt"
        else None,
    )
    parser.add_argument(
        "--api-base", help="Optional real API connectivity test; read-only"
    )
    parser.add_argument("--skip-actions", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.api_base:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    report = dict(
        url=args.url,
        tested_at=datetime.now(timezone.utc).isoformat(),
        assets=[],
        status="running",
    )
    try:
        with httpx.Client(timeout=40, follow_redirects=True) as client:

            def asset_check(file):
                relative = file.relative_to(ROOT / "web").as_posix()
                response = client.get(args.url.rstrip("/") + "/" + relative)
                response.raise_for_status()
                expected = file.read_bytes().replace(b"\r\n", b"\n")
                actual = response.content.replace(b"\r\n", b"\n")
                assert actual == expected, (
                    "Deployed asset differs from workspace: " + relative
                )
                mime = response.headers.get("content-type", "")
                assert {".js": "javascript", ".css": "text/css", ".html": "text/html"}[
                    file.suffix
                ] in mime, mime
                return dict(
                    path=relative,
                    status=response.status_code,
                    content_type=mime,
                    sha256=hashlib.sha256(actual).hexdigest(),
                )

            files = sorted(
                file
                for file in (ROOT / "web").rglob("*")
                if file.suffix in {".js", ".css", ".html"}
            )
            with ThreadPoolExecutor(max_workers=6) as pool:
                report["assets"] = list(pool.map(asset_check, files))
            for path in [".env", "backend/app.py", "data/articles/", ".git/config"]:
                response = client.get(args.url.rstrip("/") + "/" + path)
                assert response.status_code == 404, (
                    "Unexpected server file published: " + path
                )
            report["server_files_absent"] = "passed"
            if not args.skip_actions:
                sha = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip()
                report["workflows"] = check_workflows(client, REPO, sha)
        report["browser"] = check_browser(
            args.url, output, args.browser_executable, args.api_base
        )
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error=str(exc)[:500])
        raise
    finally:
        (output / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(
            json.dumps(
                {k: v for k, v in report.items() if k != "assets"},
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
