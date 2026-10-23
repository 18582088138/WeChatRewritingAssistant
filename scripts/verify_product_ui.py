"""Local product acceptance: real reference synthesis, folder imports and mobile pages."""
import json
import os
import shutil
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
OUTPUT=ROOT/'test-results/product-ui';OUTPUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:8000'
token=os.getenv('APP_TOKEN','')
client=httpx.Client(base_url=BASE,trust_env=False,timeout=180,headers={'Authorization':'Bearer '+token} if token else {})

def call(method,path,**kwargs):
    response=client.request(method,path,**kwargs);response.raise_for_status();return response.json()

def main():
    originals=call('GET','/api/articles')
    original=next(a for a in originals if a['id']=='6de439746fc54eeb9a9e4aa2c45c745c')
    source=original['sources'][0]
    created=call('POST','/api/articles',json=dict(url=source['url'],title='本地实测·资料融合',text=source['text']))
    route='/api/articles/'+created['id']
    created=call('PATCH',route,json=dict(title='本地实测·资料融合',body=original['body'],summary=original['summary'],keywords=original['keywords'],revision=created['revision']))
    detail=call('GET',route);root=Path(detail['storage_path'])
    source_root=Path(call('GET','/api/articles/'+original['id'])['storage_path'])
    image=next(a for a in original['assets'] if a['type']=='image' and not a['id'].startswith('card-'))
    shutil.copyfile(source_root/image['path'],root/'manual'/'images'/'参考截图.jpg')
    video=next(a for a in original['assets'] if a['type']=='video')
    shutil.copyfile(source_root/video['path'],root/'manual'/'videos'/'参考演示.mp4')
    supplement=original['sources'][1]['text']
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport=dict(width=1440,height=1000))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script('sessionStorage.setItem("signal.token", '+repr(token)+')')
        page.goto(BASE+'/#article/'+created['id'],wait_until='networkidle')
        page.locator('#draft-body').wait_for()
        page.locator('#draft-body').evaluate('el=>{el.focus();el.setSelectionRange(0,0)}')
        page.locator('#open-references').click()
        with page.expect_response(lambda r: r.url.endswith('/materials/sync')):
            page.locator('#sync-materials').click()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('同步完成')")
        with page.expect_response(lambda r: r.url.endswith('/materials')) as uploaded:
            page.locator('#reference-upload').set_input_files(dict(name='官方参考.md',mimeType='text/markdown',buffer=supplement.encode()))
        assert uploaded.value.ok, uploaded.value.text()
        page.wait_for_function('document.querySelectorAll("#reference-source option").length === 2')
        for index in ['0','1']:
            page.locator('#reference-source').select_option(index)
            page.locator('#reference-text').evaluate('el=>{el.focus();el.setSelectionRange(260,580)}')
            page.locator('#add-selection').click()
        assert page.locator('.reference-basket p').count()==2
        page.screenshot(path=str(OUTPUT/'references-desktop.png'),full_page=True)
        before=call('GET',route)
        with page.expect_response(lambda r: r.url.endswith('/fuse'), timeout=240000) as fused:
            page.locator('#fuse-selections').click()
        assert fused.value.ok, fused.value.text()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('融合插入')",timeout=10000)
        after=call('GET',route)
        assert after['revision']>before['revision'] and after['body'].endswith(before['body'])
        page.locator('#draft-body').evaluate('el=>{el.focus();el.setSelectionRange(0,0)}')
        page.locator('#open-references').click()
        page.locator('[data-reference-kind=image]').click()
        page.locator('[data-reference-media]').first.click()
        page.locator('#save-draft').click()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('修改已保存')")
        page.locator('#draft-body').evaluate('el=>{el.focus();el.setSelectionRange(0,0)}')
        page.locator('#open-references').click()
        page.locator('[data-reference-kind=video]').click()
        page.wait_for_function("document.querySelector('#references-dialog video').readyState>=1")
        page.locator('[data-reference-media]').first.click()
        page.locator('#save-draft').click()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('修改已保存')")
        page.locator('[data-editor-tab=preview]').click()
        page.locator('.preview-prose img').wait_for()
        page.wait_for_function("document.querySelector('.preview-prose img').naturalWidth>0")
        page.wait_for_function("document.querySelector('.preview-prose video').readyState>=1")
        page.screenshot(path=str(OUTPUT/'preview-desktop.png'),full_page=True)
        first=page.locator('.preview-prose').inner_text();page.locator('#preview-next').click()
        assert page.locator('.preview-prose').inner_text()!=first
        page.set_viewport_size(dict(width=390,height=844))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUTPUT/'preview-mobile.png'),full_page=True)
        page.locator('[data-editor-tab=edit]').click()
        page.locator('#open-references').click()
        assert not page.locator('.desktop-fusion').is_visible()
        page.locator('#close-references').click()
        page.set_viewport_size(dict(width=1440,height=1000))
        page.locator('#make-cards').click()
        page.wait_for_function("document.querySelector('#toast').textContent.includes('组图已生成')",timeout=60000)
        assert page.locator('.asset-grid .asset-tile').count()<=6
        assert not errors,errors
        browser.close()
    saved=call('GET',route)
    report=dict(status='passed',article_id=created['id'],archive=str(root),real_llm_fusion=True,manual_copy=True,gui_upload=True,video_insert_and_play=True,preview_pagination=True,mobile_fusion_hidden=True,cards=len([a for a in saved['assets'] if a['id'].startswith('card-')]),console_errors=errors)
    (OUTPUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    client.close()

if __name__=='__main__':main()
