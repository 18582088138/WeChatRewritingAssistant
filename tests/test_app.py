import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import agents, store, workflow
from backend.app import app
from backend.network import validate_url
from backend.render import export_zip, html


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    monkeypatch.delenv('APP_TOKEN', raising=False)
    with TestClient(app) as client:
        yield client


def article():
    a = store.create('https://example.com/source', '模型发布解读')
    a['sources'] = [dict(title='原始发布', url=a['url'], text='新的模型发布，支持工具调用，评测方式需确认。' * 30,
                         retrieved_at=store.now(), images=[], videos=[])]
    a['body'] = '## 发生了什么\n\n这是有来源的行业分析。[S1]\n\n## 如何理解\n\n需要区分公开评测与实际体验。' * 4
    a['summary'] = '一篇有来源的模型解读。'
    a['keywords'] = ['AI', '模型']
    return store.save(a)


def test_generation_review_versions(client, monkeypatch):
    a = article()
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only')
    responses = iter([
        dict(title='新模型值得关注的变化', body=a['body'], summary=a['summary'], keywords=a['keywords']),
        dict(score=87, verdict='建议人工确认后使用', issues=[], strengths=['有来源'],
             fact_checks=[dict(claim='发布模型', source_id='S1', status='supported', reason='来源描述')]),
    ])
    monkeypatch.setattr(agents, 'complete', lambda *args, **kwargs: next(responses))
    result = client.post(f'/api/articles/{a["id"]}/generate', json={'research': False})
    assert result.status_code == 202
    saved = client.get(f'/api/articles/{a["id"]}').json()
    assert saved['status'] == 'Done' and saved['review']['score'] == 87
    assert saved['review']['draft_revision'] == saved['revision'] == 1
    assert len(client.get(f'/api/articles/{a["id"]}/versions').json()) == 2
    assert (store.folder(a['id']) / 'draft.md').read_text(encoding='utf-8') == saved['body']


def test_paragraph_edit_conflict_and_review_reset(client, monkeypatch):
    a = article()
    a['body'] = '开头😀。需要改写的段落。[S1]后面的正文。'
    a['review'] = {'score': 90}
    store.save(a)
    monkeypatch.setattr(agents.RewritingAgent, 'paragraph', lambda *args: '更自然的段落。[S1]')
    start = a['body'].index('需要')
    end = a['body'].index('后面')
    url = f'/api/articles/{a["id"]}/paragraph'
    response = client.post(url, json={'start': start, 'end': end, 'revision': 0})
    assert response.status_code == 200
    updated = response.json()
    assert updated['body'] == '开头😀。更自然的段落。[S1]后面的正文。'
    assert updated['review'] is None
    assert client.post(url, json={'start': start, 'end': end, 'revision': 0}).status_code == 409
    assert client.patch(f'/api/articles/{a["id"]}', json=dict(title='过期', body='xx', summary='', keywords=[], revision=0)).status_code == 409


def test_private_urls_rejected(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *args: [(2, 1, 6, '', ('127.0.0.1', 80))])
    with pytest.raises(ValueError):
        validate_url('http://localhost/')
    with pytest.raises(ValueError):
        validate_url('file:///etc/passwd')


def test_auth_and_html_sanitization(client, monkeypatch):
    monkeypatch.setenv('APP_TOKEN', 'session-secret')
    assert client.get('/api/articles').status_code == 401
    assert client.get('/api/articles', headers={'Authorization': 'Bearer session-secret'}).status_code == 200
    assert client.get('/api/health').json()['ok']
    rendered = html('<img src="x" onerror="alert(1)"><script>alert(1)</script>\n\n[click](javascript:alert(1))')
    assert '<script' not in rendered and 'onerror' not in rendered and 'javascript:' not in rendered


def test_upload_approve_cards_export_and_draft_boundary(client, monkeypatch):
    a = article()
    stream = io.BytesIO()
    Image.new('RGB', (500, 400), '#eeeeee').save(stream, 'PNG')
    uploaded = client.post(f'/api/articles/{a["id"]}/assets', files={'file': ('test.png', stream.getvalue(), 'image/png')}).json()
    asset = uploaded['assets'][0]
    assert not asset['approved']
    approved = client.patch(f'/api/articles/{a["id"]}/assets/{asset["id"]}', json={'approved': True, 'alt': '示例配图'}).json()
    assert approved['assets'][0]['watermark'] == 'manually_checked'
    generated = client.post(f'/api/articles/{a["id"]}/cards').json()
    assert len(generated['assets']) > 1
    assert generated['assets'][-1]['width'] == 1080
    blob = client.get(f'/api/articles/{a["id"]}/export/xiaohongshu')
    assert blob.status_code == 200
    with zipfile.ZipFile(io.BytesIO(blob.content)) as archive:
        assert {'caption.txt', 'preview.html', 'draft.md'}.issubset(archive.namelist())
        assert any(name.endswith('.png') for name in archive.namelist())
    monkeypatch.delenv('WECHAT_APP_ID', raising=False)
    result = client.post(f'/api/articles/{a["id"]}/deliver', json={'platforms': ['wechat', 'x', 'xiaohongshu', 'weibo']}).json()
    assert result[0]['status'] == 'failed'
    assert all(r['status'] == 'export_ready' for r in result[1:])


def test_failed_agent_leaves_recoverable_draft(client, monkeypatch):
    a = article()
    opts = dict(research=False, provider='deepseek', platform='wechat', word_count=1200)
    monkeypatch.setattr(agents.RewritingAgent, 'run', lambda *args: (_ for _ in ()).throw(ValueError('模型请求失败')))
    workflow.run(a['id'], opts)
    saved = store.read(a['id'])
    assert saved['body'] == a['body']
    assert saved['status'] == 'Done' and saved['error'] == '模型请求失败'


def test_review_flags_unverifiable_sources(client, monkeypatch):
    a = article()
    a['body'] = '未提供出处的结论。' * 30
    monkeypatch.setattr(agents, 'complete', lambda *args: dict(score=99, verdict='很好', issues=[], strengths=[], fact_checks=[]))
    review = agents.ReviewAgent().run(a, {'provider': 'deepseek', 'platform': 'wechat'})
    assert review['score'] <= 59 and review['issues'][-1]['severity'] == 'high'
