"""Browser checks for setup using a temporary database, fake key, and mocked downloads."""
import os
from pathlib import Path
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

with tempfile.TemporaryDirectory(prefix='sc-setup-',ignore_cleanup_errors=True) as folder:
    import db, setup_support, llm, stt, sc_piper
    db.DB_PATH=os.path.join(folder,'practice.sqlite3')
    setup_support._config_dir=lambda:Path(folder)/'private'
    os.environ['DEEPSEEK_API_KEY']=''
    llm._local_model_id=lambda:None
    llm._chat_json=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('offline'))
    stt.available=lambda:False
    voice={'ready':False,'attempt':0}
    sc_piper.status=lambda:{'available':voice['ready']}
    def fake_install():
        voice['attempt']+=1
        voice['ready']=voice['attempt']>1
        with setup_support._job_lock:
            setup_support._job='done' if voice['ready'] else 'failed'
    setup_support._install_worker=fake_install
    import app
    server=make_server('127.0.0.1',0,app.app,threaded=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
        for width in (1280,375):
            os.environ['DEEPSEEK_API_KEY']=''
            voice.update(ready=False,attempt=0);setup_support._job='idle'
            page=browser.new_page(viewport={'width':width,'height':800})
            page.goto(f'http://127.0.0.1:{server.server_port}/#talk')
            page.get_by_role('button',name='Start conversation').click()
            page.get_by_role('dialog').wait_for()
            page.get_by_text('Needs setup').wait_for()
            page.keyboard.press('Tab')
            assert page.evaluate('document.querySelector("dialog").contains(document.activeElement)')
            page.keyboard.press('Shift+Tab')
            assert page.evaluate('document.querySelector("dialog").contains(document.activeElement)')
            assert page.get_by_text('You can always type instead.').count()
            assert page.evaluate('document.querySelector("dialog").getBoundingClientRect().right <= innerWidth')
            page.keyboard.press('Escape')
            assert not page.get_by_role('dialog').is_visible()
            page.goto(f'http://127.0.0.1:{server.server_port}/#settings')
            page.get_by_role('button',name='Open setup').click()
            field=page.locator('#setup-key');field.fill('fake-key-for-testing-only')
            page.get_by_role('button',name='Save key').click()
            page.get_by_text('Key saved. Retry your AI feature when ready.').wait_for()
            assert page.locator('#setup-key').input_value()==''
            assert 'fake-key-for-testing-only' not in page.locator('body').inner_text()
            assert page.evaluate("!JSON.stringify(localStorage).includes('fake-key-for-testing-only') && !JSON.stringify(sessionStorage).includes('fake-key-for-testing-only')")
            page.get_by_role('button',name='Download Serbian voice').click()
            page.get_by_role('button',name='Retry voice download').wait_for(timeout=10000)
            page.get_by_role('button',name='Retry voice download').click()
            page.get_by_text('Marko is installed on this computer.').wait_for(timeout=10000)
            page.get_by_role('button',name='Continue without setup').click()
            page.close()
        browser.close()
    server.shutdown()
print('Setup first use, key save, voice retry, Escape and desktop/mobile layouts passed.')
