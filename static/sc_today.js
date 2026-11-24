'use strict';

// The reference application's Today layout, backed only by this course's activity.
const courseIcons = {
  flame:'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21c3.9 0 6.5-2.5 6.5-6 0-4.2-3.5-5.6-3.5-9.5-2 1-2.8 2.7-2.8 4.3 0 .9-.7 1.5-1.5 1.5S9.2 10.7 9.2 9.6c0-.7.1-1.3.3-1.9C7.4 9.2 5.5 11.6 5.5 15c0 3.5 2.6 6 6.5 6z"/></svg>',
  bolt:'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M13.5 2.5 4.5 13.5h6l-1 8 9-11h-6z"/></svg>',
  book:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19V6a2 2 0 0 1 2-2h12v15H6a2 2 0 0 0-2 2z"/><path d="M8.5 8.5h6M8.5 12h4"/></svg>'
};

function courseSummary() {
  const items=data.items, activity=data.activity || {chain:[],streak_days:0,lesson_answers_today:0};
  const practised=items.filter(i=>i.progress.attempts>0).length;
  const dueCount=items.filter(due).length;
  const todayCount=data.practiced_today;
  const complete=data.authored_lessons.filter(l=>l.completed).length;
  return {items,activity,practised,dueCount,todayCount,complete};
}

function courseStats(s) {
  return `<div class="stat-pill streak${s.activity.streak_days?'':' zero'}" title="Days practised in a row">${courseIcons.flame}<span>${s.activity.streak_days}</span></div><div class="stat-pill xp" title="Card answers today">${courseIcons.bolt}<span>${s.todayCount}</span></div>`;
}

function courseQuest(s) {
  const target=10, current=Math.min(s.todayCount,target), pct=100*current/target;
  return `<div class="rail-head"><h3>Daily quest</h3><span class="rail-link">${current}/${target}</span></div><div class="quest-row"><div class="quest-icon">${courseIcons.bolt}</div><div class="quest-body"><div class="t">Answer ${target} word cards</div><div class="progress-track slim on-light" role="progressbar" aria-label="Daily word-card quest" aria-valuenow="${current}" aria-valuemin="0" aria-valuemax="${target}"><div style="width:${pct}%"></div></div></div></div>`;
}

function renderCourseRail() {
  const s=courseSummary(), rail=document.getElementById('rail'), top=document.getElementById('mobile-stats');
  if(top)top.innerHTML=courseStats(s);
  if(!rail)return;
  const groups=[...new Set(s.items.map(i=>i.theme))].slice(0,4).map(name=>{
    const group=s.items.filter(i=>i.theme===name), done=group.filter(i=>i.progress.attempts>0).length;
    return {name,done,total:group.length,href:`#words?q=${encodeURIComponent(name)}`};
  });
  const library=[{name:'Authored lessons',done:s.complete,total:data.authored_lessons.length,href:'#lessons'},...groups];
  rail.innerHTML=`<div class="rail-stats">${courseStats(s)}</div><div class="rail-card">${courseQuest(s)}</div><div class="rail-card"><div class="rail-head"><h3>Your library</h3><a class="btn ghost sm" href="#words">View all</a></div>${library.map(item=>{const pct=item.total?Math.round(100*item.done/item.total):0;return `<a class="quest-row rail-source" href="${item.href}"><div class="quest-icon" style="background:var(--green-tint);color:var(--green-text)">${courseIcons.book}</div><div class="quest-body"><div class="t" style="margin-bottom:.3rem">${esc(item.name)}</div><div class="progress-track slim on-light" role="progressbar" aria-label="${esc(item.name)} progress" aria-valuenow="${item.done}" aria-valuemin="0" aria-valuemax="${item.total}"><div style="width:${pct}%"></div></div></div></a>`;}).join('')}</div><div class="rail-card"><h3>Words practised</h3><div style="font-size:2rem;font-weight:800;color:var(--blue)">${s.practised}</div><p class="muted">Words and phrases tried in your word bank.</p></div>`;
}

