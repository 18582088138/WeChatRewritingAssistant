import ipaddress
import socket
import time
from urllib.parse import urljoin, urlparse

import httpx
from .configuration import settings

HEADERS = {"User-Agent": "WeChatRewritingAssistant/0.1 (research; source attribution)"}
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def source_headers(url, referer=None):
    headers = {"Referer": referer} if referer else {}
    if urlparse(url).hostname in {"mp.weixin.qq.com", "zhidx.com", "oss.zhidx.com"}:
        headers.update({"User-Agent": BROWSER_USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    return headers


def validate_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("请输入公开的 HTTP/HTTPS 文章链接")
    if parsed.port not in (None, 80, 443):
        raise ValueError("仅支持标准 HTTP/HTTPS 端口")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except OSError as exc:
        raise ValueError("无法解析来源域名") from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("不能抓取本机、内网或保留地址")
    return url


def fetch(url, limit=12_000_000, referer=None, timeout=35):
    retries = settings("research").get("download_retries", 1)
    for attempt in range(retries + 1):
        try:
            return _fetch(url, limit, referer, timeout)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            transient = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {500, 502, 503, 504}
            if not transient or attempt == retries:
                raise
            time.sleep(min(2 ** attempt, 4))


def _fetch(url, limit, referer, timeout):
    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=False) as client:
        for _ in range(6):
            validate_url(url)
            headers = source_headers(url, referer)
            with client.stream("GET", url, headers=headers) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("来源文件超过下载大小限制")
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", ""), url
    raise ValueError("来源重定向次数过多")
