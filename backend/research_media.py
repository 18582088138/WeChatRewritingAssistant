"""Discover lazy images, responsive candidates, direct videos and external embeds."""

import json
import re
from urllib.parse import parse_qs, urljoin, urlparse


def public_link(base, link):
    if not isinstance(link, str) or not link.strip():
        return ""
    url = urljoin(base, link.strip())
    return url if urlparse(url).scheme in {"http", "https"} else ""


def candidates(tag, base):
    values = []
    for attr in ["data-srcset", "srcset"]:
        for item in (tag.get(attr) or "").split(","):
            bits = item.strip().split()
            if bits:
                weight = float(re.sub(r"[^0-9.]", "", bits[-1]) or 1) if len(bits) > 1 else 1
                values.append((weight, public_link(base, bits[0])))
    values.sort(reverse=True)
    urls = [url for _, url in values if url]
    urls += [
        public_link(base, tag.get(attr))
        for attr in ["data-src", "data-original", "data-lazy-src", "src"]
    ]
    return list(dict.fromkeys(url for url in urls if url))


def discover_media(main, soup, final):
    images, videos, embedded = [], [], []
    seen = set()
    for img in main.find_all("img"):
        links = candidates(img, final)
        if img.parent.name == "picture":
            links = list(
                dict.fromkeys(
                    [u for s in img.parent.find_all("source") for u in candidates(s, final)] + links
                )
            )
        if not links or links[0] in seen:
            continue
        if "cdn-avatars." in (urlparse(links[0]).hostname or ""):
            continue
        seen.add(links[0])
        figure = img.find_parent("figure")
        caption = figure.find("figcaption") if figure else None
        images.append(
            dict(
                url=links[0],
                candidates=links,
                alt=img.get("alt", ""),
                caption=caption.get_text(" ", strip=True) if caption else "",
            )
        )
    for video in main.find_all("video"):
        for tag in [video, *video.find_all("source")]:
            url = public_link(final, tag.get("src") or tag.get("data-src"))
            if url:
                videos.append(url)
        poster = public_link(final, video.get("poster"))
        if poster and poster not in seen:
            seen.add(poster)
            images.append(dict(url=poster, candidates=[poster], alt="视频封面", caption=""))
    for tag in main.find_all(["iframe", "embed", "object"]):
        url = public_link(final, tag.get("data-src") or tag.get("src") or tag.get("data"))
        if not url:
            continue
        if re.search(r"\.(mp4|mov|webm)(?:[?#]|$)", url, re.I):
            videos.append(url)
        elif tag.get("type", "").startswith("image/") or re.search(
            r"\.(svg|png|jpe?g|webp)(?:[?#]|$)", url, re.I
        ):
            if url not in seen:
                seen.add(url)
                images.append(dict(url=url, candidates=[url], alt=tag.get("title", ""), caption=""))
        else:
            embedded.append(
                dict(
                    url=url,
                    type="external_player",
                    title=tag.get("title", ""),
                    status="reference_only",
                    reason="外部播放器链接已记录；不代表视频文件已下载",
                )
            )

    for anchor in main.select("a[href]"):
        url = public_link(final, anchor["href"])
        host = urlparse(url).hostname or ""
        if (
            (host.endswith("youtube.com") and ("/watch" in url or "/embed/" in url))
            or host == "youtu.be"
            or host == "player.bilibili.com"
        ):
            embedded.append(
                dict(
                    url=url,
                    type="external_player",
                    title=anchor.get_text(" ", strip=True),
                    status="reference_only",
                    reason="正文视频链接；保留播放器地址，未下载视频文件",
                )
            )
    # Interactive players may only expose a YouTube poster before user interaction.
    for image in images:
        url = image["url"]
        inner = parse_qs(urlparse(url).query).get("url", [url])[0]
        match = re.search(r"(?:img|i)\.youtube\.com/vi/([^/]+)/", inner)
        if match:
            embedded.append(
                dict(
                    url="https://www.youtube.com/watch?v=" + match[1],
                    type="external_player",
                    title=image.get("alt", ""),
                    status="reference_only",
                    reason="由视频封面识别的播放器地址，未下载视频文件",
                )
            )

    def inspect(obj):
        if isinstance(obj, list):
            for item in obj:
                inspect(item)
        elif isinstance(obj, dict):
            if "VideoObject" in str(obj.get("@type", "")):
                direct = public_link(final, obj.get("contentUrl"))
                player = public_link(final, obj.get("embedUrl"))
                if direct:
                    videos.append(direct)
                elif player:
                    embedded.append(
                        dict(
                            url=player,
                            type="external_player",
                            title=obj.get("name", ""),
                            status="reference_only",
                            reason="结构化播放器链接，不代表视频已下载",
                        )
                    )
            for key in ["@graph", "video"]:
                inspect(obj.get(key, []))

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            inspect(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            pass
    return (
        images,
        list(dict.fromkeys(videos)),
        list({item["url"]: item for item in embedded}.values()),
    )
