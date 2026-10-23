import io
import os
import uuid

import httpx
from PIL import Image

from . import store
from .network import fetch


def stock_images(article_id, query):
    key = os.getenv('PIXABAY_API_KEY')
    if not key:
        raise ValueError('请在 .env 配置 PIXABAY_API_KEY 后搜索图库素材')
    with httpx.Client(timeout=35) as client:
        response = client.get('https://pixabay.com/api/', params={
            'key': key, 'q': query, 'image_type': 'photo', 'safesearch': 'true', 'per_page': 6, 'min_width': 800})
        if response.status_code >= 400:
            raise ValueError(f'图库请求失败（HTTP {response.status_code}），请检查 Pixabay 密钥与额度')
        hits = response.json().get('hits', [])
    result = []
    for item in hits:
        try:
            raw, _, _ = fetch(item['webformatURL'], limit=8_000_000)
            image = Image.open(io.BytesIO(raw))
            if image.width * image.height > 30_000_000:
                continue
            asset_id = 'stock-' + uuid.uuid4().hex
            path = store.folder(article_id) / 'materials' / 'pixabay' / 'images' / (asset_id + '.jpg')
            path.parent.mkdir(parents=True, exist_ok=True)
            image.convert('RGB').save(path, 'JPEG', quality=92)
            result.append(dict(id=asset_id, type='image', path=str(path.relative_to(store.folder(article_id))).replace('\\', '/'),
                               alt=item.get('tags', query), source_url=item['webformatURL'], attribution=item['pageURL'],
                               approved=False, watermark='unchecked', rights=f'Pixabay / {item.get("user", "")}，需核对许可与人物商标',
                               width=image.width, height=image.height))
        except Exception:
            continue
    return result
