import io
import re
import zipfile
from pathlib import Path

import bleach
import markdown
from PIL import Image, ImageDraw, ImageFont

from . import store

TAGS = ['p', 'br', 'h2', 'h3', 'h4', 'strong', 'em', 'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'code', 'pre', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td']
STYLES = {'p': 'margin:0 0 20px;line-height:1.9;color:#293344;', 'h2': 'font-size:23px;margin:34px 0 18px;color:#172733;',
          'h3': 'font-size:19px;margin:26px 0 14px;', 'blockquote': 'border-left:3px solid #138a72;padding:12px 20px;background:#eff8f4;',
          'img': 'max-width:100%;height:auto;border-radius:10px;', 'a': 'color:#138a72;', 'li': 'line-height:1.9;margin-bottom:8px;',
          'table': 'width:100%;border-collapse:collapse;', 'th': 'border:1px solid #dbe5e0;padding:8px;', 'td': 'border:1px solid #dbe5e0;padding:8px;'}


def html(body):
    safe = bleach.clean(markdown.markdown(body, extensions=['tables', 'fenced_code']), tags=TAGS,
                        attributes={'a': ['href', 'title'], 'img': ['src', 'alt']}, protocols=['http', 'https'], strip=True)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(safe, 'html.parser')
    for tag in soup.find_all(True):
        if tag.name in STYLES:
            tag['style'] = STYLES[tag.name]
        if tag.name == 'a':
            tag['rel'] = 'noopener noreferrer'
            tag['target'] = '_blank'
    return str(soup)


def document(article):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + bleach.clean(article['title'], tags=[], strip=True) + '</title><body style="max-width:720px;margin:40px auto;padding:24px;font-family:system-ui,sans-serif;background:#fafcfb"><h1>' + bleach.clean(article['title'], tags=[], strip=True) + '</h1>' + html(article['body']) + '</body></html>'


def font(size):
    for file in ['C:/Windows/Fonts/msyh.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(file).exists():
            return ImageFont.truetype(file, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, max_width):
    lines, line = [], ''
    for char in text:
        if char == '\n' or draw.textlength(line + char, font=face) > max_width:
            lines.append(line)
            line = '' if char == '\n' else char
        else:
            line += char
    if line:
        lines.append(line)
    return lines


def cards(article):
    sections = re.split(r'\n(?=## )', article['body'])
    sections = [s.strip() for s in sections if s.strip() and not s.strip().startswith('## 来源')]
    pages = [('本期观察', article['title'], article['summary'])]
    for section in sections:
        lines = section.splitlines()
        heading = lines[0].lstrip('# ').strip() if lines[0].startswith('#') else '关键解读'
        content = '\n'.join(lines[1:] if lines[0].startswith('#') else lines)
        content = re.sub(r'!\[[^]]*\]\([^)]*\)', '', content)
        content = re.sub(r'\[([^]]+)\]\(https?://[^)]+\)', r'\1', content)
        content = re.sub(r'[*`#]', '', content).strip()
        # Split long sections rather than silently discarding the latter half.
        for offset in range(0, len(content), 420):
            pages.append(('行业解读' if not offset else '接上页', heading, content[offset:offset + 420]))
    refs = '\n\n'.join(f"[S{i+1}] {s['title']}\n{s['url']}" for i, s in enumerate(article['sources']))
    for offset in range(0, len(refs), 500):
        pages.append(('事实有据', '来源与参考', refs[offset:offset + 500]))
    root = store.folder(article['id']) / 'generated' / f'cards-r{article["revision"]}'
    root.mkdir(parents=True, exist_ok=True)
    assets = []
    for index, (eyebrow, title, content) in enumerate(pages):
        image = Image.new('RGB', (1080, 1440), '#f5f2ea')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((58, 55, 1022, 1385), radius=28, fill='#fffef9')
        draw.rounded_rectangle((100, 105, 295, 155), radius=25, fill='#deeee5')
        draw.text((122, 114), eyebrow, font=font(25), fill='#277362')
        draw.text((815, 120), f'{index + 1:02d} / {len(pages):02d}', font=font(26), fill='#77827b')
        y = 205
        for line in wrap(draw, title, font(58), 840):
            draw.text((110, y), line, font=font(58), fill='#1b3431')
            y += 83
        draw.line((110, y + 18, 970, y + 18), fill='#d9e3dd', width=2)
        y += 63
        if index == 0:
            cover = next((a for a in article['assets'] if a['type'] == 'image' and a.get('approved') and not a['id'].startswith('card-')), None)
            if cover:
                from PIL import ImageOps
                visual = ImageOps.fit(Image.open(store.folder(article['id']) / cover['path']).convert('RGB'), (840, 400))
                image.paste(visual, (110, int(y)))
                y += 440
        # Adapt font size to ensure all text fits within the card.
        size = 34
        while size > 19:
            content_lines = wrap(draw, content, font(size), 840)
            if y + len(content_lines) * (size + 18) <= 1250:
                break
            size -= 1
        for line in content_lines:
            draw.text((110, y), line, font=font(size), fill='#46554f')
            y += size + 18
        draw.text((110, 1310), 'SIGNAL STUDIO  /  科技内容工作台', font=font(22), fill='#849189')
        path = root / f'{index + 1:02d}.png'
        image.save(path)
        assets.append(dict(id=f'card-r{article["revision"]}-{index}', type='image', path=str(path.relative_to(store.folder(article['id']))).replace('\\', '/'),
                           alt=title, approved=True, watermark='none', rights='本地排版生成', source_url='', attribution='', width=1080, height=1440))
    return assets


def export_zip(article, platform):
    stream = io.BytesIO()
    body = article['body']
    if platform in ('xiaohongshu', 'weibo', 'x'):
        text = article['title'] + '\n\n' + re.sub(r'!\[[^]]*\]\([^)]*\)', '', body)
        text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
        text = re.sub(r'[*`#]', '', text)
        text += '\n\n' + ' '.join('#' + k for k in article['keywords'])
    else:
        text = body
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('draft.md', '# ' + article['title'] + '\n\n' + body)
        archive.writestr('caption.txt', text)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(document(article), 'html.parser')
        for image in soup.find_all('img'):
            match = re.fullmatch(r'/api/articles/' + article['id'] + r'/assets/([^/]+)/file', image.get('src', ''))
            if match:
                asset = next((a for a in article['assets'] if a['id'] == match[1] and a['approved']), None)
                if asset:
                    image['src'] = 'assets/' + Path(asset['path']).name
                else:
                    image.decompose()
        archive.writestr('preview.html', str(soup))
        archive.writestr('README.txt', '这是发布素材包。请在对应平台创建草稿，检查字数、分段、图文、来源与授权后保存。\n组图为 1080×1440 PNG。X 长文需要对应账号权限，普通帖子请按实际限额拆分。\n未调用任何直接发布接口。')
        for asset in article['assets']:
            if asset.get('approved'):
                path = store.folder(article['id']) / asset['path']
                archive.write(path, 'assets/' + path.name)
    return stream.getvalue()
