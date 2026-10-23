import io
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image
from pypdf import PdfReader

from . import store
from .network import fetch


def extract(url, output: Path):
    raw, kind, final = fetch(url)
    output.mkdir(parents=True, exist_ok=True)
    images, videos = [], []
    if 'pdf' in kind or raw.startswith(b'%PDF'):
        (output / 'source.pdf').write_bytes(raw)
        reader = PdfReader(io.BytesIO(raw))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages[:60])
        title = str((reader.metadata or {}).get('/Title', '') or urlparse(final).path.split('/')[-1])
    else:
        (output / 'source.html').write_bytes(raw)
        soup = BeautifulSoup(raw, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else urlparse(final).hostname
        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            title = og['content']
        main = soup.select_one('#js_content') or soup.find('article') or soup.find('main') or soup.body or soup
        for img in main.find_all('img'):
            link = img.get('data-src') or img.get('src')
            if link and not link.startswith('data:'):
                images.append({'url': urljoin(final, link), 'alt': img.get('alt', '')})
        for video in main.find_all(['video', 'source']):
            if video.get('src'):
                videos.append(urljoin(final, video['src']))
        for tag in main.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        text = main.get_text('\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    if len(text) < 150:
        raise ValueError('未能获取足够正文，来源可能需要登录或使用动态渲染。请粘贴原文导入。')
    (output / 'text.txt').write_text(text, encoding='utf-8')
    source = dict(title=title[:240], url=final, text=text[:65000], retrieved_at=store.now(),
                  images=images[:12], videos=videos[:3])
    (output / 'metadata.json').write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    return source


def search(query):
    raw, _, _ = fetch('https://www.google.com/search?q=' + __import__('urllib.parse', fromlist=['quote']).quote(query), limit=2_000_000)
    soup = BeautifulSoup(raw, 'html.parser')
    results = []
    for a in soup.select('a[href]'):
        link = a['href']
        if link.startswith('/url?'):
            link = parse_qs(urlparse(link).query).get('q', [''])[0]
        label = a.get_text(' ', strip=True)
        host = urlparse(link).hostname or ''
        if link.startswith('http') and label and 'google.' not in host and len(label) > 12:
            if not any(r['url'] == link for r in results):
                results.append(dict(url=unquote(link), title=label[:180]))
    return results[:6]


def download_assets(source, article_id, source_number):
    result = []
    root = store.folder(article_id) / 'materials' / f'source-{source_number}'
    for index, item in enumerate(source.get('images', [])[:6]):
        try:
            raw, mime, _ = fetch(item['url'], limit=8_000_000)
            image = Image.open(io.BytesIO(raw))
            image.verify()
            image = Image.open(io.BytesIO(raw))
            if image.width < 400 or image.height < 240 or image.width * image.height > 30_000_000:
                continue
            path = root / 'images' / f'{index}.jpg'
            path.parent.mkdir(parents=True, exist_ok=True)
            image.convert('RGB').save(path, 'JPEG', quality=90)
            result.append(dict(id=f's{source_number}-image-{index}', type='image',
                               path=str(path.relative_to(store.folder(article_id))).replace('\\', '/'),
                               source_url=item['url'], attribution=source['url'], alt=item.get('alt', ''),
                               width=image.width, height=image.height, approved=False,
                               rights='来源图片，需确认授权与水印', watermark='unchecked'))
        except Exception:
            continue
    for index, url in enumerate(source.get('videos', [])[:1]):
        try:
            raw, mime, _ = fetch(url, limit=25_000_000)
            if not mime.startswith('video/'):
                continue
            path = root / 'videos' / f'{index}.mp4'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            result.append(dict(id=f's{source_number}-video-{index}', type='video',
                               path=str(path.relative_to(store.folder(article_id))).replace('\\', '/'),
                               source_url=url, attribution=source['url'], approved=False,
                               rights='来源视频，需确认授权', watermark='unchecked'))
        except Exception:
            continue
    return result
