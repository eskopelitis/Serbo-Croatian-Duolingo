'use strict';
// Credentials stay in this form only until submission; they are never stored in the browser.
let setupDialog, setupTimer, voiceInstalling=false, voiceWatch;
// With the dialog closed, keep reporting the voice download in the page's status line.
function watchVoiceInstall(){
  clearTimeout(voiceWatch);
  voiceWatch=setTimeout(async()=>{
    if(setupDialog?.open)return; // the dialog shows its own progress bar
    const line=document.getElementById('speech-status');
    try{
      const s=await setupRequest('status');
      voiceInstalling=s.install==='running';
      if(voiceInstalling){line.textContent=`Downloading the Serbian voice… ${s.progress||0}%`;watchVoiceInstall();}
      else if(s.install==='done'&&s.voice_available){piperVoice=await api('voice');line.textContent='The Serbian voice is ready.';}
      else if(s.install==='failed')line.textContent='The voice download failed. Open Settings → AI & speech setup to retry.';
    }catch{watchVoiceInstall();}
  },3000);
}
async function setupRequest(path, body={}){
  const response=await fetch('/api/setup/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Local-Setup':'1'},body:JSON.stringify(body),cache:'no-store'});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Setup is unavailable.');return result;
}
function openSetup(reason=''){
  if(!setupDialog){
    setupDialog=document.createElement('dialog');setupDialog.className='setup-dialog';
    setupDialog.setAttribute('aria-labelledby','setup-title');
    setupDialog.innerHTML=`<div class="setup-head"><div><div class="eyebrow">YOUR LEARNING SPACE</div><h2 id="setup-title">Make it yours.</h2><p>Set up what you need now. You can return to this any time.</p></div><button class="setup-close" type="button" aria-label="Close setup">×</button></div><p class="setup-message" id="setup-message" role="status"></p><div id="setup-content" aria-live="polite"><p>Checking this computer…</p></div><div class="actions"><button class="button outline" id="setup-skip" type="button">Continue without setup</button></div>`;
    document.body.appendChild(setupDialog);
    setupDialog.querySelector('.setup-close').onclick=()=>setupDialog.close();
    setupDialog.querySelector('#setup-skip').onclick=()=>setupDialog.close();
    setupDialog.addEventListener('close',()=>{clearTimeout(setupTimer);const field=setupDialog.querySelector('#setup-key');if(field)field.value='';if(voiceInstalling)watchVoiceInstall();});
  }
  if(!setupDialog.open)setupDialog.showModal();
  setupDialog.querySelector('#setup-message').textContent=reason;
  setupDialog.querySelector('#setup-content').innerHTML='<p>Checking this computer…</p>';
  refreshSetup();
}
async function refreshSetup(){
  clearTimeout(setupTimer);const content=setupDialog.querySelector('#setup-content');
  if(content.querySelector('#setup-key')?.value){setupTimer=setTimeout(refreshSetup,2000);return;}
  try{
    const s=await setupRequest('status');if(!setupDialog.open)return;
    if(content.querySelector('#setup-key')?.value){setupTimer=setTimeout(refreshSetup,2000);return;}
    content.innerHTML=`<section class="setup-section"><div class="setup-row"><div><div class="eyebrow">AI CONVERSATION & FEEDBACK</div><h3>Conversation partner</h3></div><span class="setup-badge">${s.ai_configured?'Configured':s.local_ai_available?'Local AI ready':'Needs setup'}</span></div><p>${s.ai_configured?'A DeepSeek key is saved or configured. Its connection has not been checked.':s.local_ai_available?'Your local AI is available. A DeepSeek key is optional.':'Add a DeepSeek API key, or use an available local AI model.'} Your conversation text is sent to the configured provider.</p><form id="setup-key-form"><label for="setup-key">${s.ai_configured?'Replace API key':'DeepSeek API key'}</label><div class="setup-key-row"><input id="setup-key" type="password" class="field" autocomplete="off" spellcheck="false" required minlength="16" maxlength="256"><button class="button" type="submit">Save key</button></div><p class="setup-hint">Saved on this computer. We never display the key after saving.</p></form><p id="setup-key-status" role="status"></p></section><section class="setup-section"><div class="setup-row"><div><div class="eyebrow">OPTIONAL LISTENING</div><h3>Serbian voice</h3></div><span class="setup-badge">${s.voice_available?'Ready':'Optional'}</span></div><p>${s.voice_available?'Marko is installed on this computer.':'Install Marko, a local Serbian voice (about 64 MB), or use a matching system voice in Settings.'}</p>${!s.voice_available&&s.voice_install_supported&&s.install==='running'?`<progress class="setup-progress" max="100" value="${s.progress||0}" aria-label="Serbian voice download"></progress><p class="setup-hint">Downloading… ${s.progress||0}%. You can close this window. The download keeps going in the background.</p>`:!s.voice_available&&s.voice_install_supported?`<button class="button outline" id="setup-voice" type="button">${s.install==='failed'?'Retry voice download':'Download Serbian voice'}</button>`:!s.voice_available?'<p class="setup-hint">Your voice uses a custom path or the Piper package is missing. Follow the voice setup instructions in README.</p>':''}${s.install==='failed'?'<p role="alert">The download could not be installed. Check your connection and retry; existing files were preserved.</p>':''}</section><section class="setup-section"><div class="setup-row"><div><div class="eyebrow">OPTIONAL SPEAKING</div><h3>Speech recognition</h3></div><span class="setup-badge">${s.recognition_available?'Installed':'Optional'}</span></div><p>${s.recognition_available?'The local speech recognition files are installed; they may take a moment to start.':'To speak a reply, install CrispASR and a Whisper model using the instructions in README. You can always type instead.'}</p></section>`;
    const form=content.querySelector('#setup-key-form');form.onsubmit=async event=>{event.preventDefault();const input=content.querySelector('#setup-key'),button=form.querySelector('button'),status=content.querySelector('#setup-key-status');button.disabled=true;status.textContent='Saving…';try{await setupRequest('key',{key:input.value});input.value='';await refreshSetup();setupDialog.querySelector('#setup-message').textContent='Key saved. Retry your AI feature when ready.';}catch(e){input.value='';button.disabled=false;status.textContent=e.message;}};
    const voice=content.querySelector('#setup-voice');if(voice)voice.onclick=async()=>{voice.disabled=true;try{await setupRequest('voice');await refreshSetup();}catch(e){voice.disabled=false;setupDialog.querySelector('#setup-message').textContent=e.message;}};
    voiceInstalling=s.install==='running';
    if(voiceInstalling)setupTimer=setTimeout(refreshSetup,2000);
    if(s.install==='done' && s.voice_available){piperVoice=await api('voice');}
  }catch(error){if(!setupDialog.open)return;content.innerHTML='<section class="setup-section"><h3>Setup on your computer</h3><p>Open this app on the computer running it at <strong>localhost</strong> to configure the AI key or install a voice. You can continue using the course here.</p></section>';}
}
