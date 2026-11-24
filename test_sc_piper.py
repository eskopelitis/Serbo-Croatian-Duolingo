import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sc_piper


class PiperConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': self.tmp.name}, clear=False)
        self.env.start()
        self.old_model = os.environ.pop('SC_PIPER_MODEL', None)
        self.old_config = os.environ.pop('SC_PIPER_CONFIG', None)
        self.model = sc_piper.default_model_path()
        self.model.parent.mkdir(parents=True)
        self.config = Path(str(self.model) + '.json')
        self.model.write_bytes(b'reviewed model')
        self.config.write_bytes(b'reviewed config')
        self.model_hash = patch.object(sc_piper, '_MODEL_SHA256', hashlib.sha256(self.model.read_bytes()).hexdigest())
        self.config_hash = patch.object(sc_piper, '_CONFIG_SHA256', hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.model_hash.start()
        self.config_hash.start()
        sc_piper._verified_hash.cache_clear()

    def tearDown(self):
        sc_piper._verified_hash.cache_clear()
        self.model_hash.stop()
        self.config_hash.stop()
        if self.old_model is not None:
            os.environ['SC_PIPER_MODEL'] = self.old_model
        if self.old_config is not None:
            os.environ['SC_PIPER_CONFIG'] = self.old_config
        self.env.stop()
        self.tmp.cleanup()

    def test_default_model_is_verified_once_then_rechecked_when_changed(self):
        with patch('sc_piper.importlib.util.find_spec', return_value=object()), \
                patch.object(sc_piper, '_sha256', wraps=sc_piper._sha256) as sha:
            self.assertTrue(sc_piper.status()['available'])
            self.assertTrue(sc_piper.status()['available'])
            self.assertEqual(sha.call_count, 2)
            self.model.write_bytes(b'tampered model')
            result = sc_piper.status()
            self.assertFalse(result['available'])
            self.assertIn('does not match', result['reason'])
            self.assertEqual(sha.call_count, 3)

    def test_background_warmup_uses_local_voice_without_blocking_caller(self):
        with patch.object(sc_piper, 'synthesize', return_value=b'audio') as synth:
            worker = sc_piper.start_warmup()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            synth.assert_called_once_with('Dobar dan.')


if __name__ == '__main__':
    unittest.main()
