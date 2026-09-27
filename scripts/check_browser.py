"""Optional: pip install playwright; playwright install chromium; python scripts/check_browser.py"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root = Path(__file__).resolve().parents[1]
settings = dict(line.split('=',1) for line in (root/'.env').read_text().splitlines()
                if '=' in line and not line.startswith('#'))
with sync_playwright() as p:
    options = {'headless':True}
    if os.getenv('CHROME_EXECUTABLE'):
        options['executable_path'] = os.environ['CHROME_EXECUTABLE']
    browser = p.chromium.launch(**options)
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.goto('http://localhost:8080')
    page.locator('#token').fill(settings['ADMIN_TOKEN'])
    page.locator('#login button').click()
    expect(page.locator('#identity')).to_have_text('admin 연결됨')
    page.locator('#ingestion summary').click()
    page.locator('#document').set_input_files(root/'samples/handbook.md')
    page.locator('#upload button').click()
    expect(page.locator('#notice')).to_contain_text('반입 완료')
    page.locator('.document').filter(has_text='handbook.md').filter(has_text='승인 대기').first.locator('button').click()
    expect(page.locator('#notice')).to_contain_text('승인·색인 완료')
    page.locator('#ingestion summary').click()
    page.locator('#question').fill('ORBIT 프로젝트의 문서 승인 절차는?')
    page.locator('#send').click()
    expect(page.locator('#notice')).to_have_text('응답과 출처를 저장했습니다.',timeout=30000)
    expect(page.locator('.message.assistant')).to_contain_text('LLM 추론 아님')
    expect(page.locator('.sources summary')).to_be_visible()
    (root/'docs').mkdir(exist_ok=True)
    page.screenshot(path=str(root/'docs/runtime.png'),full_page=True)
    for width in [390,768,1440]:
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
    assert not errors,errors
    browser.close()
print('PASS: browser login, approval, RAG sources, SSE UI and responsive layout.')
