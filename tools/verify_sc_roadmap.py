"""Exercise the Serbo-Croatian roadmap in installed Edge with isolated progress.

Requires the optional Python playwright package; no browser download is needed.
"""
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

with tempfile.TemporaryDirectory(prefix='sc-roadmap-', ignore_cleanup_errors=True) as folder:
    import db
    db.DB_PATH = str(Path(folder) / 'learner.sqlite3')
    import app
    server = make_server('127.0.0.1', 0, app.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    lessons = json.loads((ROOT / 'data/sc_lesson_bank_v1.json').read_text(encoding='utf-8'))['lessons']
    assert len(lessons) > 30, 'Expected the newly authored lessons.'
    client = app.app.test_client()
    client.get('/api/sc/course')
    # Reach the first newly authored lesson through the same answer endpoint.
    for lesson in lessons[:30]:
        for n, exercise in enumerate(lesson['exercises']):
            response = client.post('/api/sc/lessons/answer', json={
                'lesson_id':lesson['id'], 'exercise_id':exercise['id'],
                'answer':exercise['accepted_answers'][0], 'attempt_id':f"seed-{lesson['order']:02d}-{n:04d}"
            })
            assert response.status_code == 200 and response.get_json()['correct'], response.get_data(as_text=True)
    new_lesson = lessons[30]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
        for width in (1280, 375):
            page = browser.new_page(viewport={'width':width, 'height':900}, device_scale_factor=1)
            page.goto(f'http://127.0.0.1:{server.server_port}/#lessons')
            page.get_by_role('heading', name='Your lesson roadmap.').wait_for()
            assert page.locator('.roadmap-unit').count() > 0
            assert page.locator('.roadmap-lesson').count() == len(lessons)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            lesson_link = page.locator(f'.roadmap-lesson a[href="#lesson/{new_lesson["id"]}"]')
            lesson_link.focus()
            page.keyboard.press('Enter')
            page.locator('#lesson-answer').wait_for()
            for exercise in new_lesson['exercises']:
                answer = exercise['accepted_answers'][0]
                if exercise['kind'] == 'choice':
                    page.locator(f'#lesson-answer input[value="{answer}"]').check()
                else:
                    page.locator('#lesson-answer input[name="answer"]').fill(answer)
                page.locator('#lesson-submit').click()
                page.locator('#lesson-next').wait_for()
                assert 'right' in page.locator('#lesson-feedback').inner_text().lower()
                page.locator('#lesson-next').click()
            page.get_by_text('See your next suggestion').click()
            page.get_by_role('heading', name='Your lesson roadmap.').wait_for()
            assert page.locator(f'.roadmap-lesson a[href="#lesson/{new_lesson["id"]}"]').get_attribute('aria-label').startswith('Review')
            page.goto(f'http://127.0.0.1:{server.server_port}/#vocabulary')
            page.locator('.vocabulary-entry').first.wait_for()
            first = page.locator('.vocabulary-entry').first.inner_text()
            assert 'biti · to be' in first, first
            assert 'Used to connect' not in first and 'Wiktionary contributors' not in first
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.close()
        browser.close()
    server.shutdown()
print('Roadmap, keyboard launch, new lesson completion/return and vocabulary verified in Edge at desktop and mobile widths.')
