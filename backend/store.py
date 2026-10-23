import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DATA_DIR', ROOT / 'data')).resolve()
LOCK = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat()


def folder(article_id):
    if not article_id or any(c not in '0123456789abcdef' for c in article_id) or len(article_id) != 32:
        raise ValueError('无效的文章 ID')
    return DATA / 'articles' / article_id


def read(article_id):
    with LOCK:
        return json.loads((folder(article_id) / 'article.json').read_text(encoding='utf-8'))


def save(article, snapshot=False):
    with LOCK:
        target = folder(article['id'])
        target.mkdir(parents=True, exist_ok=True)
        article['updated_at'] = now()
        temporary = target / 'article.tmp'
        temporary.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(target / 'article.json')
        (target / 'draft.md').write_text(article.get('body', ''), encoding='utf-8')
        if snapshot:
            versions = target / 'versions'
            versions.mkdir(exist_ok=True)
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
            (versions / f'{name}.json').write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding='utf-8')
        return article


def create(url, title='待抓取的行业要闻'):
    return save(dict(id=uuid.uuid4().hex, url=url, title=title, status='New', stage='等待抓取',
                     created_at=now(), body='', summary='', keywords=[], sources=[], assets=[],
                     review=None, events=[], deliveries=[], revision=0, error=None))


def listing():
    root = DATA / 'articles'
    if not root.exists():
        return []
    result = []
    for file in root.glob('*/article.json'):
        try:
            result.append(read(file.parent.name))
        except (OSError, ValueError):
            continue
    return sorted(result, key=lambda a: a['updated_at'], reverse=True)


def event(article_id, stage, message):
    with LOCK:
        article = read(article_id)
        article['stage'] = stage
        article['events'].append(dict(at=now(), stage=stage, message=message))
        save(article)
