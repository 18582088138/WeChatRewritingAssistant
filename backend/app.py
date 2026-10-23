import io
import json
import os
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from . import store
from .agents import RewritingAgent, provider_config
from .network import validate_url
from .materials import stock_images
from .publishing import PLATFORMS, wechat_draft
from .render import cards, document, export_zip, html
from .workflow import ingest, run


def auth(request: Request):
    import secrets
    token = os.getenv('APP_TOKEN', '')
    if token and not secrets.compare_digest(request.headers.get('Authorization', ''), 'Bearer ' + token):
        raise HTTPException(401, '请在设置中填写后端访问令牌')


@asynccontextmanager
async def lifespan(app):
    recover()
    yield


app = FastAPI(title='Signal Studio · WeChatRewritingAssistant', version='0.1.0', lifespan=lifespan)
origins = os.getenv('CORS_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,https://18582088138.github.io').split(',')
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins], allow_methods=['GET', 'POST', 'PATCH'],
                   allow_headers=['Authorization', 'Content-Type'])
API = [Depends(auth)]
BUSY = set()
BUSY_LOCK = threading.Lock()


def get_article(article_id):
    try:
        return store.read(article_id)
    except (OSError, ValueError):
        raise HTTPException(404, '文章不存在')


def launch(article_id, fn, *args):
    with BUSY_LOCK:
        if article_id in BUSY:
            raise HTTPException(409, '文章正在处理，请等待当前任务完成')
        BUSY.add(article_id)
    try:
        fn(*args)
    finally:
        with BUSY_LOCK:
            BUSY.discard(article_id)


def reserve(article_id):
    with BUSY_LOCK:
        if article_id in BUSY:
            raise HTTPException(409, '文章正在处理')
        BUSY.add(article_id)


def background_job(article_id, options=None, fetch_only=False, review_only=False):
    try:
        if fetch_only:
            try:
                ingest(article_id)
                article = store.read(article_id)
                article.update(status='New', stage='来源已就绪', error=None)
                store.save(article)
            except Exception as exc:
                article = store.read(article_id)
                article.update(status='New', stage='抓取失败', error=str(exc)[:300] if isinstance(exc, ValueError) else '抓取失败，请检查网络或粘贴原文')
                store.save(article)
        else:
            run(article_id, options, review_only)
    finally:
        with BUSY_LOCK:
            BUSY.discard(article_id)


class ImportArticle(BaseModel):
    url: str = Field(max_length=2000)
    title: str = Field(default='', max_length=240)
    text: str = Field(default='', max_length=100000)


class Options(BaseModel):
    word_count: int = Field(default=1200, ge=300, le=6000)
    style: str = Field(default='专业、有观点、自然简洁', max_length=300)
    platform: Literal['wechat', 'x', 'xiaohongshu', 'weibo'] = 'wechat'
    provider: Literal['deepseek', 'openrouter'] = 'deepseek'
    research: bool = True
    related_urls: list[str] = Field(default_factory=list, max_length=4)
    revise: bool = False


