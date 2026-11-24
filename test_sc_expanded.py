"""Expanded reference and adaptive-path checks with isolated learner state."""
import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
import db
import serbocroatian as sc
from sc_recommendations import recommend


class ExpandedCourseTest(unittest.TestCase):
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

    def test_today_activity_counts_saved_course_answers_and_preserves_prior_state(self):
        before = self.client.get('/api/sc/course').get_json()
        self.assertEqual(before['activity']['streak_days'], 0)
        self.assertEqual(len(before['activity']['chain']), 28)
        self.client.post('/api/sc/answer', json={'id':'milk', 'direction':'to_target',
                         'answer':'wrong', 'attempt_id':'activity-001'})
        lesson = {'id':'one', 'order':1, 'title':'First', 'prerequisites':[], 'examples':[],
                  'exercises':[{'id':'a', 'kind':'short_text', 'prompt':'Reply',
                                'accepted_answers':['hello'], 'feedback':'Hello.', 'tags':[]}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            self.client.post('/api/sc/lessons/answer', json={'lesson_id':'one', 'exercise_id':'a',
                             'answer':'hello', 'attempt_id':'activity-002'})
            after = self.client.get('/api/sc/course').get_json()
        self.assertTrue(after['activity']['chain'][-1])
        self.assertEqual(after['activity']['streak_days'], 1)
        self.assertEqual(after['activity']['lesson_answers_today'], 1)
        self.assertEqual(after['practiced_today'], 1)
        self.assertEqual(next(i for i in after['items'] if i['id']=='milk')['progress']['attempts'], 1)

    def test_vocabulary_search_pagination_and_script(self):
        page = self.client.get('/api/sc/vocabulary').get_json()
        self.assertEqual(page['inventory_total'], 2000)
        self.assertEqual(len(page['entries']), 30)
        self.assertEqual(page['entries'][0]['rank'], 1)
        self.assertEqual(self.client.get('/api/sc/vocabulary?offset=1980').get_json()['entries'][-1]['rank'], 2000)
        self.assertEqual(self.client.get('/api/sc/vocabulary?offset=-1').status_code, 400)
        self.client.post('/api/sc/settings', json={'variant':'sr', 'script':'cyrillic'})
        found = self.client.get('/api/sc/vocabulary?q=бити').get_json()
        self.assertEqual(found['entries'][0]['target'], 'бити')
        self.assertTrue(found['entries'][0]['senses'][0]['source_url'].startswith('https://en.wiktionary.org/'))
        self.assertGreater(self.client.get('/api/sc/vocabulary?q=water').get_json()['total'], 0)

    def test_recommendation_reacts_to_answers_and_respects_prerequisites(self):
        lessons = [
            {'id':'one', 'order':1, 'prerequisites':[], 'skills':['greetings'],
             'exercises':[{'id':'a'}, {'id':'b'}]},
            {'id':'two', 'order':2, 'prerequisites':['one'], 'skills':['questions'],
             'exercises':[{'id':'c'}]},
        ]
        def answer(exercise, correct):
            return {'lesson_id':'one', 'exercise_id':exercise, 'correct':correct,
                    'skills':['greetings'], 'vocabulary':[]}
        self.assertEqual(recommend(lessons, [])['lesson_id'], 'one')
        missed = [answer('a', False), answer('b', True)]
        self.assertEqual(recommend(lessons, missed)['lesson_id'], 'one')
        self.assertEqual(recommend(lessons, missed)['kind'], 'review')
        self.assertEqual(recommend(lessons, missed + [answer('a', True)])['lesson_id'], 'two')
        self.assertEqual(recommend(lessons, missed + [answer('a', True), answer('b', False)])['lesson_id'], 'one')

    def test_authored_lesson_answers_persist_and_unlock(self):
        lesson = {'id':'one', 'order':1, 'level':'A0', 'title':'Hello', 'objective':'Greet',
                  'teaching_note':'A greeting.', 'prerequisites':[], 'skill_tags':['greeting'],
                  'examples':[{'target':'Dobar dan', 'english':'Good day'}],
                  'exercises':[{'id':'a', 'kind':'short_text', 'prompt':'Say hello',
                                'accepted_answers':['Dobar dan'], 'feedback':'A greeting.', 'tags':['greeting']}]}
        next_lesson = {**lesson, 'id':'two', 'order':2, 'prerequisites':['one'],
                       'exercises':[{**lesson['exercises'][0], 'id':'b'}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson, next_lesson]):
            fresh = self.client.get('/api/sc/course').get_json()
            self.assertEqual(fresh['recommendation']['lesson_id'], 'one')
            self.assertEqual(self.client.get('/api/sc/lessons/two').status_code, 400)
            public = self.client.get('/api/sc/lessons/one').get_json()['lesson']
            self.assertNotIn('accepted_answers', public['exercises'][0])
            def answer(value, attempt):
                return self.client.post('/api/sc/lessons/answer', json={'lesson_id':'one','exercise_id':'a',
                    'answer':value, 'attempt_id':attempt}).get_json()
            self.assertFalse(answer('wrong', 'attempt-001')['correct'])
            self.assertFalse(answer('Dobar dan', 'attempt-001')['correct'])
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['kind'], 'review')
            self.assertTrue(answer('Добар дан', 'attempt-002')['correct'])
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['lesson_id'], 'two')
            self.assertEqual(self.client.get('/api/sc/lessons/two').status_code, 200)
            self.assertEqual(self.client.get('/api/sc/course').get_json()['practiced_today'], 0)

    def test_prior_card_answers_influence_unlocked_lessons(self):
        def lesson(ident, order, word):
            return {'id':ident, 'order':order, 'title':ident, 'prerequisites':[],
                    'vocabulary_tags':[word], 'exercises':[{'id':'ex', 'tags':[]}]}
        lessons = [lesson('greetings', 1, 'greeting'), lesson('milk', 2, 'milk')]
        with patch.object(sc, 'authored_lessons', return_value=lessons):
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['lesson_id'], 'greetings')
            self.client.post('/api/sc/answer', json={'id':'milk','direction':'to_target',
                'answer':'wrong','attempt_id':'card-00001'})
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['lesson_id'], 'milk')

    def test_choice_and_script_preserve_existing_card_history(self):
        lesson = {'id':'choice', 'order':1, 'level':'A0', 'title':'Milk', 'objective':'Choose',
                  'teaching_note':'Choose milk.', 'prerequisites':[],
                  'examples':[{'target':{'cnr':'mlijeko', 'sr':'mleko', 'hr':'mlijeko', 'bs':'mlijeko'}, 'english':'milk'}],
                  'exercises':[{'id':'choice-ex', 'kind':'choice', 'prompt':'Choose milk',
                                'answer_language':'target', 'options':[{'id':'a','text':'mleko'}, {'id':'b','text':'voda'}],
                                'accepted_answers':['a'], 'feedback':'Milk is mleko.', 'tags':['milk']}]}
        self.client.post('/api/sc/answer', json={'id':'milk', 'direction':'to_target',
                         'answer':'wrong', 'attempt_id':'old-card-001'})
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            for variant, example in [('cnr','млијеко'), ('sr','млеко'), ('hr','млијеко'), ('bs','млијеко')]:
                self.client.post('/api/sc/settings',json={'variant':variant,'script':'cyrillic'})
                public = self.client.get('/api/sc/lessons/choice').get_json()['lesson']
                self.assertEqual(public['examples'][0]['target'], example)
                self.assertEqual(public['exercises'][0]['options'][0]['text'], 'млеко')
                self.assertEqual(public['exercises'][0]['prompt'], 'Choose milk')
            def submit(value, ident):
                return self.client.post('/api/sc/lessons/answer',json={'lesson_id':'choice','exercise_id':'choice-ex',
                                        'answer':value,'attempt_id':ident})
            self.assertEqual(submit('invalid','choice-000').status_code, 400)
            self.assertFalse(submit('b','choice-001').get_json()['correct'])
            correct=submit('a','choice-002').get_json()
            self.assertTrue(correct['correct'])
            self.assertEqual(correct['expected'], ['млеко'])
            course=self.client.get('/api/sc/course').get_json()
            self.assertTrue(next(x for x in course['authored_lessons'] if x['id']=='choice')['completed'])
            self.assertEqual(next(x for x in course['items'] if x['id']=='milk')['progress']['attempts'], 1)

    def test_self_assessment_unlocks_without_turning_it_into_a_correct_answer(self):
        lesson = {'id':'one', 'order':1, 'title':'First', 'prerequisites':[], 'examples':[],
                  'exercises':[{'id':'a', 'kind':'dialogue_response', 'prompt':'Reply',
                                'accepted_answers':['Hello'], 'feedback':'A greeting.', 'tags':['greeting']}]}
        following = {**lesson, 'id':'two', 'order':2, 'prerequisites':['one'],
                     'exercises':[{**lesson['exercises'][0], 'id':'b'}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson, following]):
            payload={'lesson_id':'one', 'exercise_id':'a', 'answer':'Good day', 'attempt_id':'self-0001'}
            result=self.client.post('/api/sc/lessons/answer', json=payload).get_json()
            self.assertFalse(result['correct'])
            self.assertEqual(result['given'], 'Good day')
            self.assertTrue(result['may_self_assess'])
            self.assertEqual(self.client.get('/api/sc/lessons/two').status_code, 400)
            result=self.client.post('/api/sc/lessons/self-assess', json={'attempt_id':'self-0001'}).get_json()
            self.assertTrue(result['self_assessed'])
            self.assertFalse(result['correct'])
            self.assertTrue(self.client.post('/api/sc/lessons/self-assess', json={'attempt_id':'self-0001'}).get_json()['self_assessed'])
            self.assertTrue(self.client.post('/api/sc/lessons/answer', json=payload).get_json()['self_assessed'])
            self.assertEqual(self.client.get('/api/sc/lessons/two').status_code, 200)
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['lesson_id'], 'two')
            payload.update(answer='not sure', attempt_id='self-0002')
            self.client.post('/api/sc/lessons/answer', json=payload)
            self.assertEqual(self.client.get('/api/sc/lessons/two').status_code, 400)
            self.assertEqual(self.client.get('/api/sc/course').get_json()['recommendation']['kind'], 'review')
            self.assertEqual(self.client.post('/api/sc/lessons/self-assess', json={'attempt_id':'missing-1'}).status_code, 404)

    def test_self_assessment_does_not_override_choice_or_required_script(self):
        lesson={'id':'one','order':1,'title':'First','prerequisites':[],'examples':[],
                'exercises':[{'id':'a','kind':'choice','prompt':'Choose',
                   'options':[{'id':'a','text':'Yes'}, {'id':'b','text':'No'}],
                   'accepted_answers':['a'],'feedback':'Choose yes.','tags':[]},
                  {'id':'b','kind':'short_text','prompt':'Write Cyrillic', 'required_script':'cyrillic',
                   'accepted_answers':['\u0417\u0434\u0440\u0430\u0432\u043e'],'feedback':'Write Cyrillic.','tags':[]}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            for exercise, answer, attempt in [('a','b','choice-01'),('b','Zdravo','script-01')]:
                response=self.client.post('/api/sc/lessons/answer',json={'lesson_id':'one','exercise_id':exercise,'answer':answer,'attempt_id':attempt}).get_json()
                self.assertFalse(response['may_self_assess'])
                self.assertEqual(self.client.post('/api/sc/lessons/self-assess',json={'attempt_id':attempt}).status_code,400)

    def test_mixed_prompt_and_choice_use_authored_script_markers(self):
        lesson = {'id':'mixed', 'order':1, 'title':'Mixed', 'prerequisites':[], 'examples':[],
                  'exercises':[{'id':'pick', 'kind':'choice', 'prompt':'fallback',
                      'prompt_segments':[{'text':'Choose the form: ', 'language':'literal'},
                                         {'text':'Mi ___ ovde', 'language':'target'},
                                         {'text':' (we are here).', 'language':'literal'}],
                      'options':[{'id':'a', 'text':'smo', 'language':'target'},
                                 {'id':'b', 'text':'Latin: smo', 'language':'literal'}],
                      'accepted_answers':['a'], 'feedback':'Use smo.', 'tags':[]}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            self.client.post('/api/sc/settings', json={'variant':'sr', 'script':'cyrillic'})
            exercise = self.client.get('/api/sc/lessons/mixed').get_json()['lesson']['exercises'][0]
            self.assertEqual(exercise['prompt'], 'Choose the form: \u041c\u0438 ___ \u043e\u0432\u0434\u0435 (we are here).')
            self.assertEqual(exercise['options'][0]['text'], '\u0441\u043c\u043e')
            self.assertEqual(exercise['options'][1]['text'], 'Latin: smo')
            result = self.client.post('/api/sc/lessons/answer', json={'lesson_id':'mixed',
                'exercise_id':'pick', 'answer':'b', 'attempt_id':'mixed-0001'}).get_json()
            self.assertEqual(result['expected'], ['\u0441\u043c\u043e'])

    def test_choice_can_preserve_an_explicit_script_in_prompt_and_feedback(self):
        lesson = {'id':'scripts', 'order':1, 'title':'Scripts', 'prerequisites':[], 'examples':[],
                  'exercises':[{'id':'pick', 'kind':'choice', 'prompt':'Which Latin form?',
                     'answer_language':'target', 'options':[{'id':'a','text':'Dobar dan','language':'target','display_script':'latin'},
                     {'id':'b','text':'Zdravo','language':'target','display_script':'latin'}],
                     'accepted_answers':['a'], 'feedback':'Choose the Latin form.', 'tags':[]}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            self.client.post('/api/sc/settings', json={'variant':'sr', 'script':'cyrillic'})
            public=self.client.get('/api/sc/lessons/scripts').get_json()['lesson']['exercises'][0]
            self.assertEqual([o['text'] for o in public['options']], ['Dobar dan','Zdravo'])
            result=self.client.post('/api/sc/lessons/answer', json={'lesson_id':'scripts',
                'exercise_id':'pick', 'answer':'b', 'attempt_id':'choice-script-01'}).get_json()
            self.assertEqual(result['expected'], ['Dobar dan'])

    def test_script_specific_exercise_rejects_other_script(self):
        lesson = {'id':'scripts', 'order':1, 'title':'Scripts', 'prerequisites':[], 'examples':[],
                  'exercises':[{'id':'cyrl', 'kind':'short_text', 'prompt':'Write in Cyrillic',
                                'accepted_answers':['Здраво'], 'required_script':'cyrillic',
                                'feedback':'Use Cyrillic.', 'tags':['script']}]}
        with patch.object(sc, 'authored_lessons', return_value=[lesson]):
            def submit(value, ident):
                return self.client.post('/api/sc/lessons/answer', json={'lesson_id':'scripts', 'exercise_id':'cyrl',
                                        'answer':value, 'attempt_id':ident}).get_json()
            self.assertFalse(submit('Zdravo', 'script-001')['correct'])
            self.assertFalse(submit('Зdravo', 'script-002')['correct'])
            self.assertTrue(submit('Здраво', 'script-003')['correct'])
            self.assertEqual(submit('Zdravo', 'script-004')['expected'], ['Здраво'])


if __name__ == '__main__':
    unittest.main()
