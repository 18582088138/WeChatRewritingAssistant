import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import store
from backend.app import app
from backend.archive import save_source_document
from backend.draft_media import ensure_media
from backend.pagination import paginate
from backend.research_temporal import classify


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    monkeypatch.delenv('APP_TOKEN',raising=False)
    with TestClient(app) as client:
        yield client


def article():
    a=store.create('https://example.com/news','原始新闻')
    a['sources']=[dict(title='模型发布：技术/细节?',url=a['url'],text='模型提供两种处理链路，需要保留输入采样率和测试环境。'*30,published_at='2026-09-10',retrieved_at=store.now(),images=[],videos=[])]
    a.update(title='原始新闻',body='开头😀。\n\n待插入位置。',summary='模型发布与技术条件',keywords=['AI'])
    return store.save(a,snapshot=True)


def test_title_migration_and_original_link(client):
    a=article();root=store.folder(a['id'])
    assert root.name=='模型发布：技术 细节'
    assert (store.DATA/'backups'/'title-migration'/a['id']/'article.json').exists()
    save_source_document(a['sources'][0],root/'source'/'原文')
    original=next((root/'source'/'原文').glob('*.md')).read_text(encoding='utf8')
    assert original.startswith('原文链接：https://example.com/news')
    a['title']='生成稿的新标题';store.save(a)
    assert store.folder(a['id'])==root and store.listing()[0]['id']==a['id']


def test_reference_dates_and_background():
    primary=dict(published_at='2026-09-10')
    candidate=dict(title='FLASepformer release',text='FLASepformer technical details',url='https://example.com/news',published_at='2026-09-13')
    assert classify(primary,candidate,['FLASepformer'])['accepted']
    candidate['published_at']='2026-09-14'
    assert not classify(primary,candidate,['FLASepformer'])['accepted']
    candidate['url']='https://arxiv.org/abs/2508.19528';candidate['published_at']='2025-08-20'
    assert classify(primary,candidate,['FLASepformer'])['kind']=='background'
    assert not classify(primary,candidate,['unrelated'])['accepted']


def test_manual_file_sync_and_gui_upload(client):
    a=article();root=store.folder(a['id'])
    image=io.BytesIO();Image.new('RGB',(600,400),'#426d59').save(image,'PNG')
    (root/'manual'/'images'/'直接复制.png').write_bytes(image.getvalue())
    response=client.post(f"/api/articles/{a['id']}/materials/sync").json()
    assert any(x['alt']=='直接复制' for x in response['assets'])
    text='原文链接：https://example.com/background\n\n这是一份用户补充的模型背景资料，核心信息需要融合并保留来源。'*5
    uploaded=client.post(f"/api/articles/{a['id']}/materials",files={'file':('背景资料.md',text.encode(),'text/markdown')})
    assert uploaded.status_code==200
    assert uploaded.json()['sources'][-1]['reference_role']['kind']=='manual'
    again=client.post(f"/api/articles/{a['id']}/materials/sync").json()
    assert len(again['sources'])==2


def test_reference_fusion_preserves_draft_and_revision(client,monkeypatch):
    a=article();route=f"/api/articles/{a['id']}"
    monkeypatch.setattr('backend.routes.references.complete',lambda *args:dict(text='模型的两条处理链路应区分输入采样率。[S1]'))
    payload=dict(selections=[dict(source_id=1,start=0,end=35)],position=4,revision=a['revision'])
    response=client.post(route+'/fuse',json=payload)
    assert response.status_code==200
    updated=response.json()
    assert updated['body'].startswith(a['body'][:4]) and updated['body'].endswith(a['body'][4:])
    assert updated['revision']==a['revision']+1 and updated['review'] is None
    assert client.post(route+'/fuse',json=payload).status_code==409


def test_draft_requires_real_local_visual_and_pagination(client):
    a=article();ensure_media(a)
    assert '![' in a['body'] and a['assets'][0]['approved']
    assert (store.folder(a['id'])/a['assets'][0]['path']).is_file()
    text='技术事实和条件。'*300
    pages=paginate('<p>'+text+'</p>')
    from bs4 import BeautifulSoup
    assert len(pages)>1 and ''.join(BeautifulSoup(p,'html.parser').get_text() for p in pages)==text
    assert client.get('/api/config').json()['research']['window_days']==3