function renderCourseToday() {
  const s=courseSummary(), next=data.recommendation;
  const recommendation=next && data.authored_lessons.find(l=>l.id===next.lesson_id);
  const upcoming=s.items.filter(due).slice(0,5), chain=s.activity.chain || [], active=chain.filter(Boolean).length;
  const greeting=new Date().getHours()<12?'Good morning':new Date().getHours()<18?'Good afternoon':'Good evening';
  app.innerHTML=`<div class="page-head"><div class="eyebrow">${greeting}</div><div class="today-heading"><h1>Today</h1><a class="btn ghost sm" href="#settings">Settings</a></div></div><section class="today-session"><div id="word-map"><h2 class="map-title">You practised ${s.practised} of ${s.items.length} words and phrases</h2><canvas class="map-canvas" role="img" aria-label="Word map: ${s.practised} of ${s.items.length} words and phrases practised. Use the word bank to browse the full list."></canvas><div class="map-next"><span>Next:</span>${upcoming.map(i=>`<a class="map-chip" href="#words?q=${encodeURIComponent(i.target)}" lang="${languageTag()}">${esc(i.target)}</a>`).join('')}</div><a class="map-zoom" href="#words">Show all words and phrases</a></div><div class="eyebrow">Your daily practice</div><h2>Make these words yours.</h2><p>Practise words and phrases at your own pace.</p><a class="btn green block lg" href="#practice">Start your practice</a></section>${recommendation?`<section class="rail-card today-story"><h3>Your next ${next.kind==='review'?'review':'lesson'}</h3><p>${esc(recommendation.title)} · ${esc(next.reason)}</p><a class="btn ghost" href="#lesson/${encodeURIComponent(next.lesson_id)}">Open lesson</a></section>`:''}<div class="today-summary"><span><strong>${s.dueCount}</strong> ready for practice</span><span><strong>${s.todayCount}</strong> word-card answers today</span><span><strong>${s.complete}</strong> lessons complete</span></div><section class="rail-card today-progress" aria-label="Your progress"><div class="rail-head"><h3>Last 4 weeks</h3><span>${active} of ${chain.length} days</span></div><div class="chain" role="img" aria-label="You practised on ${active} of the last ${chain.length} days">${chain.map((on,n)=>`<i class="${on?'on':''}${n===chain.length-1?' today':''}"></i>`).join('')}</div></section><section class="rail-card quest-inline">${courseQuest(s)}</section><h2 class="section-title">Or try</h2><div class="today-actions"><a class="rail-card" href="#talk"><h3>Talk out loud</h3><p class="muted">Have a conversation and get feedback.</p></a><a class="rail-card" href="#lessons"><h3>Follow your course</h3><p class="muted">Short lessons adapt to your answers.</p></a><a class="rail-card" href="#vocabulary"><h3>Explore ranked words</h3><p class="muted">Browse the 2,000-word reference.</p></a><a class="rail-card" href="#grammar"><h3>Guide to the language</h3><p class="muted">Sounds, scripts and useful patterns.</p></a></div>`;
  drawCourseMap(app.querySelector('.map-canvas'),s.items,upcoming);
}

function drawCourseMap(canvas,items,upcoming) {
  if(!canvas || !items.length)return;
  const size=canvas.clientWidth, ratio=window.devicePixelRatio||1, center=size/2;
  canvas.width=canvas.height=Math.round(size*ratio);
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);
  const scale=(center-6)/Math.sqrt(items.length+.5), angle=Math.PI*(3-Math.sqrt(5));
  const positions=items.map((item,n)=>{const r=scale*Math.sqrt(n+.5),a=n*angle;return {x:center+r*Math.cos(a),y:center+r*Math.sin(a)};});
  const nextIds=new Set(upcoming.map(item=>item.id));
  items.forEach((item,n)=>{const p=positions[n];ctx.fillStyle=nextIds.has(item.id)?'#89e219':item.progress.attempts>0?'#ffc800':'rgba(255,255,255,.2)';ctx.beginPath();ctx.arc(p.x,p.y,Math.max(.9,scale*.6),0,Math.PI*2);ctx.fill();});
  canvas.onclick=e=>{const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)*size/rect.width,y=(e.clientY-rect.top)*size/rect.height;let best=-1,dist=Math.max(scale*2,18)**2;positions.forEach((p,n)=>{const d=(p.x-x)**2+(p.y-y)**2;if(d<dist){best=n;dist=d;}});if(best>=0)location.hash=`words?q=${encodeURIComponent(items[best].target)}`;};
}
