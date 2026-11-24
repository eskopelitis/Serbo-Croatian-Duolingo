'use strict';
let vocabularyQuery='', vocabularyOffset=0, vocabularyRequest=0;
function lessonExampleSource(source){
  if(!source || source.corpus!=='Tatoeba')return '';
  const sourceId=Number(source.source_sentence_id), translationId=Number(source.translation_sentence_id);
  if(!Number.isSafeInteger(sourceId) || sourceId<1 || !Number.isSafeInteger(translationId) || translationId<1)return '';
  return `<small>Tatoeba: <a href="https://tatoeba.org/en/sentences/show/${sourceId}" target="_blank" rel="noopener noreferrer">${esc(source.source_contributor)}</a> (export owner ${esc(source.source_export_owner)}); translation: <a href="https://tatoeba.org/en/sentences/show/${translationId}" target="_blank" rel="noopener noreferrer">${esc(source.translation_contributor)}</a> (export owner ${esc(source.translation_export_owner)}). <a href="https://creativecommons.org/licenses/by/2.0/fr/" target="_blank" rel="noopener noreferrer">${esc(source.license)}</a>. ${esc(source.modification)} Script may be converted.</small>`;
}
// Lesson path layout adapted from sanidhyy/duolingo-clone (MIT); path styles live in style.css.
const PATH_ICON=d=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const PATH_ICONS={
  check:PATH_ICON('<path d="M4.5 12.5 9.5 17.5 19.5 7" stroke-width="3.5"/>'),
  star:PATH_ICON('<path d="M12 3.5l2.7 5.5 6 .9-4.35 4.25 1.03 6-5.38-2.83L6.62 20.15l1.03-6L3.3 9.9l6-.9z" fill="currentColor" stroke-width="2"/>'),
  crown:PATH_ICON('<path d="M4 8l3.5 3L12 5l4.5 6L20 8l-1.5 10h-13z"/><path d="M5.5 20.5h13"/>')
};
function pathNode(l,current,last,step,unitProgress){
  const shift=[0,1,2,1,0,-1,-2,-1][step%8];
  const icon=l.completed?PATH_ICONS.check:last?PATH_ICONS.crown:PATH_ICONS.star;
  const cls=['node',l.completed?'mastered':current?'current':'',l.unlocked?'':'locked',last?'trophy':''].filter(Boolean).join(' ');
  const node=l.unlocked
    ?`<a class="${cls}" href="#lesson/${encodeURIComponent(l.id)}" aria-label="${l.completed?'Review':'Open'} ${esc(l.title)}">${icon}</a>`
    :`<span class="${cls}" role="img" aria-label="Locked: ${esc(l.title)}">${icon}</span>`;
  const label=`<span class="node-label">${esc(l.title)}</span>`;
  if(!current)return `<li class="roadmap-lesson node-slot" style="--shift:${shift}">${node}${label}</li>`;
  // ponytail: ring shows unit progress; lessons have no partial-progress field yet.
  const C=2*Math.PI*47, offset=C*(1-unitProgress);
  return `<li class="roadmap-lesson node-slot is-next" style="--shift:${shift}"><span class="start-bubble">Start</span><div class="node-ring"><svg class="ring" viewBox="0 0 102 102" aria-hidden="true"><circle class="trail" cx="51" cy="51" r="47"/><circle class="path" cx="51" cy="51" r="47" stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"/></svg>${node}</div>${label}</li>`;
}
function renderLessons(){
  const lessons=[...data.authored_lessons].sort((a,b)=>a.order-b.order);
  const next=lessons.find(l=>l.unlocked&&!l.completed);
  const done=lessons.filter(l=>l.completed).length;
  const units=[];
  lessons.forEach((lesson,index)=>{
    const id=lesson.unit_id || `unit-${Math.floor(index/5)+1}`;
    let unit=units.find(item=>item.id===id);
    if(!unit){unit={id,title:lesson.unit_title || 'Lessons',objective:lesson.unit_objective || '',lessons:[]};units.push(unit);}
    unit.lessons.push(lesson);
  });
  let step=0; // global index, so the zig-zag flows unbroken through unit banners
  app.innerHTML=`<div class="page">${pageTitle('YOUR COURSE','Your lesson roadmap.','Build confidence one practical lesson at a time.')}<section class="roadmap-summary" aria-label="Course progress"><div><div class="eyebrow">YOUR PROGRESS</div><h2>${done} of ${lessons.length} lessons complete</h2><div class="roadmap-progress" role="progressbar" aria-label="Lessons completed" aria-valuemin="0" aria-valuemax="${lessons.length}" aria-valuenow="${done}"><span style="width:${lessons.length?100*done/lessons.length:0}%"></span></div></div>${next?`<div><div class="eyebrow">UP NEXT</div><h3>${esc(next.title)}</h3><p>${esc(next.objective)}</p><a class="button" href="#lesson/${encodeURIComponent(next.id)}">Start next lesson →</a></div>`:'<p>All available lessons are complete. Revisit any lesson below.</p>'}</section><div class="section-head"><div><div class="eyebrow">YOUR LEARNING PATH</div><h2>Follow the sequence.</h2></div></div>${units.map((unit,index)=>{const unitDone=unit.lessons.filter(l=>l.completed).length;const nextHere=unit.lessons.includes(next);return `<section class="roadmap-unit unit"><div class="unit-banner"><div class="u-text"><div class="u-eyebrow">Unit ${index+1}</div><h3>${esc(unit.title)}</h3>${unit.objective?`<p>${esc(unit.objective)}</p>`:''}</div><span class="u-count" aria-label="${unitDone} of ${unit.lessons.length} complete">${unitDone}/${unit.lessons.length}</span>${nextHere?`<a class="button light" href="#lesson/${encodeURIComponent(next.id)}">Continue</a>`:''}</div><ol class="roadmap-list node-track">${unit.lessons.map((l,i)=>pathNode(l,l===next,i===unit.lessons.length-1,step++,unit.lessons.length?unitDone/unit.lessons.length:0)).join('')}</ol></section>`;}).join('')||'<div class="empty">No lessons are available yet.</div>'}<div class="actions"><a class="button outline" href="#practice">Word-card practice</a></div></div>`;
}
async function renderAuthoredLesson(id){
  app.innerHTML='<div class="page"><p>Loading lesson…</p></div>';
  try{
    const result=await api(`lessons/${encodeURIComponent(id)}`);
    if(location.hash!==`#lesson/${encodeURIComponent(id)}`)return;
    const lesson=result.lesson;
    let index=0, correct=0, selfAssessed=0;
    const draw=()=>{
      const exercise=lesson.exercises[index];
      if(!exercise){const completed=data.authored_lessons.find(item=>item.id===lesson.id)?.completed;app.innerHTML=`<div class="page">${pageTitle(completed?'LESSON COMPLETE':'LESSON PRACTICE FINISHED',`${esc(lesson.title)}<br><em>practised.</em>`,`You matched ${correct} of ${lesson.exercises.length} model answers${selfAssessed?` and marked ${selfAssessed} other answer${selfAssessed===1?"":"s"} valid yourself`:""}. Your answers are saved.`)}<div class="actions"><a class="button" href="#lessons">See your next suggestion →</a><button class="button outline" id="retry-lesson">Practise this lesson again</button></div></div>`;document.getElementById('retry-lesson').onclick=()=>{index=0;correct=0;selfAssessed=0;draw();};return;}
      const attempt=(window.crypto && crypto.randomUUID?crypto.randomUUID():`lesson-${Date.now()}-${Math.random().toString(36).slice(2)}`);
      app.innerHTML=`<div class="page">${pageTitle(`${lesson.level} · LESSON ${lesson.order}`,esc(lesson.title),lesson.objective)}<div class="panel"><p>${esc(lesson.teaching_note)}</p>${lesson.examples.map(x=>`<div class="word-row"><div><strong lang="${languageTag()}">${esc(x.target)}</strong>${x.note?`<small>${esc(x.note)}</small>`:''}${x.alternatives?.length?`<small>Also: ${x.alternatives.map(esc).join(' / ')}</small>`:''}</div><div>${esc(x.english)}${lessonExampleSource(x.source)}</div>${soundButton(x.speech,x.speech_cyrillic)}</div>`).join('')}</div><div class="panel"><span class="pill">QUESTION ${index+1} OF ${lesson.exercises.length}</span><p class="prompt">${esc(exercise.prompt)}</p><form id="lesson-answer" class="form-grid">${exercise.kind==='choice'?exercise.options.map(o=>`<label class="choice" style="display:flex;align-items:center;gap:10px"><input type="radio" name="answer" value="${esc(o.id)}" required> ${esc(o.text)}</label>`).join(''):'<label>Your answer<input class="field" name="answer" maxlength="300" required autocomplete="off"></label>'}<div><button class="button" id="lesson-submit">Check answer →</button></div></form><div id="lesson-feedback" role="status"></div></div><div class="actions"><a class="button outline" href="#lessons">← Lesson library</a></div></div>`;
      bindSounds();
      const form=document.getElementById('lesson-answer');
      form.onsubmit=async e=>{
        e.preventDefault();
        const button=document.getElementById('lesson-submit');button.disabled=true;
        try{
          const answer=new FormData(form).get('answer');
          const response=await api('lessons/answer',{lesson_id:lesson.id,exercise_id:exercise.id,answer,attempt_id:attempt});
          if(!form.isConnected)return;
          await load();if(!form.isConnected)return;
          if(response.correct)correct++;
          form.querySelectorAll('input').forEach(input=>input.disabled=true);button.remove();
          const feedback=document.getElementById('lesson-feedback');
          feedback.innerHTML=`<div class="feedback ${response.correct?'':response.may_self_assess?'review':'wrong'}"><strong>${response.correct?'That\u2019s right.':'Compare with the model answer.'}</strong> ${esc(response.feedback)}${!response.correct?`<br>Your answer: ${esc(response.given ?? answer)}<br>Model answer: ${response.expected.map(esc).join(' / ')}`:''}${response.may_self_assess?'<p>If your answer is also valid, you can mark it yourself. It will count toward completing this lesson but is not a verified answer.</p>':''}</div><div class="actions">${response.may_self_assess?'<button type="button" class="button outline" id="lesson-self-assess">My answer is also valid</button>':''}<button class="button" id="lesson-next">${index+1===lesson.exercises.length?'Finish lesson':'Next question'} \u2192</button></div><div id="self-assess-status" role="status"></div>`;
          const next=document.getElementById('lesson-next');next.onclick=()=>{index++;draw();};
          const self=document.getElementById('lesson-self-assess');
          if(self)self.onclick=async()=>{
            self.disabled=true;next.disabled=true;
            try{
              await api('lessons/self-assess',{attempt_id:attempt});
              await load();if(!form.isConnected)return;
              selfAssessed++;self.textContent='Marked valid by you';
              document.getElementById('self-assess-status').textContent='Saved as your own assessment, not a verified answer.';
            }catch(err){if(!form.isConnected)return;self.disabled=false;document.getElementById('self-assess-status').textContent=err.message;}
            finally{if(form.isConnected)next.disabled=false;}
          };
        }catch(err){if(!form.isConnected)return;button.disabled=false;document.getElementById('lesson-feedback').textContent=err.message;}
      };
    };
    draw();
  }catch(err){if(location.hash.startsWith('#lesson/'))app.innerHTML=`<div class="page"><p role="alert">${esc(err.message)}</p><a href="#lessons">Back to lessons</a></div>`;}
}
function vocabularyMeaning(entry){
  if(entry.primary_meaning)return {text:entry.primary_meaning,source:entry.source_url || ''};
  for(const sense of entry.senses || [])for(const gloss of sense.glosses || []){
    // The inventory is unreviewed dictionary data; choose one short candidate,
    // never concatenate the raw senses into the learner-facing entry.
    const candidate=gloss.replace(/\s*\([^)]*\)/g,'').split(/[,;]/)[0].trim().replace(/[.:]+$/,'');
    if(candidate && candidate.length<=70 && !/^(used |a form of |alternative |inflection |the act of |past |plural |\()/i.test(candidate))return {text:candidate,source:sense.source_url || ''};
  }
  return {text:'Meaning not available',source:''};
}
function renderVocabulary(){
  app.innerHTML=`<div class="page">${pageTitle('FREQUENCY REFERENCE','A wider world<br><em>of words.</em>','Explore ranked words and their short meanings.')}<p class="muted">These automatically selected meanings have not been individually reviewed and may contain errors.</p><details class="notice"><summary>About these words and sources</summary><p>Rank is based on hrLex 1.3 counts from the Croatian hrWaC web corpus; it is not a balanced ranking for all four standards. Meanings are adapted from English Wiktionary via Kaikki and may have extraction errors. <a href="https://hdl.handle.net/11356/1232" target="_blank" rel="noopener noreferrer">hrLex source</a> · <a href="https://kaikki.org/dictionary/Serbo-Croatian/index.html" target="_blank" rel="noopener noreferrer">Kaikki extract</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA</a> · <a href="https://en.wiktionary.org/wiki/Wiktionary:Copyrights" target="_blank" rel="noopener noreferrer">Wiktionary licensing</a></p></details><form class="toolbar" id="vocabulary-search"><label class="field-label" for="vocabulary-query">Search headwords or definitions</label><input class="field" id="vocabulary-query" type="search" maxlength="100" value="${esc(vocabularyQuery)}"><button class="button">Search</button><a class="button outline" href="#words">Back to words</a></form><p id="vocabulary-count" role="status"></p><div class="word-list" id="vocabulary-list"></div><div class="actions" id="vocabulary-pages"></div></div>`;
  const form=document.getElementById('vocabulary-search');
  form.onsubmit=e=>{e.preventDefault();vocabularyQuery=document.getElementById('vocabulary-query').value.trim();vocabularyOffset=0;loadVocabulary();};
  loadVocabulary();
}
async function loadVocabulary(){
  const requestId=++vocabularyRequest, list=document.getElementById('vocabulary-list'), count=document.getElementById('vocabulary-count'), pages=document.getElementById('vocabulary-pages');
  count.textContent='Loading vocabulary…';list.innerHTML='';pages.innerHTML='';
  try{
    const result=await api(`vocabulary?q=${encodeURIComponent(vocabularyQuery)}&offset=${vocabularyOffset}`);
    if(requestId!==vocabularyRequest || !list.isConnected)return;
    count.textContent=`${result.total} matches in ${result.inventory_total} ranked entries${result.total?` · showing ${result.offset+1}–${Math.min(result.offset+result.entries.length,result.total)}`:''}`;
    list.innerHTML=result.entries.length?result.entries.map(entry=>{const meaning=vocabularyMeaning(entry);const url=/^https:\/\/en\.wiktionary\.org\/wiki\//.test(meaning.source)?meaning.source:'';return `<article class="word-row vocabulary-entry"><div><strong lang="${languageTag()}">${esc(entry.target)}</strong> <span aria-hidden="true">·</span> ${esc(meaning.text)}<small>Rank ${entry.rank}</small>${url?`<details class="word-source"><summary>Source</summary><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Wiktionary contributors</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a></details>`:''}</div>${soundButton(entry.speech,entry.speech_cyrillic)}</article>`;}).join(''):'<div class="empty">No entries found. Try another search.</div>';
    pages.innerHTML=`<button class="button outline" id="vocabulary-prev" ${result.offset===0?'disabled':''}>← Previous</button><button class="button outline" id="vocabulary-next" ${result.offset+result.entries.length>=result.total?'disabled':''}>Next →</button>`;
    document.getElementById('vocabulary-prev').onclick=()=>{vocabularyOffset=Math.max(0,vocabularyOffset-result.limit);loadVocabulary();};
    document.getElementById('vocabulary-next').onclick=()=>{vocabularyOffset+=result.limit;loadVocabulary();};bindSounds();
  }catch(err){if(list.isConnected)count.textContent=err.message;}
}
let checkState = null;
function shuffled(items) {
  const result=[...items];
  for(let i=result.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[result[i],result[j]]=[result[j],result[i]];}
  return result;
}
function teachingSections() {
  return `<div class="section-head"><div><div class="eyebrow">A LITTLE STRUCTURE</div><h2>Learn in context.</h2><p>Eight short lessons, everyday dialogues and a gentle self-check.</p></div></div><div class="cards"><a class="card card-button" href="#dialogues"><span class="number">01 / READ &amp; LISTEN</span><h3>Everyday dialogues</h3><p>Follow five short conversations and try the prompts aloud.</p><span class="card-footer">Open dialogues →</span></a><a class="card card-button" href="#check"><span class="number">02 / SEE WHERE YOU ARE</span><h3>A beginner self-check</h3><p>Sixteen questions for reflection, with explanations.</p><span class="card-footer">Start the self-check →</span></a><a class="card card-button" href="#tutor"><span class="number">03 / PRACTISE A CHAT</span><h3>Conversation partner</h3><p>Try a text conversation with the configured AI model.</p><span class="card-footer">Open a chat →</span></a><a class="card card-button" href="#writing"><span class="number">04 / WRITE</span><h3>Writing feedback</h3><p>Get optional feedback on a short piece of writing.</p><span class="card-footer">Open the writing page →</span></a></div><div class="section-head"><div><div class="eyebrow">THE BEGINNER LESSONS</div><h2>One idea at a time.</h2></div></div>${data.teaching.lessons.map(l=>`<article class="panel lesson"><div class="eyebrow">LESSON ${esc(l.order)}</div><h3>${esc(l.title)}</h3><p>${esc(l.body)}</p>${l.examples.map(x=>`<div class="word-row" style="margin-top:12px"><div><strong lang="${languageTag()}">${esc(x.text)}</strong>${x.note?`<small>${esc(x.note)}</small>`:''}</div><div>${esc(x.english)}</div>${soundButton(x.speech,x.speech_cyrillic)}</div>`).join('')}</article>`).join('')}`;
}
function renderDialogues() {
  const dialogues=data.teaching.dialogues.map(d=>`<article class="panel"><div class="eyebrow">EVERYDAY DIALOGUE</div><h2>${esc(d.title)}</h2><p class="muted">${esc(d.context)}</p>${d.lines.map(line=>`<div class="word-row" style="margin-top:10px"><div><small>PERSON ${esc(line.speaker)}</small><strong lang="${languageTag()}">${esc(line.text)}</strong></div><div>${esc(line.english)}</div>${soundButton(line.speech,line.speech_cyrillic)}</div>`).join('')}<p class="notice"><strong>Try it:</strong> ${esc(d.practice_prompt)}</p></article>`).join('');
  const rhythm=data.teaching.rhythm.map(r=>`<article class="panel"><div class="eyebrow">READ TO A BEAT</div><h2>${esc(r.title)}</h2>${r.lines.map((line,i)=>`<div class="word-row" style="margin-top:10px"><div><strong lang="${languageTag()}">${esc(line.text)}</strong></div><div>${esc(r.english[i])}</div>${soundButton(line.speech,line.speech_cyrillic)}</div>`).join('')}<p class="muted">${esc(r.usage_note)}</p></article>`).join('');
  app.innerHTML=`<div class="page">${pageTitle('READ & LISTEN','Words in<br><em>conversation.</em>','Read a short exchange, listen if a supported voice is available, then try the prompt yourself.')}<p class="notice">${esc(voiceInfo())} These are reading and speaking prompts; they do not assess your speech.</p>${dialogues}${rhythm}<div class="actions"><a class="button outline" href="#grammar">← Back to the guide</a></div></div>`;
  bindSounds();
}
function renderCheck() {
  if(!checkState)checkState={index:0,matched:0,self:0,order:Object.fromEntries(data.teaching.questions.filter(q=>q.options).map(q=>[q.id,shuffled(q.options)]))};
  const s=checkState, q=data.teaching.questions[s.index];
  if(!q){app.innerHTML=`<div class="page">${pageTitle('SELF-CHECK COMPLETE','A starting point,<br><em>not a label.</em>',`You matched ${s.matched} of ${data.teaching.questions.length} model answers${s.self?` and marked ${s.self} other answers as possibly valid`:''}. This is not a CEFR level or an official exam.`)}<div class="actions"><button class="button" id="restart-check">Try again</button><a class="button outline" href="#grammar">Back to the guide</a></div></div>`;document.getElementById('restart-check').onclick=()=>{checkState=null;renderCheck();};return;}
  app.innerHTML=`<div class="page">${pageTitle('BEGINNER SELF-CHECK','See what you<br><em>already know.</em>','A short reading and language check, not an exam or a CEFR level. Examples use the scripts shown in each question.')}<div class="panel"><span class="pill">QUESTION ${s.index+1} OF ${data.teaching.questions.length}</span><p class="prompt" style="font-size:30px">${esc(q.prompt)}</p><form id="check-form" class="form-grid">${q.kind==='choice'?s.order[q.id].map(o=>`<label class="choice" style="display:flex;align-items:center;gap:10px"><input type="radio" name="answer" value="${esc(o.id)}" required> ${esc(o.text)}</label>`).join(''):`<label>Your answer<input class="field" name="answer" maxlength="300" required autocomplete="off"></label>`}<div><button class="button" id="check-submit">Check answer →</button></div></form><div id="check-feedback" role="status"></div><p class="muted">Results stay in this session and do not change your word progress.</p></div></div>`;
  document.getElementById('check-form').onsubmit=async e=>{e.preventDefault();const form=e.target,button=document.getElementById('check-submit');button.disabled=true;try{const response=await api('check/answer',{id:q.id,answer:new FormData(form).get('answer')});if(!form.isConnected)return;if(response.correct)s.matched++;form.querySelectorAll('input').forEach(input=>input.disabled=true);button.remove();const feedback=document.getElementById('check-feedback');feedback.innerHTML=`<div class="feedback ${response.correct?'':'wrong'}"><strong>${response.correct?'Matched a model answer.':'Compare with the model answer.'}</strong> ${esc(response.feedback)}</div><div class="actions">${response.may_self_assess?'<button class="button outline" id="self-assess" type="button">My answer may also be valid</button>':''}<button class="button" id="next-check" type="button">${s.index+1===data.teaching.questions.length?'See results':'Next question'} →</button></div>`;const self=document.getElementById('self-assess');if(self)self.onclick=()=>{s.self++;self.disabled=true;self.textContent='Marked for your own review';};document.getElementById('next-check').onclick=()=>{s.index++;renderCheck();};}catch(err){if(!form.isConnected)return;button.disabled=false;document.getElementById('check-feedback').textContent=err.message;}};
}

let tutorTurns=[];
function renderTutor(){
  const turns=tutorTurns.map(t=>t.role==='user'?`<article class="word-row"><div><small>YOU</small><strong>${esc(t.text)}</strong></div></article>`:`<article class="word-row"><div><small>CONVERSATION PARTNER</small><strong lang="${languageTag()}">${esc(t.text)}</strong><small>${esc(t.english)}</small></div><div><small>YOU COULD SAY</small><span lang="${languageTag()}">${esc(t.suggestion)}</span><small>${esc(t.suggestion_english)}</small></div>${soundButton(t.reply_speech,t.reply_cyrillic)}</article>`).join('');
  app.innerHTML=`<div class="page">${pageTitle('OPTIONAL AI PRACTICE','Make room for<br><em>conversation.</em>','Start with a greeting or a sentence about your day. The partner replies with an English translation and a suggestion.')}<p class="notice">Messages and recent conversation context are sent to the configured model provider when you press Send. The model can make language mistakes; this chat does not score your ability or update word progress. Chat is kept only in this page session.</p><div class="panel"><div class="word-list">${turns || '<p class="muted">Try “Zdravo! Kako si?” or introduce yourself.</p>'}</div><form id="tutor-form" class="form-grid" style="margin-top:24px"><label for="tutor-message">Your message<textarea id="tutor-message" rows="3" maxlength="600" required></textarea></label><div class="actions"><button class="button" id="tutor-send">Send message →</button><button class="button outline" type="button" id="tutor-clear">New conversation</button></div></form><div id="tutor-feedback" role="status"></div></div><div class="actions"><a class="button outline" href="#dialogues">Read the offline dialogues</a></div></div>`;
  bindSounds();
  document.getElementById('tutor-clear').onclick=()=>{tutorTurns=[];renderTutor();};
  document.getElementById('tutor-form').onsubmit=async e=>{e.preventDefault();const form=e.target,field=document.getElementById('tutor-message'),button=document.getElementById('tutor-send');const message=field.value.trim();if(!message)return;button.disabled=true;document.getElementById('tutor-feedback').textContent='Thinking…';try{const history=[...tutorTurns.map(t=>({role:t.role,text:t.text})),{role:'user',text:message}].slice(-12);const result=await api('tutor',{history});if(!form.isConnected)return;tutorTurns.push({role:'user',text:message},{role:'assistant',text:result.reply,...result});renderTutor();}catch(err){if(!form.isConnected)return;button.disabled=false;document.getElementById('tutor-feedback').textContent=err.message;}};
}

let writingDraft='', writingResult=null;
function renderWriting(){
  app.innerHTML=`<div class="page">${pageTitle('OPTIONAL AI FEEDBACK','Put your words<br><em>on the page.</em>','Write a few lines in the language and ask for a possible correction with an explanation.')}<p class="notice">Your text is sent to the configured model provider when you request feedback. Suggestions can be wrong or change your meaning; check them with a speaker. This page session is not saved and does not change word progress.</p><div class="panel"><form id="writing-form" class="form-grid"><label for="writing-text">Your writing<textarea id="writing-text" rows="7" maxlength="1200" required>${esc(writingDraft)}</textarea></label><div><button class="button" id="writing-send">Request feedback →</button></div></form><div id="writing-feedback" role="status">${writingResult?`<div class="feedback"><strong>Possible correction</strong><p lang="${languageTag()}">${esc(writingResult.corrected)}</p>${soundButton(writingResult.speech,writingResult.speech_cyrillic)}<p>${esc(writingResult.explanation)}</p></div>`:''}</div></div><div class="actions"><a class="button outline" href="#grammar">← Back to the guide</a></div></div>`;
  bindSounds();const form=document.getElementById('writing-form'),field=document.getElementById('writing-text');field.oninput=()=>{writingDraft=field.value;writingResult=null;document.getElementById('writing-feedback').textContent='';};
  form.onsubmit=async e=>{e.preventDefault();const text=field.value.trim(),button=document.getElementById('writing-send');if(!text)return;button.disabled=true;field.disabled=true;document.getElementById('writing-feedback').textContent='Thinking…';try{const result=await api('writing',{text});if(!form.isConnected)return;writingResult=result;renderWriting();}catch(err){if(!form.isConnected)return;button.disabled=false;field.disabled=false;document.getElementById('writing-feedback').textContent=err.message;}};
}

let sourceDraft='',sourcePreview='';
function csvField(value){return '"'+value.replace(/"/g,'""')+'"';}
function renderSources(){
  app.innerHTML=`<div class="page">${pageTitle('LEARN FROM A TEXT','Bring your own<br><em>words.</em>','Paste part of a song, transcript or reading and ask the model to suggest words and meanings.')}<p class="notice">The text is sent to the configured model provider when you request suggestions. The model can misread a phrase or invent a meaning: review and edit every pair before saving. Only the reviewed pairs are saved; the source text remains in this page session.</p><div class="panel"><form id="source-form" class="form-grid"><label for="source-text">Source text<textarea id="source-text" rows="8" maxlength="6000" required>${esc(sourceDraft)}</textarea></label><div><button class="button" id="source-extract">Suggest words →</button></div></form><div id="source-feedback" role="status"></div></div>${sourcePreview?`<div class="panel"><h2>Review before saving</h2><p>One phrase and English meaning per line. Edit or remove anything uncertain.</p><form id="source-save" class="form-grid"><label>Suggested pairs<textarea name="text" rows="10" required>${esc(sourcePreview)}</textarea></label><label>Standard for these pairs<select name="variant">${Object.keys(data.variants).map(v=>`<option value="${v}" ${v===data.settings.variant?'selected':''}>${variantName(v)}</option>`).join('')}</select></label><div><button class="button" id="source-save-button">Save reviewed pairs</button></div><div id="source-save-feedback" role="status"></div></form></div>`:''}<div class="actions"><a class="button outline" href="#words">← Back to words</a></div></div>`;
  const form=document.getElementById('source-form'),field=document.getElementById('source-text');
  field.oninput=()=>{sourceDraft=field.value;sourcePreview='';const preview=document.getElementById('source-save');if(preview)preview.closest('.panel').remove();};
  form.onsubmit=async e=>{e.preventDefault();const text=field.value.trim(),button=document.getElementById('source-extract');if(!text)return;button.disabled=true;field.disabled=true;document.getElementById('source-feedback').textContent='Finding suggestions…';try{const result=await api('extract',{text});if(!form.isConnected)return;sourcePreview=result.entries.map(x=>`${csvField(x.target)},${csvField(x.english)}`).join('\n');renderSources();document.getElementById('source-save').scrollIntoView({behavior:'smooth'});}catch(err){if(!form.isConnected)return;button.disabled=false;field.disabled=false;document.getElementById('source-feedback').textContent=err.message;}};
  const save=document.getElementById('source-save');if(save){const textArea=save.elements.text;textArea.oninput=()=>{sourcePreview=textArea.value;};save.onsubmit=async e=>{e.preventDefault();const button=document.getElementById('source-save-button');button.disabled=true;try{await api('words/import',Object.fromEntries(new FormData(save)));await load();sourceDraft='';sourcePreview='';session=null;go('words');}catch(err){if(!save.isConnected)return;button.disabled=false;document.getElementById('source-save-feedback').textContent=err.message;}};}
}
