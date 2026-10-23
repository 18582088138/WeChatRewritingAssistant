"""Real source/search checks. Accept a custom JSON corpus; never call writing agents."""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image

from backend import store
from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
from backend.research import download_assets, extract
from backend.research_quality import failure_reason
from backend.research_search import search_with_report


def probe_video(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_name,width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return dict(
            status="ok" if result.returncode == 0 else "failed",
            details=json.loads(result.stdout) if result.returncode == 0 else {},
        )
    except FileNotFoundError:
        return dict(status="not_available", reason="ffprobe 未安装；仅校验容器文件头")


def article_check(case):
    start = time.monotonic()
    article = store.create(case["url"], "抓取质量测试：" + case["name"])
    result = dict(
        name=case["name"],
        url=case["url"],
        article_id=article["id"],
        expected_limitation=case.get("expected_limitation", ""),
    )
    try:
        source = extract(case["url"], store.folder(article["id"]) / "materials/source-1/text")
        assets = download_assets(source, article["id"], 1)
        article.update(
            sources=[source], assets=assets, title=source["title"], stage="真实抓取测试完成"
        )
        store.save(article)
        issues = []
        if len(source["text"]) < case.get("min_chars", 150):
            issues.append("正文长度低于预期")
        for anchor in case.get("anchors", []):
            if anchor.lower() not in source["text"].lower():
                issues.append("缺少正文锚点：" + anchor)
        for key, actual in [
            ("images", len(source["images"])),
            ("videos", len(source["videos"])),
            ("embeds", len(source["embedded_media"])),
            ("saved_videos", source["quality"]["saved_videos"]),
            ("pages", source["quality"].get("extracted_pages", 0)),
        ]:
            if actual < case.get("min_" + key, 0):
                issues.append(f"{key} 数量低于预期")
        video_probes = []
        for asset in assets:
            path = store.folder(article["id"]) / asset["path"]
            assert path.exists() and path.stat().st_size > 0
            if asset["type"] == "image":
                with Image.open(path) as image:
                    image.verify()
            else:
                probe = probe_video(path)
                video_probes.append(dict(path=asset["path"], **probe))
                if probe["status"] == "failed":
                    issues.append("ffprobe 无法读取视频容器")
        result.update(
            status="passed" if not issues else "needs_review",
            issues=issues,
            title=source["title"],
            final_url=source["url"],
            chars=len(source["text"]),
            published_at=source.get("published_at", ""),
            quality=source["quality"],
            media_downloads=source["media_downloads"],
            embedded_media=source["embedded_media"],
            video_probes=video_probes,
            headings=source["headings"][:50],
        )
    except Exception as exc:
        result.update(
            status="limited" if case.get("expected_limitation") else "failed",
            reason=failure_reason(exc),
        )
    result["seconds"] = round(time.monotonic() - start, 1)
    return result


def search_check(case):
    report = search_with_report(case["query"])
    present = any(case.get("expected_url", "") in result["url"] for result in report["results"])
    forbidden = case.get("forbidden_title")
    incorrect = forbidden and any(forbidden in result["title"] for result in report["results"])
    return dict(**report, verification="passed" if present and not incorrect else "needs_review")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=ROOT / "scripts/research_cases.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "test-results" / ("research-" + time.strftime("%Y%m%d-%H%M%S")),
    )
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    store.DATA = args.output.resolve()
    store.DATA.mkdir(parents=True, exist_ok=True)
    report = dict(tested_at=store.now(), articles=[], searches=[])

    def save():
        (store.DATA / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
        )

    with ThreadPoolExecutor(max_workers=min(4, max(1, args.workers))) as pool:
        jobs = {pool.submit(article_check, case): case for case in cases.get("articles", [])}
        for job in as_completed(jobs):
            result = job.result()
            report["articles"].append(result)
            save()
            print(
                json.dumps(
                    {k: result[k] for k in ["name", "status", "seconds"]}, ensure_ascii=False
                ),
                flush=True,
            )
    for case in cases.get("searches", []):
        result = search_check(case)
        report["searches"].append(result)
        save()
        print(
            json.dumps(
                dict(
                    query=case["query"],
                    status=result["verification"],
                    results=len(result["results"]),
                ),
                ensure_ascii=False,
            ),
            flush=True,
        )
    print("Report: " + str(store.DATA / "report.json"))
    if any(item["status"] in {"failed", "needs_review"} for item in report["articles"]) or any(
        item["verification"] != "passed" for item in report["searches"]
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
