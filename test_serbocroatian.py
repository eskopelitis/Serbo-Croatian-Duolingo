"""Integration checks for the Serbo-Croatian course using disposable learner databases."""
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import db
import serbocroatian as sc
from flask import Flask

class CourseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'learner.sqlite3')
        app = Flask(__name__)
        sc.register(app)
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self.original
        self.tmp.cleanup()

    def test_fresh_course_starts_empty(self):
        result=self.client.get('/api/sc/course').get_json()
        self.assertEqual(result['settings'], {'variant':'cnr','script':'latin'})
        self.assertEqual(len(result['items']),len(sc.ROWS)+len(sc.TATOEBA))
        self.assertEqual(next(i for i in result['items'] if i['id']=='tatoeba-466190-373330')['source']['target_author'],'FeuDRenais')
        self.assertEqual(result['practiced_today'],0)
        self.assertTrue(all(item['progress']['attempts']==0 for item in result['items']))

    def test_variants_script_and_answers(self):
        for variant,expected in [('cnr','млијеко'),('sr','млеко'),('hr','млијеко'),('bs','млијеко')]:
            self.assertEqual(self.client.post('/api/sc/settings',json={'variant':variant,'script':'cyrillic'}).status_code,200)
            items=self.client.get('/api/sc/course').get_json()['items']
            self.assertEqual(next(i for i in items if i['id']=='milk')['target'],expected)
        response=self.client.post('/api/sc/answer',json={'id':'milk','direction':'to_target','answer':'млеко','attempt_id':'attempt-0001'})
        self.assertTrue(response.get_json()['correct'])
        self.assertTrue(response.get_json()['accepted_alternative'])
        self.assertEqual(self.client.post('/api/sc/answer',json={'id':'milk','direction':'to_target','answer':'wrong','attempt_id':'attempt-0001'}).get_json(),response.get_json())
        item=next(i for i in self.client.get('/api/sc/course').get_json()['items'] if i['id']=='milk')
        self.assertEqual(item['progress']['attempts'],1)
        self.assertEqual(self.client.get('/api/sc/course').get_json()['practiced_today'],1)
        wrong=self.client.post('/api/sc/answer',json={'id':'milk','direction':'to_target','answer':'mliko','attempt_id':'attempt-0002'}).get_json()
        self.assertFalse(wrong['correct'])
        self.assertEqual(sc.convert('Njegoš, ljubav i džez', 'cyrillic'),'Његош, љубав и џез')
        self.assertEqual(sc.convert('Његош, љубав и џез', 'latin'),'Njegoš, ljubav i džez')
        self.assertNotEqual(sc.normalized('caj'),sc.normalized('čaj'))

    def test_sourced_sentence_variants_keep_attribution_and_convert_scripts(self):
        for script in ('latin', 'cyrillic'):
            self.client.post('/api/sc/settings',json={'variant':'cnr','script':script})
            items=self.client.get('/api/sc/course').get_json()['items']
            sourced=[i for i in items if 'source' in i]
            self.assertEqual(len(sourced),13)
            self.assertEqual({i['source']['variant'] for i in sourced},{'sr','hr','bs'})
            self.assertTrue(all(i['source']['target_author'] and i['source']['english_author'] and
                                i['source']['target_id'] and i['source']['english_id'] and
                                i['source']['license']=='CC BY 2.0 FR' for i in sourced))
            sample=next(i for i in sourced if i['id']=='tatoeba-468745-392210')
            self.assertEqual(sample['target'], 'Šta je ovo?' if script=='latin' else 'Шта је ово?')

    def test_word_list_import_is_atomic(self):
        good = self.client.post('/api/sc/words/import',json={'text':'voda, water\n\u043a\u0443\u045b\u0430\thome','variant':'sr'})
        self.assertEqual(good.status_code,201)
        self.assertEqual(good.get_json()['imported'],2)
        bad = self.client.post('/api/sc/words/import',json={'text':'hvala, thanks\nmissing meaning','variant':'sr'})
        self.assertEqual(bad.status_code,400)
        custom=[item for item in self.client.get('/api/sc/course').get_json()['items'] if item['custom']]
        self.assertEqual(len(custom),2)
        self.assertEqual({i['target'] for i in custom},{'voda','ku\u0107a'})

    def test_beginner_teaching_and_self_check(self):
        course=self.client.get('/api/sc/course').get_json()
        self.assertEqual(len(course['teaching']['lessons']),8)
        self.assertEqual(len(course['teaching']['dialogues']),5)
        self.assertEqual(len(course['teaching']['questions']),16)
        self.assertNotIn('accepted_answers',course['teaching']['questions'][0])
        def submit(id_,value):
            return self.client.post('/api/sc/check/answer',json={'id':id_,'answer':value})
        self.assertTrue(submit('p01','a').get_json()['correct'])
        self.assertEqual(submit('p01','invalid').status_code,400)
        self.assertTrue(submit('p14','Не разумем!').get_json()['correct'])
        self.assertTrue(submit('p14','unknown wording').get_json()['may_self_assess'])
        self.assertEqual(submit('missing','a').status_code,404)
        self.assertEqual(self.client.get('/api/sc/course').get_json()['practiced_today'],0)

    def test_optional_tutor_validates_provider_and_keeps_progress_separate(self):
        valid={'reply':'Zdravo! Kako si?', 'english':'Hello! How are you?',
               'suggestion':'Dobro sam.', 'suggestion_english':'I am well.'}
        self.client.post('/api/sc/settings',json={'variant':'sr','script':'cyrillic'})
        with patch('llm._chat_json',return_value=valid) as model:
            response=self.client.post('/api/sc/tutor',json={'history':[{'role':'user','text':'Zdravo'}]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['reply'],'Здраво! Како си?')
        self.assertIn('Serbian',model.call_args.args[0])
        self.assertEqual(self.client.get('/api/sc/course').get_json()['practiced_today'],0)
        with patch('llm._chat_json',return_value={**valid,'reply':'Γεια'}):
            self.assertEqual(self.client.post('/api/sc/tutor',json={'history':[{'role':'user','text':'hello'}]}).status_code,503)
        self.assertEqual(self.client.post('/api/sc/tutor',json={'history':[{'role':'assistant','text':'hi'}]}).status_code,400)

    def test_optional_writing_feedback_is_checked_and_not_scored(self):
        with patch('llm._chat_json',return_value={'corrected':'Dobar dan!', 'explanation':'Use a capital letter.'}):
            response=self.client.post('/api/sc/writing',json={'text':'dobar dan'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['corrected'],'Dobar dan!')
        with patch('llm._chat_json',return_value={'corrected':'Γεια','explanation':'Hello'}):
            self.assertEqual(self.client.post('/api/sc/writing',json={'text':'zdravo'}).status_code,503)
        self.assertEqual(self.client.get('/api/sc/course').get_json()['practiced_today'],0)

    def test_source_extraction_requires_actual_source_phrases(self):
        with patch('llm._chat_json',return_value={'entries':[{'target':'voda','english':'water'}]}):
            result=self.client.post('/api/sc/extract',json={'text':'Molim, voda.'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.get_json()['entries'][0]['target'],'voda')
        with patch('llm._chat_json',return_value={'entries':[{'target':'čaj','english':'tea'}]}):
            self.assertEqual(self.client.post('/api/sc/extract',json={'text':'Molim, voda.'}).status_code,503)
        self.assertFalse(any(i['custom'] for i in self.client.get('/api/sc/course').get_json()['items']))

    def test_custom_words_persist_and_input_is_validated(self):
        for endpoint in ('settings','words','words/import','answer'):
            self.assertEqual(self.client.post('/api/sc/'+endpoint,json=['invalid']).status_code,400)
        self.assertEqual(self.client.post('/api/sc/settings',json={'variant':'el','script':'latin'}).status_code,400)
        self.assertEqual(self.client.post('/api/sc/words',json={'target':'','english':'x','variant':'sr'}).status_code,400)
        created=self.client.post('/api/sc/words',json={'target':'кућа','english':'home','variant':'sr','note':'from family'})
        self.assertEqual(created.status_code,201)
        item=next(i for i in self.client.get('/api/sc/course').get_json()['items'] if i['id']==created.get_json()['id'])
        self.assertEqual(item['target'],'kuća')
        self.assertTrue(self.client.post('/api/sc/answer',json={'id':item['id'],'direction':'to_target','answer':'кућа','attempt_id':'attempt-0003'}).get_json()['correct'])
        self.assertEqual(self.client.post('/api/sc/answer',json={'id':item['id'],'direction':'to_target','answer':'кућа','attempt_id':'bad'}).status_code,400)

    def test_optional_serbian_voice_endpoint_and_failures(self):
        with patch('sc_piper.status', return_value={'available': True, 'language': 'sr', 'voice': 'Marko'}):
            self.assertEqual(self.client.get('/api/sc/voice').get_json()['language'], 'sr')
        with patch('sc_piper.synthesize', return_value=b'RIFF-test-WAVE') as synth:
            response = self.client.post('/api/sc/tts', json={'text':'Добар дан'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'audio/wav')
        self.assertEqual(response.headers['X-Voice-Provider'], 'Serbian Marko (Piper)')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        synth.assert_called_once_with('Добар дан')
        with patch('sc_piper.synthesize', side_effect=sc.sc_piper.VoiceUnavailable('Not configured')):
            response = self.client.post('/api/sc/tts', json={'text':'Dobar dan'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error'], 'Not configured')
        with patch('sc_piper.synthesize', side_effect=sc.sc_piper.VoiceInputError('Invalid text')):
            self.assertEqual(self.client.post('/api/sc/tts', json={'text':''}).status_code, 400)

if __name__=='__main__': unittest.main()
