"""Spoken conversation contracts with isolated progress and stubbed providers."""
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
import db
import llm
import serbocroatian as sc
import stt


class ConversationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'talk.sqlite3')
        app = Flask(__name__)
        sc.register(app)
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def test_turn_suggestions_script_and_grade(self):
        self.client.post('/api/sc/settings', json={'variant':'sr','script':'cyrillic'})
        turn = {'reply':'Kako si?', 'translation':'How are you?',
                'suggestions':[{'target':'Dobro sam','english':'I am well'}], 'correction':None}
        with patch.object(llm, '_chat_json', return_value=turn):
            response = self.client.post('/api/sc/talk/turn', json={'history':[]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['reply'], 'Како си?')
        self.assertEqual(response.json['suggestions'][0]['target'], 'Добро сам')
        history=[{'role':'assistant','text':response.json['reply']},{'role':'user','text':'Добро сам'}]
        with patch.object(llm, '_chat_json', return_value={'score':82,'strengths':['Good greeting'], 'fixes':['Try a follow-up question']}):
            grade=self.client.post('/api/sc/talk/grade',json={'history':history})
        self.assertEqual(grade.json['score'], 82)
        self.assertEqual(grade.json['fixes'], ['Try a follow-up question'])
        self.assertEqual(self.client.post('/api/sc/talk/grade',json={'history':history[:1]}).status_code,400)

    def test_provider_and_transcription_failures_are_recoverable(self):
        with patch.object(llm, '_chat_json', side_effect=RuntimeError('provider detail')):
            response=self.client.post('/api/sc/talk/turn',json={'history':[]})
        self.assertEqual(response.status_code,503)
        self.assertNotIn('provider detail',response.get_data(as_text=True))
        with patch.object(stt, 'available', return_value=False):
            response=self.client.post('/api/sc/talk/transcribe',data={'audio':(io.BytesIO(b'wav'),'speech.wav')})
        self.assertEqual(response.status_code,503)
        self.assertIn('type',response.get_data(as_text=True))
        self.client.post('/api/sc/settings',json={'variant':'hr','script':'latin'})
        with patch.object(stt, 'available', return_value=True), patch.object(stt,'transcribe',return_value='Dobar dan') as transcribe:
            response=self.client.post('/api/sc/talk/transcribe',data={'audio':(io.BytesIO(b'wav'),'speech.wav')})
        self.assertEqual(response.json['text'],'Dobar dan')
        self.assertEqual(transcribe.call_args.kwargs['language'],'hr')


if __name__ == '__main__':
    unittest.main()
