"""Build a provisional frequency-ranked Serbo-Croatian vocabulary candidate file.

Pass the directory containing dictionary.jsonl and sr/hr/bs.txt, then the output
path. See research/sc_frequency_2000_sources.md for provenance and limitations.
"""
import argparse
from collections import defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote

PITCH_MARKS = {'\u0300', '\u0301', '\u0302', '\u0304', '\u030f', '\u0311'}
CYR = dict(zip('абвгдђежзијклмнопрстћуфхцчџш',
               ['a','b','v','g','d','đ','e','ž','z','i','j','k','l','m','n','o','p','r','s','t','ć','u','f','h','c','č','dž','š']))
CYR.update({'љ':'lj','њ':'nj','ј':'j'})
ALLOWED_POS = {'noun', 'verb', 'adj', 'adv', 'pron', 'det', 'prep', 'conj', 'particle', 'intj', 'num'}
EXCLUDED_SENSE_TAGS = {'form-of', 'alt-of', 'obsolete', 'archaic', 'misspelling', 'error', 'nonstandard'}
MORPH_TAGS = {'nominative', 'genitive', 'dative', 'accusative', 'vocative', 'instrumental', 'locative', 'present', 'past', 'future', 'imperative', 'participle', 'infinitive', 'singular', 'plural', 'comparative', 'superlative'}
# Reviewed spelling counterparts, with source links in the notes. These are
# spellings of a headword, not blanket equivalences between standards.
PAIRS = [('mlijeko', 'mleko'), ('čovjek', 'čovek'), ('vrijeme', 'vreme'),
         ('dijete', 'dete'), ('lijep', 'lep'), ('snijeg', 'sneg'), ('vjera', 'vera')]
# The dictionary identifies oni, mi and vi as plural forms of on, ja and ti.
# Keep their source senses and tagged counts without calling them spellings.
PARADIGM = [('on', 'oni'), ('ja', 'mi'), ('ti', 'vi')]
# Sense-specific lexical alternatives, with labels as supplied by Wiktionary.
# These are not automatically interchangeable in unrelated senses.
REGIONAL = {
    'kruh': [
        {'form':'hleb', 'sense':'bread', 'source_tags':['Ekavian'], 'source_url':'https://en.wiktionary.org/wiki/hleb#Serbo-Croatian'},
        {'form':'hljeb', 'sense':'bread', 'source_tags':['Ijekavian', 'regional'], 'source_url':'https://en.wiktionary.org/wiki/hljeb#Serbo-Croatian'}],
    'vlak': [{'form':'voz', 'sense':'train', 'source_tags':['Bosnia', 'Serbia'], 'source_url':'https://en.wiktionary.org/wiki/voz#Serbo-Croatian'}],
    'tisuća': [{'form':'hiljada', 'sense':'thousand', 'source_tags':['Bosnia', 'Croatia', 'Serbia'], 'source_url':'https://en.wiktionary.org/wiki/hiljada#Serbo-Croatian'}],
    'tjedan': [{'form':'sedmica', 'sense':'week', 'source_tags':['Bosnia', 'regional'], 'source_url':'https://en.wiktionary.org/wiki/sedmica#Serbo-Croatian'}],
}

@lru_cache(maxsize=250000)
def normal(s):
    # Acute is a lexical mark in ć, ś and ź, not a pitch accent. Keep it.
    chars = []
    base = ''
    for c in unicodedata.normalize('NFD', s.casefold()):
        if not unicodedata.combining(c):
            base = c
        if c in PITCH_MARKS and not (c == '\u0301' and base in 'csz'):
            continue
        chars.append(c)
    s = ''.join(chars)
    s = unicodedata.normalize('NFC', s)
    return ''.join(CYR.get(c, c) for c in s)

