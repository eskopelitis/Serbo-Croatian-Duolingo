const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup() {
  const status = {textContent: ''}, spoken = [], requests = [];
  const browserVoice = {name:'Serbian', lang:'sr-RS', voiceURI:'browser-sr'};
  const context = {document:{getElementById:id=>id==='speech-status'?status:{}, querySelectorAll:()=>[]},
    window:{speechSynthesis:{cancel(){},speak:u=>spoken.push(u)}}, localStorage:{getItem:()=>null},
    SpeechSynthesisUtterance:function(text){this.text=text;},
    URL:{createObjectURL:()=> 'blob:voice',revokeObjectURL(){}},
    Audio:function(){this.play=async()=>{};this.pause=()=>{};},
    fetch:async (url,options)=>{requests.push({url,options});return {ok:true,blob:async()=>({})};}};
  vm.createContext(context);
  const source=fs.readFileSync('static/sc.js','utf8').split("window.addEventListener('hashchange'")[0];
  vm.runInContext(source+"\ndata={settings:{variant:'sr',script:'cyrillic'}}; voices=[{name:'Serbian',lang:'sr-RS',voiceURI:'browser-sr'}]; piperVoice={available:true}; chosenVoice=PIPER;",context);
  return {context,status,spoken,requests,browserVoice};
}

test('local Serbian voice uses selected script and sends a playback request',async()=>{
  const {context,requests}=setup();
  await vm.runInContext("speak('Dobar dan', 'Добар дан')",context);
  assert.equal(requests[0].url,'/api/sc/tts');
  assert.equal(JSON.parse(requests[0].options.body).text,'Добар дан');
  assert.match(vm.runInContext('voiceInfo()',context),/Local Serbian voice/);
});

test('local voice is the default while an explicitly selected browser voice is respected',()=>{
  const {context}=setup();
  vm.runInContext('chosenVoice=null',context);
  assert.equal(vm.runInContext('usePiper()',context),true);
  vm.runInContext("chosenVoice='browser-sr'",context);
  assert.equal(vm.runInContext('usePiper()',context),false);
  vm.runInContext("chosenVoice='no-longer-installed'",context);
  assert.equal(vm.runInContext('usePiper()',context),true);
});

test('unavailable local synthesis announces and uses the browser voice',async()=>{
  const {context,status,spoken}=setup();
  context.fetch=async()=>({ok:false});
  await vm.runInContext("speak('Dobar dan', 'Добар дан')",context);
  assert.equal(spoken[0].text,'Dobar dan');
  assert.match(status.textContent,/using your browser voice/);
});

test('missing voices open setup and a local failure is announced',async()=>{
  const {context,status}=setup();
  let opened=false; context.openSetup=()=>{opened=true;};
  vm.runInContext('voices=[]; piperVoice={available:false}',context);
  assert.equal(vm.runInContext('canSpeak()',context),false);
  assert.doesNotMatch(vm.runInContext("soundButton('Dobar dan','Добар дан')",context),/disabled/);
  await vm.runInContext("speak('Dobar dan','Добар дан')",context);
  assert.equal(opened,true);
  vm.runInContext('piperVoice={available:true}',context);
  context.fetch=async()=>({ok:false});
  await vm.runInContext("speak('Dobar dan','Добар дан')",context);
  assert.match(status.textContent,/Local Serbian voice unavailable/);
});

test('newer playback prevents an older pending response from playing',async()=>{
  const {context}=setup(); let resolveFirst, plays=0, calls=0;
  context.Audio=function(){this.play=async()=>{plays++};this.pause=()=>{};};
  context.fetch=()=>++calls===1 ? new Promise(resolve=>{resolveFirst=resolve}) : Promise.resolve({ok:true,blob:async()=>({})});
  const first=vm.runInContext("speak('first')",context);
  await vm.runInContext("speak('second')",context);
  resolveFirst({ok:true,blob:async()=>({})}); await first;
  assert.equal(plays,1);
});
