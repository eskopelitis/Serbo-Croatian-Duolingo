// Exercise lesson navigation and answer submission with a small authored fixture.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('authored lesson renders, submits, and offers the next suggestion', async () => {
  const nodes = {};
  const app = {innerHTML:''};
  const lesson = {id:'hello', level:'A0', order:1, title:'Hello', objective:'Greet',
    teaching_note:'Say hello.', examples:[{target:'Dobar dan', english:'Good day', speech:'Dobar dan'}],
    exercises:[{id:'one', kind:'short_text', prompt:'Say hello'}]};
  const requests = [];
  const context = vm.createContext({app, console, location:{hash:'#lesson/hello'},
    window:{crypto:{randomUUID:()=> 'attempt-12345678'}}, crypto:{randomUUID:()=> 'attempt-12345678'},
    document:{getElementById:id=>nodes[id] ||= {isConnected:true, querySelectorAll:()=>[], remove(){}}},
    FormData:class {get(){return 'Dobar dan';}},
    data:{authored_lessons:[{id:'hello',level:'A0',order:1,title:'Hello',objective:'Greet',unlocked:true}],
          recommendation:{lesson_id:'hello',kind:'lesson',reason:'Start here.'}},
    api:async (path, body)=>{requests.push({path,body});return body?{correct:true,feedback:'Well done.',expected:['Dobar dan']}:{lesson};},
    load:async()=>{}, pageTitle:(a,b,c)=>`${a} ${b} ${c}`, esc:s=>String(s ?? ''),
    languageTag:()=> 'sr-Latn', soundButton:()=>'', bindSounds:()=>{}
  });
  vm.runInContext(fs.readFileSync('static/sc_learning.js','utf8'),context);
  await context.renderAuthoredLesson('hello');
  assert.match(app.innerHTML,/Say hello/);
  await nodes['lesson-answer'].onsubmit({preventDefault(){}});
  assert.deepEqual(JSON.parse(JSON.stringify(requests[1].body)),
    {lesson_id:'hello',exercise_id:'one',answer:'Dobar dan',attempt_id:'attempt-12345678'});
  assert.match(nodes['lesson-feedback'].innerHTML,/That’s right/);
  nodes['lesson-next'].onclick();
  assert.match(app.innerHTML,/See your next suggestion/);
  context.renderLessons();
  assert.match(app.innerHTML,/#lesson\/hello/);
  assert.match(app.innerHTML,/class="node /);
});