def word(s):
    return bool(s and len(s) <= 40 and all(c.isalpha() for c in s))

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    freq, totals = {}, {}
    for lang in ('sr', 'hr', 'bs'):
        counts = defaultdict(int)
        for line in (args.inputs / (lang + '.txt')).read_text(encoding='utf8').splitlines():
            token, count = line.rsplit(' ', 1)
            token = normal(token)
            if word(token):
                counts[token] += int(count)
        freq[lang] = counts
        # Denominator includes every listed token, including symbols, to keep
        # comparable within-list relative frequencies.
        totals[lang] = sum(int(x.rsplit(' ', 1)[1]) for x in (args.inputs / (lang + '.txt')).read_text(encoding='utf8').splitlines())
    observed = set().union(*(set(v) for v in freq.values()))
    entries, form_targets, morph = {}, defaultdict(set), defaultdict(dict)
    with (args.inputs / 'dictionary.jsonl').open(encoding='utf8') as source:
        for line in source:
            obj = json.loads(line)
            original = obj.get('word', '')
            lemma = normal(original)
            if not word(lemma) or original[:1].isupper() or obj.get('pos') not in ALLOWED_POS:
                continue
            senses = []
            for sense in obj.get('senses', []):
                tags = sense.get('tags', [])
                if sense.get('form_of') or sense.get('alt_of') or EXCLUDED_SENSE_TAGS.intersection(tags):
                    for target in sense.get('form_of', []):
                        target = normal(target.get('word', ''))
                        if lemma in observed and word(target):
                            form_targets[lemma].add(target)
                    continue
                glosses = [x.strip() for x in sense.get('glosses', []) if isinstance(x, str) and x.strip()]
                if glosses:
                    senses.append({'pos':obj['pos'], 'glosses':glosses, 'tags':tags,
                                   'source_headword':original,
                                   'source_id':sense.get('id'),
                                   'source_url':'https://en.wiktionary.org/wiki/' + quote(original, safe='') + '#Serbo-Croatian'})
            if not senses:
                continue
            entry = entries.setdefault(lemma, {'senses':[], 'cyrillic':set()})
            for sense in senses:
                if sense not in entry['senses']:
                    entry['senses'].append(sense)
            form_targets[lemma].add(lemma)
            for form in obj.get('forms', []):
                text, tags = form.get('form', ''), form.get('tags', [])
                if 'Cyrillic' in tags and text:
                    clean = ''.join(c for c in unicodedata.normalize('NFD', text) if c not in PITCH_MARKS)
                    entry['cyrillic'].add(unicodedata.normalize('NFC', clean))
                normalized = normal(text)
                if normalized in observed and word(normalized) and MORPH_TAGS.intersection(tags):
                    form_targets[normalized].add(lemma)
                    morph[lemma][normalized] = sorted(set(tags))
    # Collapse only explicitly listed spelling pairs, before ambiguity checks.
    canonical = {key:key for key in entries}
    for preferred, alternate in PAIRS + PARADIGM:
        if preferred in entries and alternate in entries:
            canonical[alternate] = preferred
    for f in form_targets:
        form_targets[f] = {canonical[t] for t in form_targets[f] if t in entries}
    grouped = {}
    for lemma, entry in entries.items():
        target = canonical[lemma]
        g = grouped.setdefault(target, {'spellings':[], 'attached_lemmas':[], 'senses':[], 'cyrillic':set()})
        if (target, lemma) in PARADIGM:
            g['attached_lemmas'].append(lemma)
        else:
            g['spellings'].append(lemma)
        g['cyrillic'].update(entry['cyrillic'])
        for sense in entry['senses']:
            if sense not in g['senses']:
                g['senses'].append(sense)
    # hrLex contains corpus-tagged (surface, lemma, POS) frequencies. Use
    # these rather than guessing the lemma of an ambiguous subtitle token.
    upos = {'NOUN':'noun', 'VERB':'verb', 'AUX':'verb', 'ADJ':'adj',
            'ADV':'adv', 'PRON':'pron', 'DET':'det', 'ADP':'prep',
            'CCONJ':'conj', 'SCONJ':'conj', 'PART':'particle', 'INTJ':'intj', 'NUM':'num'}
    # Wiktionary and UD use different boundaries for determiners/pronouns.
    compatible = {'pron':{'pron', 'det'}, 'det':{'pron', 'det'}}
    available_pos = {lemma:{sense['pos'] for sense in g['senses']} for lemma,g in grouped.items()}
    evidence = defaultdict(int)
    pos_counts = defaultdict(lambda:defaultdict(int))
    observed_forms = defaultdict(lambda:defaultdict(int))
    with gzip.open(args.inputs / 'hrLex_v1.3.gz', 'rt', encoding='utf8') as source:
        for line in source:
            fields = line.rstrip('\n').split('\t')
            if len(fields) < 8 or fields[4] not in upos:
                continue
            lemma = normal(fields[1])
            if lemma not in canonical:
                continue
            surface = normal(fields[0])
            if not word(surface):
                continue
            target = canonical[lemma]
            pos = upos[fields[4]]
            if not available_pos[target].intersection(compatible.get(pos, {pos})):
                continue
            count = int(fields[6])
            if count <= 0:
                continue
            evidence[target] += count
            pos_counts[target][pos] += count
            observed_forms[target][surface] += count
    candidates=[]
    for lemma, count in evidence.items():
        g=grouped[lemma]
        candidates.append((count,lemma,g))
    candidates.sort(key=lambda row:(-row[0],row[1]))
    out=[]
    for rank,(count,lemma,g) in enumerate(candidates[:2000],1):
        supported = set(g['attached_lemmas'])
        for spelling in g['spellings'] + g['attached_lemmas']:
            supported.update(morph[spelling])
        # Require the corpus analysis to agree with a dictionary paradigm or
        # an explicit attached lemma. This still does not disambiguate senses.
        inflections = [{'form':form, 'count':n} for form,n in
                       sorted(observed_forms[lemma].items(),key=lambda row:(-row[1],row[0]))[:30]
                       if form not in g['spellings'] and form in supported]
        # Collapse exact duplicates while retaining all contributing pages.
        merged_senses = {}
        for sense in g['senses']:
            key = (sense['pos'], tuple(sense['glosses']), tuple(sorted(sense['tags'])))
            if key not in merged_senses:
                merged_senses[key] = dict(sense, alternate_source_urls=[], alternate_source_ids=[])
            else:
                merged = merged_senses[key]
                if sense['source_url'] != merged['source_url'] and sense['source_url'] not in merged['alternate_source_urls']:
                    merged['alternate_source_urls'].append(sense['source_url'])
                if sense['source_id'] and sense['source_id'] != merged['source_id'] and sense['source_id'] not in merged['alternate_source_ids']:
                    merged['alternate_source_ids'].append(sense['source_id'])
        # POS frequency is evidence only for the grammatical category; it is
        # not evidence that the first sense within that category is common.
        senses = sorted(merged_senses.values(), key=lambda s: (-pos_counts[lemma].get(s['pos'], 0),
                                                                 normal(s['source_headword']) != lemma))
        out.append({'id':'sc-'+hashlib.sha256(lemma.encode()).hexdigest()[:16], 'rank':rank,
                    'lemma_latin':lemma, 'spellings_latin':sorted(g['spellings']),
                    'attached_lemmas':sorted(g['attached_lemmas']),
                    'regional_alternatives':REGIONAL.get(lemma, []),
                    'cyrillic':sorted(g['cyrillic']), 'inflections':inflections,
                    'senses':senses, 'frequency':{'hrwac_tagged_count':count,
                    'hrwac_pos_counts':dict(pos_counts[lemma]),
                    'subtitle_headword_surface_counts':{lang:sum(freq[lang].get(s,0) for s in g['spellings']) for lang in freq}},
                    'review_status':'unreviewed_machine_join'})
    if len(out) != 2000:
        raise RuntimeError(f'Only {len(out)} candidates')
    result={'schema_version':1, 'status':'candidate_unreviewed',
            'rank_method':'descending hrLex 1.3 hrWaC tagged counts for dictionary-matched lemma and POS; alphabetical tiebreak',
            'subtitle_corpus_totals':totals, 'input_sha256':{x:sha(args.inputs/x) for x in ('dictionary.jsonl','hrLex_v1.3.gz','sr.txt','hr.txt','bs.txt')},
            'entries':out}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Wrote',len(out),'entries to',args.output)
    for item in out[:25]:
        print(item['rank'],item['lemma_latin'],item['senses'][0]['glosses'][0],item['frequency']['hrwac_tagged_count'])

if __name__ == '__main__':
    main()
