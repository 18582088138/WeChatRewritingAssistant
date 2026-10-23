"""Shared extraction diagnostics and readable network failure reasons."""

import json
from pathlib import Path

import httpx


def failure_reason(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return {
            403: "HTTP 403：来源拒绝访问",
            404: "HTTP 404：链接不存在",
            429: "HTTP 429：来源限流",
        }.get(code, f"HTTP {code}：来源请求失败")
    if isinstance(exc, httpx.TimeoutException):
        return "网络超时"
    if isinstance(exc, httpx.ConnectError):
        return "连接失败（域名、代理或 TLS）"
    if isinstance(exc, ValueError):
        return str(exc)[:240]
    return f"{type(exc).__name__}：处理失败"


def save_metadata(source, output):
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / "metadata.json").write_text(
        json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def quality(text, method, warnings=None, **details):
    warnings = list(warnings or [])
    if text.count("\ufffd") > max(3, len(text) // 1000):
        warnings.append("正文存在字符解码损失，请核对原文")
    if len(text) < 500:
        warnings.append("来源正文较短，可能是简短公告；生成长文需补充资料")
    return dict(method=method, full_text_chars=len(text), warnings=warnings, **details)
