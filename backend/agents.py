import json
import os
import re

import httpx
from pydantic import BaseModel, Field
from .research_context import source_context as source_context
from .configuration import settings, prompt, writer_prompt
from .generation_attempts import save_attempt


class Draft(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=400)
    keywords: list[str] = Field(min_length=1, max_length=12)
    body: str = Field(min_length=100, max_length=40000)


class Issue(BaseModel):
    category: str
    severity: str
    detail: str
    suggestion: str


class Review(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    issues: list[Issue]
    strengths: list[str]
    fact_checks: list[dict]


def provider_config(provider="deepseek"):
    prefix = "OPENROUTER" if provider == "openrouter" else "DEEPSEEK"
    defaults = (
        ("https://openrouter.ai/api/v1", "deepseek/deepseek-chat")
        if prefix == "OPENROUTER"
        else ("https://api.deepseek.com", settings("generation")["model"])
    )
    return (
        os.getenv(prefix + "_API_KEY", ""),
        os.getenv(prefix + "_BASE_URL", defaults[0]).rstrip("/"),
        os.getenv(prefix + "_MODEL", defaults[1]),
    )


def complete(system, payload, provider="deepseek"):
    key, base, model = provider_config(provider)
    if not key:
        raise ValueError(f"{provider} API key 未配置，请检查本地 .env")
    cfg = settings("generation")
    review = payload.get("_agent") == "review"
    with httpx.Client(
        timeout=cfg["review_timeout_seconds"] if review else cfg["timeout_seconds"]
    ) as client:
        response = client.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": cfg["review_temperature"]
                if review
                else cfg["temperature"],
                "max_tokens": cfg["review_max_tokens"] if review else cfg["max_tokens"],
            },
        )
        if response.status_code >= 400:
            raise ValueError(
                f"模型请求失败（HTTP {response.status_code}），请检查额度、模型名称与网络"
            )
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
        return json.loads(content)


class RewritingAgent:
    def run(self, article, options, feedback=None):
        WRITER = writer_prompt()
        assets = [
            dict(
                alt=a.get("alt", "配图"),
                markdown=f"![{a.get('alt', '配图')}](/api/articles/{article['id']}/assets/{a['id']}/file)",
            )
            for a in article["assets"]
            if a["type"] == "image"
            and not a["id"].startswith("card-")
            and (
                a.get("approved")
                or settings("platforms")["include_pending_media_in_draft"]
            )
        ]
        result = complete(
            WRITER,
            dict(
                sources=source_context(article),
                options=options,
                approved_assets=assets,
                reference_videos=[dict(markdown=f"[视频：{a.get('alt', '参考视频')}](/api/articles/{article['id']}/assets/{a['id']}/file)", attribution=a.get('attribution', '')) for a in article['assets'] if a['type'] == 'video'],
                previous_draft=article.get("body", ""),
                feedback=feedback,
            ),
            options["provider"],
        )
        save_attempt(article["id"], result, "writer")
        draft = Draft.model_validate(result).model_dump()

        # Count prose without the bibliography, link destinations, and Markdown syntax.
        def prose_length(body):
            body = re.split(
                r"\n#{1,3}\s*(?:(?:信息|资料|事实|内容)?来源|参考|References)",
                body,
                maxsplit=1,
            )[0]
            body = re.sub(r"!\[[^]]*\]\([^)]*\)", "", body)
            body = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", body)
            return len(re.sub(r"\[S\d+\]|[\s#*`>-]", "", body))

        for _ in range(settings("generation")["compression_retries"]):
            measured = prose_length(draft["body"])
            if measured <= options["word_count"] * min(1.35, settings("generation")["length_tolerance"]):
                break
            compressed = complete(
                prompt("compression") + "\n" + prompt("language-style"),
                dict(
                    options=options,
                    draft=draft,
                    measured_prose_chars=measured,
                    maximum_prose_chars=options["word_count"],
                ),
                options["provider"],
            )
            save_attempt(article["id"], compressed, "compression")
            draft = Draft.model_validate(compressed).model_dump()
        if (
            prose_length(draft["body"])
            > options["word_count"] * settings("generation")["length_tolerance"]
        ):
            raise ValueError(f"模型未遵守目标篇幅（正文 {prose_length(draft['body'])} 字符，目标 {options['word_count']}），尝试稿已保存，当前文案尚未替换")
        return draft

    def paragraph(self, article, selected, instruction, provider):
        WRITER = writer_prompt()
        result = complete(
            WRITER
            + "\n此任务仅修改选中段落，输出 JSON 字段 text，不要额外标题或来源列表。保留事实与引用，不改变未选中内容。context 仅供参考，禁止把未选中的相邻段落复制到输出；返回内容将只替换 selection。",
            dict(
                sources=source_context(article),
                selection=selected,
                instruction=instruction,
                context=article["body"][:20000],
            ),
            provider,
        )
        if not isinstance(result.get("text"), str) or not result["text"].strip():
            raise ValueError("模型没有返回有效段落")
        return result["text"]


class ReviewAgent:
    def run(self, article, options):
        result = complete(
            prompt("reviewing"),
            dict(
                _agent="review",
                title=article["title"],
                body=article["body"],
                sources=source_context(article),
                assets=article["assets"],
                platform=options["platform"],
            ),
            options["provider"],
        )
        review = Review.model_validate(result).model_dump()
        citations = set(re.findall(r"\[S(\d+)\]", article["body"]))
        missing = [c for c in citations if not 1 <= int(c) <= len(article["sources"])]
        if not citations or missing:
            review["issues"].append(
                dict(
                    category="来源",
                    severity="high",
                    detail="正文缺少可核对的来源编号，或编号超出来源范围",
                    suggestion="补齐逐项来源并删除无证据结论",
                )
            )
            review["score"] = min(review["score"], 59)
        source_text = "\n".join(s["text"] for s in article["sources"])
        overlap = [
            line.strip()
            for line in article["body"].splitlines()
            if len(line.strip()) > 70 and line.strip() in source_text
        ]
        if overlap:
            review["issues"].append(
                dict(
                    category="原创性",
                    severity="high",
                    detail="存在与来源相同的长段落",
                    suggestion="重新组织论述或缩短为有标注的引用",
                )
            )
            review["score"] = min(review["score"], 59)
        review["checked_at"] = __import__("backend.store", fromlist=["now"]).now()
        review["draft_revision"] = article["revision"]
        return review
