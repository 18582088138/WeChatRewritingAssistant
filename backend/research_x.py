"""Public X posts: official syndication first, explicitly labelled FxTwitter fallback."""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from .network import fetch
from .research_quality import quality, failure_reason


def post_identity(url):
    parsed = urlparse(url)
    if parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
        return None
    return re.fullmatch(r"/([^/]+)/status/(\d+)(?:/.*)?", parsed.path)


def extract_x(url, output):
    match = post_identity(url)
    if not match:
        raise ValueError("请输入 X 帖子的 status 链接")
    author, identifier = match.groups()
    canonical = f"https://x.com/{author}/status/{identifier}"
    failures = []
    endpoints = [
        ("x-syndication", f"https://cdn.syndication.twimg.com/tweet-result?id={identifier}&lang=zh&token=0"),
        ("fxtwitter", f"https://api.fxtwitter.com/{author}/status/{identifier}"),
    ]
    for channel, endpoint in endpoints:
        try:
            raw, _, _ = fetch(endpoint, timeout=20)
            (output / (channel + ".json")).write_bytes(raw)
            payload = json.loads(raw)
            tweet = payload.get("tweet", payload)
            if str(tweet.get("id", tweet.get("id_str", ""))) != identifier:
                raise ValueError("备用渠道未返回匹配的帖子 ID")
            account = tweet.get("author", tweet.get("user", {}))
            if account.get("screen_name", "").lower() != author.lower():
                raise ValueError("备用渠道返回的作者与链接不一致")
            text = tweet.get("note_tweet", {}).get("text") or tweet.get("text", "")
            if not text or (channel == "x-syndication" and (text.rstrip().endswith("…") or tweet.get("is_note_tweet") and not tweet.get("note_tweet", {}).get("text"))):
                raise ValueError("嵌入接口未提供完整长帖正文")
            source = normalize(tweet, canonical, channel, failures)
            source["capture_endpoint"] = endpoint
            return source
        except Exception as exc:
            failures.append(f"{channel}：{failure_reason(exc)}")
    raise ValueError("X 正文抓取失败；" + "；".join(failures) + "。可手动导入原文文件，未保存登录或错误页面。")


def normalize(tweet, canonical, channel, failures):
    account = tweet.get("author", tweet.get("user", {}))
    text = tweet.get("note_tweet", {}).get("text") or tweet["text"]
    first = next((line.strip() for line in text.splitlines() if line.strip()), "X 帖子")
    images, videos = [], []
    media = tweet.get("media", {}).get("all", []) or tweet.get("mediaDetails", [])
    for item in media:
        kind = item.get("type")
        caption = first[:120]
        if kind == "photo":
            images.append(dict(url=item.get("url") or item.get("media_url_https"), alt=caption))
        elif kind in {"video", "animated_gif", "gif"}:
            variants = item.get("variants") or item.get("video_info", {}).get("variants", [])
            variants = [v for v in variants if v.get("content_type") == "video/mp4" or v.get("container") == "mp4"]
            best = max(variants, key=lambda v: v.get("bitrate", 0), default={})
            video = best.get("url", item.get("url", ""))
            if video and ".mp4" in video:
                videos.append(video)
            thumbnail = item.get("thumbnail_url") or item.get("media_url_https")
            if thumbnail:
                images.append(dict(url=thumbnail, alt="视频封面 · " + caption))
    timestamp = tweet.get("created_timestamp")
    published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else tweet.get("created_at", "")
    warnings = list(failures)
    if channel != "x-syndication":
        warnings.append("使用第三方 FxTwitter 公共接口获取原帖，非原站直连；内容主张仍需独立核实")
    links = [dict(url=u, title=u, origin="article_link") for u in re.findall(r"https?://[^\s<>]+", text)]
    for facet in tweet.get("raw_text", {}).get("facets", []):
        if facet.get("type") == "url" and facet.get("replacement", "").startswith("http"):
            links.append(dict(url=facet["replacement"], title=facet.get("display", ""), origin="article_link"))
    return dict(title=first[:150], text=text, url=canonical, author=account.get("name", "") + " (@" + account.get("screen_name", "") + ")", published_at=published, images=images, videos=videos, embedded_media=[], links=links, headings=[], canonical_url=canonical, quality=quality(text, "x:" + channel, warnings, discovered_images=len(images), discovered_videos=len(videos), embedded_media=0))
