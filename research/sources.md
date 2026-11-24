# Source notes and sentence pilot

Snapshot: 19 November 2026. Research search used the local SearXNG instance; Yandex and Seznam engine selectors were used when defaults returned irrelevant results. [Detailed research and source caveats](../SERBO_CROATIAN_RESEARCH.md) contains the larger source manifest.

## Pilot data and reuse

[tatoeba-pilot.json](tatoeba-pilot.json) contains 13 hand-selected, directly linked Tatoeba pairs: 4 Serbian, 5 Croatian and 4 Bosnian. Each side retains its text, ISO 639-3 source label, sentence ID, original contributor from the sentence history, current owner in the detailed export, source URL and verified sentence-level license. Attribution must cover **both** sentences and include the indicated license and source links; owners can differ from initial contributors. No audio is included. The source language label is not a claim of exclusive use, country, or a Montenegrin variety. Script is identified; Ekavian/Ijekavian is left unset where not established. The selection is a pilot, not a CEFR-rated corpus, and still needs native-speaker review.

The five weekly source archives are identified by exact URLs and SHA-256 in the JSON; download timestamps were 19 November and the server reported 14 November 2026 for the English and links archives. Archives are deliberately outside this repository. Pairs were selected by matching IDs in `links.tar.bz2` to the four detailed exports. Exact normalized duplicate source texts, English texts and sentence pairs were excluded. An obviously incorrect Bosnian cat sentence and misspelled hotel/toilet candidates were excluded rather than repaired or silently attributed. Sources can change after this snapshot; recheck licenses and attribution before redistributing a refreshed export. The Tatoeba downloads page is https://tatoeba.org/en/downloads ; audio licenses are independent and empty audio licenses do not permit external reuse.

## Examination references

- Serbian: University of Belgrade's Center for Serbian as a Foreign Language publishes A1-C2 written examples, listening audio and a speaking example: https://learnserbian.fil.bg.ac.rs/ . Link to official examples; no reuse permission for exam content was established.
- Montenegrin: The Faculty of Montenegrin Language and Literature hosts the 2018 national education council program for testing foreigners: https://fcjk.ac.me/wp-content/uploads/2024/03/Provjera-znanja-crnogorskoga-jezika-za-strance.pdf . It describes a permanent-residence A2 assessment in listening, reading, writing and speaking, with at least 60% in each section. This historical program does not establish current legal requirements. Faculty course details: https://fcjk.ac.me/kurs-crnogorskoga-jezika-za-strance/ .
- Croatian: Zagreb's Croaticum discusses CEFR testing at https://croaticum.ffzg.unizg.hr/?p=7071 ; its linked test page returned 404 at research time. No public sample exam or reproduction license was verified.
- Bosnian: IUS advertises a beginner A1.1 course at https://www.ius.edu.ba/en/event/bosnian-language-course-level-a11-0 ; this is a course, not a verified national examination.
- CEFR ability descriptors are available at https://rm.coe.int/cefr-companion-volume-with-new-descriptors-2018/1680787989 . No joint embassy exam was substantiated.

## Speech

- On Windows, installed `piper-tts 1.8.0` (GPL-3.0-or-later) and the author's MIT-declared Serbian Marko model produced nonempty 22,050 Hz mono WAVs from Serbian Latin, diacritics and Cyrillic via the Python `PiperVoice` API. Model and runtime are separate licensing questions. The model card https://huggingface.co/phantom9623/piper-serbian-tts notes prosody problems, and its training data provenance is not fully documented. Files and test audio stayed outside the repository. Synthesis success does not establish native pronunciation or redistribution clearance.
- The Piper `sr_RS-serbski_institut` model is unsafe to treat as Serbian: its model card https://huggingface.co/rhasspy/piper-voices/blob/main/sr/sr_RS/serbski_institut/medium/MODEL_CARD points to a Lower Sorbian training corpus under CC BY-NC-SA 4.0. No judgment about its actual sound was made.
- Microsoft documents Serbian, Croatian and Bosnian cloud neural voices at https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support ; verify region, service terms and pronunciation. No dedicated Montenegrin TTS voice was established. Browser voice availability is device dependent.
- eSpeak NG lists Serbian, Croatian and Bosnian and both scripts: https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md . It is GPL-3.0-or-later and formant speech; no local eSpeak generation or listening test was performed.
