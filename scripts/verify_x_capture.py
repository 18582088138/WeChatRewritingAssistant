"""Verify the user's real X post, recorded text/media quality and optional generation."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
URL = "https://x.com/laobaishare/status/2113589307789512863?s=20"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--article-id")
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    key = os.getenv("APP_TOKEN", "")
    client = httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, timeout=240, headers={"Authorization": "Bearer " + key} if key else {})
    if args.article_id:
        article = client.get("/api/articles/" + args.article_id).json()
    else:
        response = client.post("/api/articles", json=dict(url=URL))
        response.raise_for_status()
        article = response.json()
    route = "/api/articles/" + article["id"]
    for _ in range(120):
        article = client.get(route).json()
        if article["status"] != "Process":
            break
        time.sleep(3)
    assert article["sources"], article.get("error")
    source = article["sources"][0]
    assert len(source["text"]) >= 400
    assert "Eleven v4" in source["text"] and "Grok" in source["text"]
    assert source["published_at"].startswith("2026-10-23")
    assert source["videos"] and source["images"]
    if args.generate:
        response = client.post(route + "/generate", json=dict(word_count=1000, research=True))
        response.raise_for_status()
        for _ in range(200):
            article = client.get(route).json()
            if article["status"] != "Process":
                break
            time.sleep(3)
        assert article["body"] and article["review"], article.get("error")
    report = dict(article_id=article["id"], url=source["url"], archive=article["storage_path"], text_chars=len(source["text"]), published_at=source["published_at"], capture_channel=source["quality"]["method"], media_downloads=source.get("media_downloads", []), reference_count=len(article["sources"]), reference_coverage=article.get("reference_coverage"), prose_chars=article.get("prose_chars"), review=article.get("review"), research_report=article.get("research_report"), media_success=bool([a for a in article["assets"] if a["type"] == "video"]), generation_success=bool(article["body"] and article.get("review")))
    output = ROOT / "test-results/x-capture"
    output.mkdir(parents=True, exist_ok=True)
    (output / "acceptance-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"research_report", "review", "media_downloads"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