def test_model_entity_spacing_and_chinese_boundaries():
    from backend.research_related import queries
    source=dict(title='Opus5.5逆向使命召唤',text='Claude Opus 5.5 performs reverse engineering')
    entities=queries(source)
    assert 'Opus5.5' in entities and 'Opus5' not in entities
    candidate=dict(title='Opus 5.5 reverse engineering',text='details',url='https://example.com/news',published_at='2026-10-12')
    assert classify(dict(published_at='2026-10-12'),candidate,entities)['accepted']


def test_transient_download_retry_and_no_retry_for_forbidden(monkeypatch):
    import httpx
    from backend import network
    calls=[]
    def request(*args):
        calls.append(1)
        if len(calls)==1:
            response=httpx.Response(504,request=httpx.Request('GET','https://example.com'))
            response.raise_for_status()
        return b'real bytes','image/png','https://example.com'
    monkeypatch.setattr(network,'_fetch',request)
    monkeypatch.setattr(network.time,'sleep',lambda _:None)
    assert network.fetch('https://example.com')[0]==b'real bytes' and len(calls)==2
    calls.clear()
    def forbidden(*args):
        calls.append(1)
        httpx.Response(403,request=httpx.Request('GET','https://example.com')).raise_for_status()
    monkeypatch.setattr(network,'_fetch',forbidden)
    with pytest.raises(httpx.HTTPStatusError):network.fetch('https://example.com')
    assert len(calls)==1


def test_short_card_paragraphs_combined_without_lost_text():
    from backend.card_layout import editorial_pages
    chunks=['这是一个完整的技术事实。'*5 for _ in range(8)]
    a=dict(title='模型',summary='摘要',body='\n\n'.join(chunks))
    pages=editorial_pages(a,[],dict(card_chars=240))
    assert len(pages)<len(chunks)+1
    assert ''.join(p['text'].replace('\n','') for p in pages[1:])==''.join(chunks)


def test_fusion_bad_citation_does_not_change_draft(client,monkeypatch):
    a=article();route=f"/api/articles/{a['id']}"
    monkeypatch.setattr('backend.routes.references.complete',lambda *args:dict(text='未经资料支持的结论 [S8]'))
    result=client.post(route+'/fuse',json=dict(selections=[dict(source_id=1,start=0,end=35)],position=0,revision=a['revision']))
    assert result.status_code==502 and store.read(a['id'])['body']==a['body']


def test_minimax_search_rejects_chemistry_h3():
    from backend.research_search import rank
    candidates=[dict(title='H3+ Between the Stars',url='https://arxiv.org/abs/astro-ph/0102038',provider='arxiv'),dict(title='MiniMax H3',url='https://www.minimax.io/blog/minimax-h3',provider='official')]
    assert [r['url'] for r in rank(candidates,'MiniMax H3',6)]==[candidates[1]['url']]


def test_fusion_retry_repairs_missing_citations():
    from backend.reference_fusion import synthesize
    answers=iter([dict(text='模型处理两条技术链路。'),dict(text='模型处理两条技术链路。[S1]')])
    result=synthesize([dict(source_id='S1',text='参考资料')],'简洁','','deepseek',completion=lambda *args:next(answers))
    assert result.endswith('[S1]')


def test_wechat_local_video_rejected_before_remote_call(monkeypatch):
    from backend.publishing import wechat_draft
    monkeypatch.setenv('WECHAT_APP_ID','test-id')
    monkeypatch.setenv('WECHAT_APP_SECRET','test-secret')
    a=dict(id='a'*32,assets=[],body='[视频：演示](/api/articles/'+'a'*32+'/assets/demo/file)')
    with pytest.raises(ValueError,match='本地视频上传'):
        wechat_draft(a,dict(wechat=dict(thumb_media_id='existing-cover')))
