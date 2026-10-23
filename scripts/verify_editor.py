"""Browser integration check with a real previously generated draft; no extra model calls."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import store
from playwright.sync_api import sync_playwright

live_root = ROOT / 'test-results' / 'live-data' / 'articles'
source = next(live_root.glob('*/article.json'))
live = json.loads(source.read_text(encoding='utf-8'))
draft = store.create(live['url'], live['title'])
for field in ['body', 'summary', 'keywords', 'sources', 'review', 'revision']:
    draft[field] = live[field]
draft.update(status='Done', stage='真实接口验证完成（历史论文）')
store.save(draft, snapshot=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.goto('http://127.0.0.1:8000', wait_until='networkidle')
    page.locator(f'article[data-article="{draft["id"]}"]').click()
    page.locator('#draft-body').wait_for()
    original = page.locator('#draft-title').input_value()
    page.locator('#draft-title').fill(original + ' · 人工编辑')
    page.get_by_role('button', name='保存修改', exact=True).click()
    page.wait_for_function("document.querySelector('#toast').textContent.includes('修改已保存')")
    page.get_by_role('button', name='图文预览', exact=True).click()
    page.locator('.preview-prose h2').first.wait_for()
    assert page.locator('.preview-prose').inner_text()
    page.screenshot(path=str(ROOT / 'test-results' / 'editor-preview.png'), full_page=True)
    page.get_by_role('button', name='修订记录', exact=True).click()
    page.locator('.version').first.wait_for()
    page.get_by_role('button', name='文案编辑', exact=True).click()
    page.get_by_role('button', name='生成 3:4 组图', exact=False).click()
    page.locator('.asset-tile').first.wait_for()
    assert page.locator('.asset-tile').count() > 1
    page.screenshot(path=str(ROOT / 'test-results' / 'cards.png'), full_page=True)
    with page.expect_download() as download:
        page.get_by_role('button', name='下载图文包', exact=True).click()
    assert download.value.suggested_filename.endswith('.zip')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(ROOT / 'test-results' / 'mobile-editor.png'), full_page=True)
    assert not errors, errors
    # Remove only this run's newly created fixture; existing user articles remain intact.
    fixture = store.folder(draft['id']).resolve()
    assert fixture.parent == (store.DATA / 'articles').resolve()
    shutil.rmtree(fixture)
    print(json.dumps({'editor_save': 'passed', 'preview': 'passed', 'versions': 'passed',
                      'cards': 'passed', 'download': 'passed', 'mobile': 'passed', 'errors': errors}))
    browser.close()
