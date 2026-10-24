"""Platform-specific caption tags; WeChat uses ordinary keyword text."""

import re


def format_keywords(keywords, platform):
    tags = [k.strip().strip("#") for k in keywords if k.strip().strip("#")]
    if platform == "wechat":
        return "，".join(tags)
    tags = [re.sub(r"\s+", "", tag) for tag in tags]
    return " ".join("#" + tag + ("#" if platform == "weibo" else "") for tag in tags)
