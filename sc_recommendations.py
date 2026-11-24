"""Deterministic recommendations over authored lessons and recorded answers."""
from collections import Counter
import re


def tag_key(value):
    return re.sub(r'[-_\s]+', ' ', value.casefold()).strip()


def recommend(lessons, attempts):
    """Return an eligible lesson and reason. Attempts are in chronological order.

    A lesson is complete when each latest answer matches or is self-assessed as valid.
    This keeps a later mistake visible and never bypasses a prerequisite.
    """
    latest = {}
    for attempt in attempts:
        latest[(attempt['lesson_id'], attempt['exercise_id'])] = attempt
    completed = set()
    for lesson in lessons:
        exercises = lesson.get('exercises', [])
        if exercises and all((latest.get((lesson['id'], exercise['id']), {}).get('correct') or
                              latest.get((lesson['id'], exercise['id']), {}).get('self_assessed'))
                             for exercise in exercises):
            completed.add(lesson['id'])
    eligible = [lesson for lesson in lessons
                if set(lesson.get('prerequisites', [])) <= completed]
    eligible.sort(key=lambda lesson: (lesson.get('order', 0), lesson['id']))
    if not eligible:
        return None
    weak = Counter()
    for attempt in attempts[-30:]:
        if attempt.get('self_assessed'):
            continue  # A learner's judgment unlocks progress but is not a tested mastery signal.
        for tag in set(attempt.get('skills', []) + attempt.get('vocabulary', [])):
            weak[tag_key(tag)] += -1 if attempt['correct'] else 1
    def weakness(lesson):
        return sum(max(0, weak[tag_key(tag)]) for tag in set(lesson.get('skill_tags', []) + lesson.get('vocabulary_tags', []) + lesson.get('grammar_tags', [])))
    started = [lesson for lesson in eligible if lesson['id'] not in completed and
               any(key[0] == lesson['id'] for key in latest)]
    if started:
        lesson = max(started, key=lambda item: (weakness(item), -item.get('order', 0)))
        return {'lesson_id': lesson['id'], 'kind': 'review',
                'reason': 'Continue this lesson and review answers that need more practice.'}
    remaining = [lesson for lesson in eligible if lesson['id'] not in completed]
    if remaining:
        lesson = max(remaining, key=lambda item: (weakness(item), -item.get('order', 0)))
        reason = ('This lesson revisits topics that need practice.' if weakness(lesson)
                  else 'This is the next available lesson.')
        return {'lesson_id': lesson['id'], 'kind': 'lesson', 'reason': reason}
    lesson = max(eligible, key=lambda item: (weakness(item), -item.get('order', 0)))
    return {'lesson_id': lesson['id'], 'kind': 'review',
            'reason': 'Review an earlier lesson to keep it fresh.'}
