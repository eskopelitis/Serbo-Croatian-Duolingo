"""Exercise the spoken conversation screen using fake audio and model providers."""
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

with tempfile.TemporaryDirectory(prefix='sc-talk-', ignore_cleanup_errors=True) as folder:
    import db
    db.DB_PATH=os.path.join(folder,'talk.sqlite3')
    import app, llm, stt
    def fake_model(prompt, **kwargs):
        if 'Grade only' in prompt:
            return {'score':82,'strengths':['You introduced yourself.'],'fixes':['Ask a question next.']}
        return {'reply':'Kako si?', 'translation':'How are you?',
                'suggestions':[{'target':'Dobro sam','english':'I am well'},
                               {'target':'Umoran sam','english':'I am tired'}], 'correction':None}
    llm._chat_json=fake_model
    stt.available=lambda:True
    stt.transcribe=lambda *args, **kwargs:'Dobro sam'
    server=make_server('127.0.0.1',0,app.app,threaded=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True,
            args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
        for width in (1280,375):
            page=browser.new_page(viewport={'width':width,'height':900}, permissions=['microphone'])
            page.goto(f'http://127.0.0.1:{server.server_port}/#today')
            page.get_by_role('link',name='Talk out loud Have a conversation and get feedback.').click()
            page.get_by_role('button',name='Start conversation').click()
            page.get_by_text('How are you?').wait_for()
            assert page.get_by_text('I am well').is_visible()
            page.get_by_role('button',name='Speak your reply').click()
            page.get_by_role('button',name='Stop recording').wait_for()
            page.wait_for_timeout(800)
            page.get_by_role('button',name='Stop recording').click()
            page.get_by_text('Check the transcription before sending.').wait_for()
            assert page.locator('#talk-text').input_value() == 'Dobro sam'
            page.get_by_role('button',name='Send reply').click()
            page.get_by_text('Your turn.').wait_for()
            page.get_by_role('button',name='Finish and score').click()
            page.get_by_text('82 / 100').wait_for()
            assert page.get_by_text('Ask a question next.').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.close()
        browser.close()
    server.shutdown()
print('Spoken conversation, example replies and grading passed at desktop and mobile widths.')
