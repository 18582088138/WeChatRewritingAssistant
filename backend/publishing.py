import os

import httpx
from bs4 import BeautifulSoup

from . import store
from .render import html

PLATFORMS = [
    dict(id='wechat', name='微信公众号', mode='remote_draft', description='官方 draft/add 接口；需公众号权限、IP 白名单和封面素材', url='https://mp.weixin.qq.com/'),
    dict(id='x', name='X', mode='export', description='导出文案与图片，在 X 手动保存草稿', url='https://x.com/compose/post'),
    dict(id='xiaohongshu', name='小红书', mode='export', description='导出 3:4 组图和文案，在创作平台保存草稿', url='https://creator.xiaohongshu.com/'),
    dict(id='weibo', name='微博', mode='export', description='导出图文素材，在微博手动保存草稿', url='https://weibo.com/'),
]


def wechat_check(response):
    response.raise_for_status()
    data = response.json()
    if data.get('errcode'):
        raise ValueError(f'微信接口拒绝请求（错误码 {data["errcode"]}），请检查权限、IP 白名单、凭据与素材限制')
    return data


def wechat_draft(article, settings):
    app_id, secret = os.getenv('WECHAT_APP_ID'), os.getenv('WECHAT_APP_SECRET')
    if not app_id or not secret:
        raise ValueError('请在 .env 配置 WECHAT_APP_ID 与 WECHAT_APP_SECRET')
    approved = [a for a in article['assets'] if a.get('approved') and a['type'] == 'image']
    cover_id = settings.get('wechat', {}).get('thumb_media_id', '').strip()
    if not approved and not cover_id:
        raise ValueError('公众号草稿需要封面：请选择已确认素材，或配置 thumb_media_id')
    soup = BeautifulSoup(html(article['body']), 'html.parser')
    if soup.find('video'):
        raise ValueError('公众号草稿暂不支持本地视频上传，请先移除视频嵌入；视频仍可用于本地预览与素材包导出')
    with httpx.Client(timeout=60) as client:
        token = wechat_check(client.post('https://api.weixin.qq.com/cgi-bin/stable_token', json={
            'grant_type': 'client_credential', 'appid': app_id, 'secret': secret}))['access_token']
        if not cover_id:
            cover = store.folder(article['id']) / approved[0]['path']
            with cover.open('rb') as file:
                cover_id = wechat_check(client.post('https://api.weixin.qq.com/cgi-bin/material/add_material',
                    params={'access_token': token, 'type': 'image'}, files={'media': (cover.name, file, 'image/' + ('png' if cover.suffix == '.png' else 'jpeg'))}))['media_id']
        for image in soup.find_all('img'):
            asset = next((a for a in approved if image.get('src') == f"/api/articles/{article['id']}/assets/{a['id']}/file"), None)
            if not asset:
                raise ValueError('正文含外部或未确认图片，请从已批准素材替换后再投递')
            path = store.folder(article['id']) / asset['path']
            with path.open('rb') as file:
                image['src'] = wechat_check(client.post('https://api.weixin.qq.com/cgi-bin/media/uploadimg',
                    params={'access_token': token}, files={'media': (path.name, file)}))['url']
        config = settings.get('wechat', {})
        result = wechat_check(client.post('https://api.weixin.qq.com/cgi-bin/draft/add', params={'access_token': token},
            json={'articles': [{'title': article['title'][:64], 'author': config.get('author', '')[:8],
                               'digest': article['summary'][:120], 'content': str(soup), 'content_source_url': article['url'],
                               'thumb_media_id': cover_id, 'need_open_comment': 0, 'only_fans_can_comment': 0}]}))
        return dict(platform='wechat', status='draft_saved', media_id=result['media_id'], at=store.now(), message='已写入微信公众号草稿箱，最终发布请在公众号后台操作')
