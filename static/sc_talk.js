'use strict';
// A spoken, turn-based conversation. Audio goes to the local speech recognizer;
// only the transcript and conversation context go to the configured model.
let scTalk = null, scTalkGeneration = 0;
function scTalkLeave(){
  scTalkGeneration++;
  if(scTalk?.timer)clearTimeout(scTalk.timer);
  if(scTalk?.recorder && scTalk.recorder.state!=='inactive')scTalk.recorder.stop();
  scTalk?.stream?.getTracks().forEach(track=>track.stop());
  if(window.speechSynthesis)window.speechSynthesis.cancel();
  if(playingAudio){playingAudio.pause();playingAudio=null;}
  scTalk=null;
}
window.addEventListener('pagehide',scTalkLeave);
function renderScTalk(){
  if(!scTalk){app.innerHTML=`<div class="page">${pageTitle('CONVERSATION PRACTICE','Talk out loud.','Have a short conversation and get feedback at the end.')}<div class="panel"><p>Your recording is transcribed locally. The transcript and conversation are sent to the configured AI provider. The feedback is an estimate and may contain mistakes.</p><p>${esc(voiceInfo())}</p><button class="button" id="talk-start">Start conversation →</button></div><div class="actions"><a class="button outline" href="#today">← Back to Today</a></div></div>`;document.getElementById('talk-start').onclick=scTalkStart;return;}
  const t=scTalk, busy=t.busy, turn=t.turn;
  if(t.grade){app.innerHTML=`<div class="page">${pageTitle('CONVERSATION FEEDBACK',`${esc(t.grade.score)} / 100`,'A guide to what you can practise next.')}<div class="panel"><h2>What went well</h2><ul>${t.grade.strengths.map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Keep practising short replies.</li>'}</ul><h2>Try next time</h2><ul>${t.grade.fixes.map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Keep the conversation going.</li>'}</ul></div><div class="actions"><button class="button" id="talk-again">Start another conversation</button><a class="button outline" href="#today">Back to Today</a></div></div>`;document.getElementById('talk-again').onclick=()=>{scTalkLeave();renderScTalk();};return;}
  app.innerHTML=`<div class="page">${pageTitle('CONVERSATION PRACTICE','Talk out loud.','Listen, speak or type, then finish for feedback.')}<div class="talk-live"><div class="talk-live-head"><span>${t.history.filter(x=>x.role==='user').length} replies</span><button class="button outline" id="talk-finish" ${busy||!t.history.some(x=>x.role==='user')?'disabled':''}>Finish and score</button></div><div class="talk-partner"><div class="eyebrow">YOUR PARTNER</div><p class="talk-live-reply" lang="${languageTag()}">${esc(turn?.reply || 'Starting conversation…')}</p>${turn?`<p>${esc(turn.translation)}</p><button class="button outline" id="talk-listen">Listen again</button>`:''}</div>${turn?.correction?`<p class="feedback">${esc(turn.correction)}</p>`:''}${turn?.suggestions?.length?`<div class="talk-hints"><div class="eyebrow">YOU COULD SAY</div>${turn.suggestions.map((hint,i)=>`<button class="talk-hint" type="button" data-talk-hint="${i}"><strong lang="${languageTag()}">${esc(hint.target)}</strong><span>${esc(hint.english)}</span></button>`).join('')}</div>`:''}<p role="status" id="talk-status">${esc(t.status||'')}</p>${turn?`<div class="actions"><button class="button" id="talk-record" ${busy&&!t.recording?'disabled':''}>${t.recording?'Stop recording':'Speak your reply'}</button></div><form id="talk-form" class="form-grid"><label for="talk-text">${t.heard?'Check what was heard, then send':'Or type your reply'}<input class="field" id="talk-text" maxlength="600" value="${esc(t.heard||'')}" required autocomplete="off"></label><div><button class="button outline" ${busy?'disabled':''}>Send reply →</button></div></form>`:''}</div><div class="actions"><a class="button outline" href="#today">End without scoring</a></div></div>`;
  if(turn){document.getElementById('talk-listen').onclick=()=>speak(convertTalkSpeech(turn.reply),turn.reply);document.getElementById('talk-record').onclick=t.recording?scTalkStop:scTalkRecord;document.getElementById('talk-form').onsubmit=e=>{e.preventDefault();scTalkSend(document.getElementById('talk-text').value);};app.querySelectorAll('[data-talk-hint]').forEach(b=>b.onclick=()=>{const text=turn.suggestions[Number(b.dataset.talkHint)].target;speak(convertTalkSpeech(text),text);});}
  document.getElementById('talk-finish').onclick=scTalkFinish;
}
// The server has already applied the selected script; the voice helper accepts both.
function convertTalkSpeech(text){return text;}
async function scTalkStart(){
  const generation=++scTalkGeneration;
  scTalk={history:[],turn:null,busy:true,status:'Starting conversation…',heard:'',grade:null};renderScTalk();
  try{const turn=await api('talk/turn',{history:[]});if(generation!==scTalkGeneration)return;scTalk.turn=turn;scTalk.history.push({role:'assistant',text:turn.reply});scTalk.busy=false;scTalk.status='Listen to your partner, then reply.';renderScTalk();speak(convertTalkSpeech(turn.reply),turn.reply);}
  catch(e){if(generation!==scTalkGeneration)return;scTalk=null;renderScTalk();const panel=app.querySelector('.panel');panel.insertAdjacentHTML('beforeend',`<p role="alert">${esc(e.message)}</p>`);}
}
async function scTalkSend(text){
  const t=scTalk, generation=scTalkGeneration; text=text.trim();if(!text||t.busy)return;
  t.busy=true;t.status='Thinking…';t.heard=text;renderScTalk();
  try{const history=[...t.history,{role:'user',text,spoken:!!t.transcribed}];const turn=await api('talk/turn',{history});if(generation!==scTalkGeneration)return;t.history=[...history,{role:'assistant',text:turn.reply}];t.turn=turn;t.heard='';t.transcribed=false;t.busy=false;t.status='Your turn.';renderScTalk();speak(convertTalkSpeech(turn.reply),turn.reply);}
  catch(e){if(generation!==scTalkGeneration)return;t.busy=false;t.status=e.message;renderScTalk();}
}
async function scTalkFinish(){
  const t=scTalk,generation=scTalkGeneration;if(t.busy)return;t.busy=true;t.status='Preparing feedback…';renderScTalk();
  try{const grade=await api('talk/grade',{history:t.history});if(generation!==scTalkGeneration)return;t.grade=grade;t.busy=false;renderScTalk();}
  catch(e){if(generation!==scTalkGeneration)return;t.busy=false;t.status=e.message;renderScTalk();}
}
async function scTalkRecord(){
  const t=scTalk,generation=scTalkGeneration;if(t.busy)return;
  if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){t.status='Microphone access needs HTTPS or localhost. Type your reply instead.';renderScTalk();return;}
  t.busy=true;t.status='Opening microphone…';renderScTalk();let stream;
  try{stream=await navigator.mediaDevices.getUserMedia({audio:true});if(generation!==scTalkGeneration){stream.getTracks().forEach(x=>x.stop());return;}const recorder=new MediaRecorder(stream);t.stream=stream;t.recorder=recorder;t.chunks=[];recorder.ondataavailable=e=>{if(e.data.size)t.chunks.push(e.data);};recorder.start();t.recording=true;t.status='Listening. Stop when you finish.';t.timer=setTimeout(scTalkStop,20000);renderScTalk();}
  catch(e){stream?.getTracks().forEach(x=>x.stop());if(generation!==scTalkGeneration)return;t.busy=false;t.status='Microphone unavailable. Type your reply instead.';renderScTalk();}
}
async function scTalkStop(){
  const t=scTalk,generation=scTalkGeneration;if(!t?.recording)return;t.recording=false;clearTimeout(t.timer);t.status='Transcribing…';renderScTalk();
  try{const blob=await new Promise(resolve=>{t.recorder.onstop=()=>resolve(new Blob(t.chunks,{type:t.recorder.mimeType}));t.recorder.stop();});t.stream.getTracks().forEach(x=>x.stop());const wav=await scTalkWav(blob);const form=new FormData();form.append('audio',wav,'speech.wav');form.append('prompt',t.turn.reply);const response=await fetch('/api/sc/talk/transcribe',{method:'POST',body:form});const result=await response.json();if(!response.ok){if(response.status===503)openSetup('Speech recognition needs setup. You can type instead.');throw Error(result.error||'Transcription failed.');}if(generation!==scTalkGeneration)return;t.heard=result.text;t.transcribed=true;t.busy=false;t.status='Check the transcription before sending.';renderScTalk();}
  catch(e){t.stream?.getTracks().forEach(x=>x.stop());if(generation!==scTalkGeneration)return;t.busy=false;t.status=e.message||'Could not transcribe. Type your reply instead.';renderScTalk();}
}
async function scTalkWav(blob){
  const AudioCtx=window.AudioContext||window.webkitAudioContext, ctx=new AudioCtx();let decoded;try{decoded=await ctx.decodeAudioData(await blob.arrayBuffer());}finally{await ctx.close();}
  const off=new OfflineAudioContext(1,Math.ceil(decoded.duration*16000),16000),src=off.createBufferSource();src.buffer=decoded;src.connect(off.destination);src.start();const pcm=(await off.startRendering()).getChannelData(0),buf=new ArrayBuffer(44+pcm.length*2),view=new DataView(buf),str=(at,s)=>[...s].forEach((c,i)=>view.setUint8(at+i,c.charCodeAt(0)));
  str(0,'RIFF');view.setUint32(4,36+pcm.length*2,true);str(8,'WAVEfmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);str(36,'data');view.setUint32(40,pcm.length*2,true);for(let i=0;i<pcm.length;i++){const s=Math.max(-1,Math.min(1,pcm[i]));view.setInt16(44+i*2,s<0?s*0x8000:s*0x7fff,true);}return new Blob([buf],{type:'audio/wav'});
}
