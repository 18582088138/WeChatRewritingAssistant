"""Optional browser check: pip install playwright; start the backend first."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'test-results'
OUTPUT.mkdir(exist_ok=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:8000', wait_until='networkidle')
    page.get_by_role('heading', name='文章工作台', exact=True).wait_for()
    page.get_by_role('button', name='查看界面示例').click()
    assert page.locator('.article-card').count() == 3
    page.screenshot(path=str(OUTPUT / 'desktop.png'), full_page=True)
    page.get_by_role('button', name='处理中', exact=False).click()
    assert page.locator('.article-card').count() == 1
    page.get_by_role('button', name='退出示例').click()
    page.get_by_role('button', name='设置与连接').click()
    page.get_by_role('heading', name='设置与连接', exact=True).wait_for()
    assert page.locator('#connection-form input[name=api]').input_value() == 'http://127.0.0.1:8000'
    page.screenshot(path=str(OUTPUT / 'settings.png'), full_page=True)
    mobile = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=1)
    phone = mobile.new_page()
    phone.on('pageerror', lambda error: errors.append(str(error)))
    phone.goto('http://127.0.0.1:8000', wait_until='networkidle')
    phone.get_by_role('button', name='查看界面示例').click()
    assert phone.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    phone.screenshot(path=str(OUTPUT / 'mobile.png'), full_page=True)
    phone.get_by_role('button', name='打开导航').click()
    phone.get_by_role('button', name='设置与连接').click()
    phone.get_by_role('heading', name='设置与连接', exact=True).wait_for()
    assert phone.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors, errors
    print(json.dumps({'desktop': 'passed', 'mobile': 'passed', 'console_errors': errors, 'screenshots': str(OUTPUT)}))
    browser.close()
