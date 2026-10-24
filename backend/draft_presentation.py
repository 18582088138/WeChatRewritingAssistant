"""Keep agent evidence separate from the prose presented to a human reader."""

import hashlib
import re


def clean_body(body):
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.split(r"\n#{1,6}\s*(?:(?:信息|资料|事实|内容)?来源|参考(?:资料|文献|来源|链接)?|References)\s*[:：]?\s*\n", body, maxsplit=1, flags=re.I)[0]
    body = re.sub(r"(?m)^\s*\[\^[^]]+\]:.*(?:\n[ \t]+.*)*", "", body)
    body = re.sub(r"\[S\d+\]|\[\^[^]]+\]", "", body)
    body = re.sub(r"(?m)^\s*(?:编者注|内部注释|审稿备注|写作备注|修改说明)[:：].*$", "", body)
    body = re.sub(r"（来源配图，授权与水印待确认）", "", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def digest(body):
    return hashlib.sha256(body.encode("utf8")).hexdigest()


def prepare(article):
    raw = article.get("body", "")
    clean = clean_body(raw)
    if raw != clean:
        article["agent_evidence"] = dict(body=raw, body_hash=digest(clean))
    article["body"] = clean


def evidence_body(article):
    evidence = article.get("agent_evidence", {})
    return evidence.get("body", article["body"]) if evidence.get("body_hash") == digest(article["body"]) else article["body"]


def prose_length(body):
    body = clean_body(body)
    body = re.sub(r"!\[[^]]*\]\([^)]*\)|\[视频：[^]]*\]\([^)]*\)|<video\b.*?</video>", "", body, flags=re.S)
    body = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", body)
    return len(re.sub(r"[\s#*`>_-]", "", body))