class Edit(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(max_length=50000)
    summary: str = Field(max_length=400)
    keywords: list[str] = Field(max_length=12)
    revision: int


class Paragraph(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    revision: int
    instruction: str = Field(default='让表达更自然简洁，保留事实与来源', max_length=1000)
    provider: Literal['deepseek', 'openrouter'] = 'deepseek'


class Approval(BaseModel):
    approved: bool
    alt: str = Field(default='配图', max_length=240)


class StockQuery(BaseModel):
    query: str = Field(min_length=1, max_length=120)


class Publish(BaseModel):
    platforms: list[Literal['wechat', 'x', 'xiaohongshu', 'weibo']] = Field(min_length=1, max_length=4)


@app.get('/api/health')
def health():
    return {'ok': True, 'version': '0.1.0', 'requires_token': bool(os.getenv('APP_TOKEN'))}


@app.get('/api/articles', dependencies=API)
def articles():
    return store.listing()


@app.post('/api/articles', dependencies=API, status_code=201)
def import_article(payload: ImportArticle, background: BackgroundTasks):
    try:
        validate_url(payload.url)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if payload.text and len(payload.text.strip()) < 150:
        raise HTTPException(422, '粘贴的原文至少需要 150 字')
    article = store.create(payload.url, payload.title or '待抓取的行业要闻')
    if payload.text:
        path = store.folder(article['id']) / 'materials' / 'source-1' / 'text'
        path.mkdir(parents=True)
        (path / 'text.txt').write_text(payload.text, encoding='utf-8')
        article['sources'] = [dict(title=payload.title or '手动导入来源', url=payload.url, text=payload.text,
                                   retrieved_at=store.now(), images=[], videos=[])]
        article['stage'] = '来源已就绪'
        store.save(article)
    else:
        reserve(article['id'])
        article.update(status='Process', stage='抓取来源')
        store.save(article)
        background.add_task(background_job, article['id'], fetch_only=True)
    return article


@app.get('/api/articles/{article_id}', dependencies=API)
def detail(article_id: str):
    return get_article(article_id)


@app.post('/api/articles/{article_id}/generate', dependencies=API, status_code=202)
def generate(article_id: str, options: Options, background: BackgroundTasks):
    article = get_article(article_id)
    if not provider_config(options.provider)[0]:
        raise HTTPException(422, '所选模型未配置 API key')
    reserve(article_id)
    article.update(status='Process', stage='排队生成', error=None, options=options.model_dump())
    store.save(article)
    background.add_task(background_job, article_id, options.model_dump())
    return article


@app.post('/api/articles/{article_id}/review', dependencies=API, status_code=202)
def review(article_id: str, options: Options, background: BackgroundTasks):
    article = get_article(article_id)
    if not article['body']:
        raise HTTPException(422, '请先生成或保存正文')
    if not provider_config(options.provider)[0]:
        raise HTTPException(422, '所选模型未配置 API key')
    reserve(article_id)
    article.update(status='Process', stage='独立审稿', error=None)
    store.save(article)
    background.add_task(background_job, article_id, options.model_dump(), review_only=True)
    return article


@app.patch('/api/articles/{article_id}', dependencies=API)
def edit(article_id: str, payload: Edit):
    result = []
    def operation():
        article = get_article(article_id)
        if payload.revision != article['revision']:
            raise HTTPException(409, '文章已更新，请刷新后再编辑')
        article.update(payload.model_dump(exclude={'revision'}))
        article['revision'] += 1
        article['review'] = None
        article['stage'] = '人工编辑，待审稿'
        result.append(store.save(article, snapshot=True))
    launch(article_id, operation)
    return result[0]


@app.post('/api/articles/{article_id}/paragraph', dependencies=API)
def paragraph(article_id: str, payload: Paragraph):
    result = []
    def operation():
        article = get_article(article_id)
        if article['revision'] != payload.revision:
            raise HTTPException(409, '文章已更新，请刷新后再选择段落')
        if not 0 <= payload.start < payload.end <= len(article['body']):
            raise HTTPException(422, '请选择有效的正文段落')
        selected = article['body'][payload.start:payload.end]
        try:
            text = RewritingAgent().paragraph(article, selected, payload.instruction, payload.provider)
        except Exception as exc:
            raise HTTPException(502, str(exc)[:300] if isinstance(exc, ValueError) else '段落生成失败，请检查模型与网络')
        article['body'] = article['body'][:payload.start] + text + article['body'][payload.end:]
        article['revision'] += 1
        article['review'] = None
        article['stage'] = '局部重写，待审稿'
        result.append(store.save(article, snapshot=True))
    launch(article_id, operation)
    return result[0]


@app.get('/api/articles/{article_id}/preview', dependencies=API, response_class=HTMLResponse)
def preview(article_id: str):
    return document(get_article(article_id))


@app.get('/api/articles/{article_id}/render', dependencies=API)
def rendered(article_id: str):
    return {'html': html(get_article(article_id)['body'])}


@app.get('/api/articles/{article_id}/versions', dependencies=API)
def versions(article_id: str):
    get_article(article_id)
    return [dict(**json.loads(p.read_text(encoding='utf-8')), version_id=p.stem) for p in sorted((store.folder(article_id) / 'versions').glob('*.json'), reverse=True)][:30]


@app.post('/api/articles/{article_id}/assets', dependencies=API)
async def upload(article_id: str, file: UploadFile = File(...)):
    raw = await file.read(12_000_001)
    if len(raw) > 12_000_000:
        raise HTTPException(413, '图片不能超过 12 MB')
    try:
        image = Image.open(io.BytesIO(raw))
        if image.width * image.height > 30_000_000:
            raise ValueError('图片像素过大')
        image.load()
    except Exception:
        raise HTTPException(422, '请上传有效的 PNG、JPEG 或 WebP 图片')
    result = []
    def operation():
        article = get_article(article_id)
        asset_id = uuid.uuid4().hex
        path = store.folder(article_id) / 'materials' / 'local' / 'images' / (asset_id + '.jpg')
        path.parent.mkdir(parents=True, exist_ok=True)
        image.convert('RGB').save(path, quality=92)
        article['assets'].append(dict(id=asset_id, type='image', path=str(path.relative_to(store.folder(article_id))).replace('\\', '/'),
                                     alt=Path(file.filename or '本地图片').stem[:240], approved=False, watermark='unchecked',
                                     rights='本地上传，需确认授权与水印', source_url='', attribution='', width=image.width, height=image.height))
        article['review'] = None
        result.append(store.save(article))
    launch(article_id, operation)
    return result[0]


@app.patch('/api/articles/{article_id}/assets/{asset_id}', dependencies=API)
def approve(article_id: str, asset_id: str, payload: Approval):
    result = []
    def operation():
        article = get_article(article_id)
        asset = next((a for a in article['assets'] if a['id'] == asset_id), None)
        if not asset:
            raise HTTPException(404, '素材不存在')
        asset.update(approved=payload.approved, alt=payload.alt,
                     watermark='manually_checked' if payload.approved else 'unchecked')
        article['review'] = None
        result.append(store.save(article))
    launch(article_id, operation)
    return result[0]


@app.get('/api/articles/{article_id}/assets/{asset_id}/file', dependencies=API)
def asset_file(article_id: str, asset_id: str):
    article = get_article(article_id)
    asset = next((a for a in article['assets'] if a['id'] == asset_id), None)
    if not asset:
        raise HTTPException(404, '素材不存在')
    root = store.folder(article_id).resolve()
    path = (root / asset['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, '素材文件不存在')
    return FileResponse(path)


@app.post('/api/articles/{article_id}/cards', dependencies=API)
def make_cards(article_id: str):
    result = []
    def operation():
        article = get_article(article_id)
        if not article['body']:
            raise HTTPException(422, '请先生成正文')
        created = cards(article)
        article['assets'] = [a for a in article['assets'] if not a['id'].startswith('card-')] + created
        result.append(store.save(article))
    launch(article_id, operation)
    return result[0]


@app.post('/api/articles/{article_id}/stock', dependencies=API)
def stock(article_id: str, payload: StockQuery):
    result = []
    def operation():
        article = get_article(article_id)
        try:
            assets = stock_images(article_id, payload.query)
        except Exception as exc:
            raise HTTPException(502, str(exc)[:300] if isinstance(exc, ValueError) else '图库搜索失败，请检查网络')
        article['assets'] += assets
        result.append(store.save(article))
    launch(article_id, operation)
    return result[0]


def read_settings():
    file = store.DATA / 'settings.json'
    return json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'wechat': {'author': '', 'thumb_media_id': ''}}


class WechatSettings(BaseModel):
    author: str = Field(default='', max_length=8)
    thumb_media_id: str = Field(default='', max_length=200)


class Settings(BaseModel):
    wechat: WechatSettings


@app.get('/api/settings', dependencies=API)
def settings():
    return dict(**read_settings(), platforms=PLATFORMS,
                providers=[dict(id=p, configured=bool(provider_config(p)[0]), model=provider_config(p)[2]) for p in ['deepseek', 'openrouter']],
                wechat_configured=bool(os.getenv('WECHAT_APP_ID') and os.getenv('WECHAT_APP_SECRET')))


@app.post('/api/settings', dependencies=API)
def save_settings(payload: Settings):
    store.DATA.mkdir(parents=True, exist_ok=True)
    with store.LOCK:
        temp = store.DATA / 'settings.tmp'
        temp.write_text(payload.model_dump_json(indent=2), encoding='utf-8')
        temp.replace(store.DATA / 'settings.json')
    return settings()


@app.post('/api/articles/{article_id}/deliver', dependencies=API)
def deliver(article_id: str, payload: Publish):
    results = []
    def operation():
        article = get_article(article_id)
        if not article['body']:
            raise HTTPException(422, '文章正文为空')
        for platform in dict.fromkeys(payload.platforms):
            try:
                if platform == 'wechat':
                    result = wechat_draft(article, read_settings())
                else:
                    exports = store.folder(article_id) / 'exports'
                    exports.mkdir(exist_ok=True)
                    (exports / f'{platform}-r{article["revision"]}.zip').write_bytes(export_zip(article, platform))
                    result = dict(platform=platform, status='export_ready', at=store.now(),
                                  message='素材包已就绪，请下载后在平台手动保存草稿')
            except Exception as exc:
                result = dict(platform=platform, status='failed', at=store.now(),
                              message=str(exc)[:300] if isinstance(exc, ValueError) else '平台接口请求失败，请检查网络和配置')
            results.append(result)
        article['deliveries'] += results
        store.save(article, snapshot=True)
    launch(article_id, operation)
    return results


@app.get('/api/articles/{article_id}/export/{platform}', dependencies=API)
def export(article_id: str, platform: Literal['wechat', 'x', 'xiaohongshu', 'weibo']):
    return Response(export_zip(get_article(article_id), platform), media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="{platform}-draft.zip"'})


def recover():
    for article in store.listing():
        if article['status'] == 'Process':
            article.update(status='Done' if article['body'] else 'New', stage='任务中断，可重试', error='后端已重启，请重新运行任务')
            store.save(article)


app.mount('/', StaticFiles(directory=str(store.ROOT / 'web'), html=True), name='web')
