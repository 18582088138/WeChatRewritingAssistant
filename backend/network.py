import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

HEADERS = {'User-Agent': 'WeChatRewritingAssistant/0.1 (research; source attribution)'}


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请输入公开的 HTTP/HTTPS 文章链接')
    if parsed.port not in (None, 80, 443):
        raise ValueError('仅支持标准 HTTP/HTTPS 端口')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except OSError as exc:
        raise ValueError('无法解析来源域名') from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('不能抓取本机、内网或保留地址')
    return url


def fetch(url, limit=12_000_000):
    with httpx.Client(timeout=35, headers=HEADERS, follow_redirects=False) as client:
        for _ in range(6):
            validate_url(url)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ValueError('来源文件超过下载大小限制')
                    chunks.append(chunk)
                return b''.join(chunks), response.headers.get('content-type', ''), url
    raise ValueError('来源重定向次数过多')
