"""Live API phases, real agents, isolated server storage; reusable by the E2E runner."""

import re
import time
from pathlib import Path

import httpx


class Session:
    def __init__(self, base, token, output):
        self.client = httpx.Client(
            base_url=base,
            timeout=200,
            trust_env=False,
            headers={"Authorization": "Bearer " + token},
        )
        self.output = Path(output)

    def call(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return (
            response.json()
            if "json" in response.headers.get("content-type", "")
            else response.content
        )

    def idle(self, article_id, timeout=1000):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            article = self.call("GET", "/api/articles/" + article_id)
            if article["status"] != "Process":
                if article["error"]:
                    raise AssertionError(article["error"])
                return article
            time.sleep(2)
        raise AssertionError("任务超过等待期限")

    def generate(self, case):
        created = self.call("POST", "/api/articles", json={"url": case["url"]})
        article_id = created["id"]
        article = self.idle(article_id)
        source = article["sources"][0]
        issues = [
            anchor
            for anchor in case["anchors"]
            if anchor.lower() not in source["text"].lower()
        ]
        assert not issues, "缺少正文锚点：" + str(issues)
        assert len(source["text"]) >= case["min_chars"]
        assert len(source["images"]) >= case["min_images"]
        assert len(source["embedded_media"]) >= case.get("min_embeds", 0)
        assert source["published_at"]
        assert source["quality"]["saved_images"] >= case["min_images"]
        assert all(not asset["approved"] for asset in article["assets"])
        options = dict(
            word_count=case.get("word_count", 1200),
            platform="wechat",
            provider="deepseek",
            research=True,
            style="专业、自然、克制；依照来源发布日期表述，不把历史报道当作今日新闻；保留性能测试条件，区分报道声称与已核实事实",
            related_urls=[],
            revise=False,
        )
        self.call("POST", f"/api/articles/{article_id}/generate", json=options)
        article = self.idle(article_id)
        assert article["status"] == "Done" and article["review"]
        assert article["body"] and article["summary"] and article["keywords"]
        assert '![' in article['body'], '原创稿必须包含配图'
        assert article.get('archive_title') == source['title']
        assert re.search(r"\[S\d+\]", article["body"])
        versions = self.call("GET", f"/api/articles/{article_id}/versions")
        assert len(versions) >= 2
        assert article["review"]["draft_revision"] == article["revision"]
        return dict(
            name=case["name"],
            url=case["url"],
            article_id=article_id,
            status="generated",
            source_title=source["title"],
            source_chars=len(source["text"]),
            source_published_at=source["published_at"],
            quality=source["quality"],
            embedded_media=source["embedded_media"],
            generated_title=article["title"],
            body_chars=len(article["body"]),
            target_word_count=options["word_count"],
            review_score=article["review"]["score"],
            review_issues=article["review"]["issues"],
            research=article.get("research_report", {}),
            sources=[dict(title=s["title"], url=s["url"]) for s in article["sources"]],
            versions=len(versions),
        )

    def close(self):
        self.client.close()
