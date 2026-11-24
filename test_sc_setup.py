import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
import llm
import setup_support as setup


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.config = patch.object(setup, '_config_dir', return_value=Path(self.tmp.name) / 'settings')
        self.config.start()
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop('DEEPSEEK_API_KEY', None)
        self.old_client, self.old_model = llm._client, llm.MODEL
        app = Flask(__name__)
        setup.register(app)
        self.client = app.test_client()
        self.headers = {'Origin': 'http://localhost', 'X-Local-Setup': '1'}

    def tearDown(self):
        llm._client, llm.MODEL = self.old_client, self.old_model
        self.env.stop()
        self.config.stop()
        self.tmp.cleanup()

    def test_untrusted_origins_and_hosts_cannot_read_or_write(self):
        for headers, base, remote in [
            ({'Origin':'https://evil.example','X-Local-Setup':'1'}, 'http://localhost', '127.0.0.1'),
            ({'Origin':'http://localhost'}, 'http://localhost', '127.0.0.1'),
            ({'Origin':'http://evil.example','X-Local-Setup':'1'}, 'http://evil.example', '127.0.0.1'),
            ({'Origin':'http://localhost','X-Local-Setup':'1'}, 'http://localhost', '192.0.2.1'),
        ]:
            for route in ('status','key','voice'):
                r=self.client.post('/api/setup/'+route,base_url=base,headers=headers,
                                   environ_base={'REMOTE_ADDR':remote},json={'key':'fake-key-for-testing-only'})
                self.assertEqual(r.status_code,403)
        self.assertFalse((Path(self.tmp.name)/'settings').exists())

    def test_save_update_and_status_do_not_return_credential(self):
        first='fake-key-for-testing-only'
        second='another-fake-key-for-testing-only'
        with patch.object(llm,'_local_model_id',return_value=None), patch.object(setup.stt,'available',return_value=False), patch.object(setup.sc_piper,'status',return_value={'available':False}):
            status=self.client.post('/api/setup/status',headers=self.headers,json={})
            self.assertFalse(status.json['ai_configured'])
            self.assertEqual(status.headers['Cache-Control'],'no-store')
            self.assertEqual(self.client.post('/api/setup/key',headers=self.headers,json={'key':'bad'}).status_code,400)
            for key in (first,second):
                result=self.client.post('/api/setup/key',headers=self.headers,json={'key':key})
                self.assertEqual(result.status_code,200)
                self.assertNotIn(key,result.get_data(as_text=True))
            status=self.client.post('/api/setup/status',headers=self.headers,json={})
            self.assertTrue(status.json['ai_configured'])
            self.assertNotIn(second,status.get_data(as_text=True))
            os.environ.pop('DEEPSEEK_API_KEY')
            setup.load_saved_key()
            self.assertEqual(os.environ['DEEPSEEK_API_KEY'],second)
            if os.name=='nt':
                self.assertNotIn(second.encode(),(Path(self.tmp.name)/'settings'/'ai-credential.bin').read_bytes())

    def test_failed_update_preserves_existing_key_and_client(self):
        os.environ['DEEPSEEK_API_KEY']='original-fake-key-only'
        llm._client=object()
        original=llm._client
        with patch.object(setup,'_save_key',side_effect=OSError('storage error')):
            r=self.client.post('/api/setup/key',headers=self.headers,json={'key':'replacement-fake-key'})
        self.assertEqual(r.status_code,503)
        self.assertEqual(os.environ['DEEPSEEK_API_KEY'],'original-fake-key-only')
        self.assertIs(llm._client,original)
        self.assertNotIn('replacement-fake-key',r.get_data(as_text=True))

    def test_custom_voice_configuration_cannot_start_default_install(self):
        with patch.dict(os.environ,{'SC_PIPER_MODEL':'custom-model'}):
            response=self.client.post('/api/setup/voice',headers=self.headers,json={})
        self.assertEqual(response.status_code,400)

    def test_running_install_reports_download_progress(self):
        folder = Path(self.tmp.name) / 'voices'
        folder.mkdir()
        (folder / '.marko-partial').write_bytes(b'x' * 40)
        (folder / 'unrelated.txt').write_bytes(b'x' * 50)
        with patch.object(setup.sc_piper, 'default_model_path', return_value=folder / 'sr_Marko_medium.onnx'), \
                patch.object(setup, '_VOICE_BYTES', 100), patch.object(setup, '_job', 'running'), \
                patch.object(llm, '_local_model_id', return_value=None):
            response = self.client.post('/api/setup/status', base_url='http://localhost',
                                        headers=self.headers, environ_base={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.get_json()['progress'], 40)


if __name__ == '__main__':
    unittest.main()
