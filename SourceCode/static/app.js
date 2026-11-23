const COL = {healthy:'#34d399', watch:'#fbbf24', high:'#fb923c', critical:'#f43f5e'};
const NAME = {healthy:'Healthy', watch:'Watch', high:'High risk', critical:'Critical'};
const STEPS = [
  {l:'What is happening?', q:'Live readings for this parameter, last 7 days, against its limits.'},
  {l:'What is abnormal?', q:"Behaviour that deviates from this station's own healthy baseline."},
  {l:'What is likely to happen?', q:'A predicted risk score with a defined time window.'},
  {l:'Why does the AI think this?', q:'The signals and dimensions driving the score.'},
  {l:'What should the field team do?', q:'A prioritised checklist, not just a number.'}];
const S = {fleet:null, st:null, param:null, step:0, chart:null, hist:null};
const $ = id => document.getElementById(id);
const f = (v,d=1) => v==null ? '-' : Number(v).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});
const when = (ms,o) => new Date(ms).toLocaleString('en-GB', o || {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false});
Chart.defaults.font.family = '"IBM Plex Sans", sans-serif'; Chart.defaults.font.size = 11; Chart.defaults.color = '#8fa3c4';

async function init(){
  S.fleet = await (await fetch('/api/fleet')).json();
  const F = S.fleet;
  renderKpis(); renderQueue();
  $('prev').onclick = () => go(S.step-1); $('next').onclick = () => go(S.step+1);
  addEventListener('keydown', e => { if(e.key==='ArrowRight') go(S.step+1); if(e.key==='ArrowLeft') go(S.step-1); });
  await pick(F.assets[0].id);
}

function renderKpis(){
  const A = S.fleet.assets, M = S.fleet.metrics;
  const act = A.filter(a=>['high','critical'].includes(a.status)), watch = A.filter(a=>a.status==='watch');
  const soon = A.filter(a=>a.eta!=null && a.status!=='healthy').sort((a,b)=>a.eta-b.eta)[0];
  $('kpis').innerHTML = `
   <div class="kpi ${act.length?'hot':''}"><div class="lbl">Stations needing action</div><div class="big">${act.length}<small>of ${A.length}</small></div><p>${watch.length} more on watch</p></div>
   <div class="kpi"><div class="lbl">Earliest predicted breach</div><div class="big">${soon?soon.eta:'-'}<small>${soon?'hours':''}</small></div><p>${soon? soon.area+' · '+soon.top_label : 'None in the next 10 days'}</p></div>
   <div class="kpi"><div class="lbl">Abnormal parameters now</div><div class="big">${A.reduce((s,a)=>s+a.n_abnormal,0)}<small>of ${A.length*12}</small></div><p>Outside their own baseline</p></div>
   <div class="kpi"><div class="lbl">Breaches the model caught</div><div class="big">${Math.round(M.recall*100)}<small>%</small></div><p>Median warning ${M.median_lead_h ?? '-'} h ahead, on unseen data</p></div>`;
}

function renderQueue(){
  $('queue').innerHTML = S.fleet.assets.map(a => `
   <button class="qi ${a.status}" data-id="${a.id}" aria-pressed="${S.st && S.st.id===a.id}">
     <b>${f(a.risk,0)}</b><span class="t">${a.area}</span><span class="e">${a.eta!=null && a.status!=='healthy' ? a.eta+' h' : NAME[a.status]}</span>
     <span class="s">${a.status==='healthy' ? a.id+' · no action needed' : a.id+' · '+a.top_label}</span></button>`).join('');
  document.querySelectorAll('.qi').forEach(b => b.onclick = () => pick(b.dataset.id));
}


async function pick(id, param, step){
  S.st = await (await fetch('/api/station/'+id)).json();
  S.param = param || S.st.top_param;
  if(step!=null) S.step = step;
  renderQueue(); renderBrief(); renderPickers(); renderSteps(); renderStage(); renderHistory();
}

function renderBrief(){
  const s = S.st, c = COL[s.status], C = 2*Math.PI*56;
  $('brief').className = 'brief '+s.status;
  $('brief').innerHTML = `<div><span class="tag"><i class="d ${s.status}"></i>${NAME[s.status]} · ${s.id}</span>
    <h1>${s.headline}</h1><div class="sub">${s.name}, ${s.area} ${s.pin} · ${s.kind}</div>
    <div class="facts"><div>Act by<b>${s.due || 'No action needed'}</b></div><div>Parameters needing attention<b>${s.n_watch} of 12</b></div>
    <div>Abnormal now<b>${s.n_abnormal}</b></div><div>Multi-signal anomaly, 24 h<b>${f(s.anomaly_share,0)} %</b></div></div></div>
    <div class="ring" role="img" aria-label="Risk score ${s.risk} of 100"><svg viewBox="0 0 132 132"><circle cx="66" cy="66" r="56" fill="none" stroke="#1b2a49" stroke-width="12"/>
    <circle cx="66" cy="66" r="56" fill="none" stroke="${c}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C*(1-Math.max(s.risk,3)/100)}"/></svg>
    <div class="v"><b>${f(s.risk,0)}</b><span>risk /100</span></div></div>`;
}

function renderPickers(){
  const order = ['critical','high','watch','healthy'], P = Object.values(S.st.params).sort((a,b)=>order.indexOf(a.status)-order.indexOf(b.status)||b.risk-a.risk);
  $('pickers').innerHTML = P.map(p=>`<button class="chip ${p.status}" data-k="${p.key}" aria-pressed="${p.key===S.param}"><i></i>${p.label}</button>`).join('');
  document.querySelectorAll('.chip').forEach(b => b.onclick = () => {S.param=b.dataset.k; renderPickers(); renderStage(); renderHistory();});
}
function renderSteps(){
  $('steps').innerHTML = STEPS.map((s,i)=>`<li class="${i<S.step?'done':''} ${i===S.step?'on':''}"><button class="sb" data-i="${i}" aria-current="${i===S.step}"><span class="n">${i<S.step?'✓':i+1}</span><span class="l">${s.l}</span></button></li>`).join('');
  document.querySelectorAll('.sb').forEach(b => b.onclick = () => go(+b.dataset.i));
  $('prev').disabled = S.step===0; $('next').disabled = S.step===4; $('stepno').textContent = `Step ${S.step+1} of 5`;
}
function go(i){ if(i<0||i>4||!S.st) return; S.step=i; renderSteps(); renderStage(); }

/* ---------- chart helpers ---------- */
const GRID='rgba(148,170,205,.10)';
function chartOpts(){ return {responsive:true,maintainAspectRatio:false,animation:{duration:450},interaction:{mode:'index',intersect:false},
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#e7eefb',titleColor:'#070d18',bodyColor:'#070d18',padding:9}},
  scales:{x:{grid:{color:GRID},ticks:{maxTicksLimit:7,maxRotation:0}},y:{grid:{color:GRID}}}}; }
const ln = (label,data,color,o={}) => ({label,data,borderColor:color,backgroundColor:color,borderWidth:o.w||2,pointRadius:0,tension:.25,...o});
const flat = (n,v,color,label) => ({label,data:Array(n).fill(v),borderColor:color,borderWidth:1.3,borderDash:[6,4],pointRadius:0});
function draw(cfg){ if(S.chart) S.chart.destroy(); const c=$('sc'); if(c) S.chart=new Chart(c,cfg); }

/* ---------- the five stages ---------- */
function renderStage(){
  const s=S.st, p=s.params[S.param], c=COL[p.status], u=p.unit, d=p.dec, T=STEPS[S.step];
  const head = `<div><h2>${T.l}</h2><p class="q">${T.q} <b>${p.label}</b>, ${s.area}.</p>`;
  const st = $('stage');
  if(S.chart){ S.chart.destroy(); S.chart=null; }
  if(S.step===0){
    const L=p.live, n=L.t.length;
    st.innerHTML = `${head}<div class="cv"><canvas id="sc"></canvas></div></div>
      <div class="side" style="--c:${c}"><div class="lab">Now</div><div class="num">${f(p.current,d)} <small>${u}</small></div>
      <div><div class="lab">Safety margin used: ${f(p.margin_used,0)} %</div><div class="gauge"><i style="width:${Math.min(100,Math.max(2,p.margin_used))}%"></i><s style="left:70%"></s></div><div class="lab">Warn at 70 %, critical at 100 %</div></div>
      <ul class="story"><li>Critical limit: ${f(p.crit,d)} ${u}. Warning level: ${f(p.warn,d)} ${u}.</li><li>Typical for this hour: ${f(p.expected,d)} ${u}.</li><li><span class="flag" style="--c:${c}">${NAME[p.status]}</span></li></ul></div>`;
    draw({type:'line',data:{labels:L.t.map(t=>when(t,{day:'2-digit',month:'short'})),datasets:[ln('Reading',L.v,'#38e1c8',{w:1.6}),flat(n,p.warn,'#fbbf24','Warn'),flat(n,p.crit,'#f43f5e','Critical')]},options:chartOpts()});
  }
  if(S.step===1){
    const L=p.live, k=72, o=L.t.length-k, sl=a=>a.slice(o), out=sl(L.v).map((v,i)=>p.sign*(v-(p.sign>0?sl(L.hi)[i]:sl(L.lo)[i]))>0);
    st.innerHTML = `${head}<div class="cv"><canvas id="sc"></canvas></div></div>
      <div class="side" style="--c:${p.abnormal?'#f43f5e':'#34d399'}"><div class="lab">Deviation from own baseline</div><div class="num">${p.z>=0?'+':''}${f(p.z,1)} <small>σ</small></div>
      <div><span class="flag" style="--c:${p.abnormal?'#f43f5e':Math.abs(p.z)>=2?'#fbbf24':'#34d399'}">${p.abnormal?'Outside baseline':Math.abs(p.z)>=2?'Edge of baseline':'Inside baseline'}</span></div>
      <ul class="story">${p.insights.slice(0,p.abnormal?2:1).map(t=>`<li>${t}</li>`).join('')}</ul>
      <div class="lab">Shaded band = normal range (±3σ) learned from this station's first 3 weeks. Red dots fall outside it.</div></div>`;
    draw({type:'line',data:{labels:sl(L.t).map(t=>when(t,{day:'2-digit',month:'short',hour:'2-digit',hour12:false})),datasets:[
      {label:'Upper',data:sl(L.hi),borderColor:'rgba(251,191,36,.45)',borderWidth:1,borderDash:[4,3],pointRadius:0,fill:false},
      {label:'Lower',data:sl(L.lo),borderColor:'rgba(251,191,36,.45)',borderWidth:1,borderDash:[4,3],pointRadius:0,fill:'-1',backgroundColor:'rgba(251,191,36,.12)'},
      ln('Own baseline',sl(L.mu),'rgba(251,191,36,.85)',{w:1}),
      {...ln('Reading',sl(L.v),'#e7eefb',{w:1.8}),pointRadius:out.map(x=>x?3.5:0),pointBackgroundColor:'#f43f5e',pointBorderColor:'#f43f5e'}]},options:chartOpts()});
  }
  if(S.step===2){
    const L=p.live, F=p.forecast, back=48, hv=L.v.slice(-back), pad=n=>Array(n).fill(null), N=back+F.t.length;
    const e1=p.eta_early ?? p.eta, e2=p.eta_late ?? p.eta, ok=p.trend_significant && p.eta!=null, pos=h=>100*Math.min(h,240)/240;
    const when2 = p.breached ? 'The limit has already been crossed.' : ok ? `Expected to cross ${f(p.crit,d)} ${u} around <b>${when(S.fleet.now+p.eta*3600e3,{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:false})}</b>, about ${p.eta} h from now.` : 'No statistically significant drift, so no crossing is projected in the next 10 days.';
    st.innerHTML = `${head}<div class="cv"><canvas id="sc"></canvas></div></div>
      <div class="side" style="--c:${c}"><div class="lab">Chance of crossing the limit within 48 h</div><div class="num">${f(p.risk,0)}<small> %</small></div>
      <p style="font-size:.88rem;color:#c9d6ee">${when2}</p>
      <div class="win"><div class="lab">Risk window${ok?`: ${e1} h to ${e2 ?? '240+'} h`:''}</div><div class="track">${ok?`<div class="seg" style="left:${pos(e1)}%;width:${Math.max(pos(e2??240)-pos(e1),2.5)}%"></div>`:''}<div class="nowm"></div></div>
      <div class="ticks"><span>Now</span><span>48 h</span><span>5 days</span><span>10 days</span></div></div>
      <div class="lab">Window uses the 80 % confidence range of the current drift${ok?` (${f(Math.abs(p.drift_per_day),d+1)} ${u} per day)`:''}.</div></div>`;
    draw({type:'line',data:{labels:L.t.slice(-back).concat(F.t).map(t=>when(t,{day:'2-digit',month:'short',hour:'2-digit',hour12:false})),datasets:[
      {label:'Upper',data:pad(back).concat(F.hi),borderColor:'transparent',pointRadius:0,fill:false},
      {label:'Likely range',data:pad(back).concat(F.lo),borderColor:'transparent',pointRadius:0,fill:'-1',backgroundColor:'rgba(251,146,60,.2)'},
      ln('Actual',hv.concat(pad(F.t.length)),'#38e1c8',{w:1.8}), ln('Forecast',pad(back).concat(F.mean),'#fbbf24',{borderDash:[6,3]}), flat(N,p.crit,'#f43f5e','Critical')]},options:chartOpts()});
  }
  if(S.step===3){
    const sig = s.signals.filter((x,i)=>x.risk>0.5||i<4), top=p.drivers.slice(0,2).map(x=>x.label.toLowerCase());
    const why = p.drivers.length ? `The score for ${p.label.toLowerCase()} is driven mainly by ${top.join(' and ')}. `+(p.abnormal?`The reading is ${f(Math.abs(p.z),1)} standard deviations from this station's own baseline, which is rare under normal operation.`:'') : `${p.label} is behaving normally, so nothing is pushing its risk up.`;
    st.innerHTML = `<div class="cols"><div><h2>${T.l}</h2><p class="q">${T.q}</p><h3 style="font-size:.86rem;margin-bottom:10px">Top signals at ${s.area} (risk /100)</h3>
      <div class="bars">${sig.map(x=>bar(x.label,x.risk,f(x.risk,0),COL[x.status])).join('')}</div></div>
      <div><h3 style="font-size:.86rem;margin:46px 0 10px">What drove the ${p.label.toLowerCase()} score</h3><div class="bars">${p.drivers.length?p.drivers.map(x=>bar(x.label,x.share,f(x.share,0)+' %',c)).join(''):'<p class="muted">No signal is pushing this parameter\'s risk up.</p>'}</div></div></div>
      <div class="because">${why}</div>`;
  }
  if(S.step===4){
    if(!s.checklist.length){ st.innerHTML=`<div class="okmsg"><h2>${T.l}</h2><p>All parameters are healthy at ${s.area}. Keep the routine inspection as planned. The model re-scores every hour.</p></div>`; return; }
    const done=JSON.parse(localStorage.getItem('done-'+s.id)||'{}');
    const hyp = s.hypotheses.length ? s.hypotheses.map(h=>`<li><b>${h.text}</b> (${h.confidence} % confidence)</li>`).join('') : s.causes.map(x=>`<li><b>${x.param}:</b> ${x.cause}</li>`).join('');
    st.innerHTML = `<div class="act"><div><h2>${T.l}</h2><p class="q">${T.q}</p>
      <div class="card warn"><h3>Act by</h3><div class="due">${s.due}</div></div>
      <div class="card"><h3>Precautions until the team arrives</h3>${s.precautions.length?`<ul>${s.precautions.map(t=>`<li>${t}</li>`).join('')}</ul>`:'<p class="muted">No operating restriction needed. Schedule the visit.</p>'}</div>
      <div class="card"><h3>Likely root cause</h3><ul>${hyp}</ul></div></div>
      <div><h3 style="font-size:.9rem;margin:0 0 10px">Field checklist, ${s.area}</h3><div class="todo">${s.checklist.map(i=>`<div class="it ${done[i.key]?'ok':''}"><button class="cb" data-k="${i.key}" aria-label="Mark done: ${i.text}">${done[i.key]?'✓':''}</button><div class="tx">${i.text}<small>${i.param}</small></div><span class="pr ${i.prio}">${i.prio}</span></div>`).join('')}</div></div></div>`;
    document.querySelectorAll('.cb').forEach(b=>b.onclick=()=>{done[b.dataset.k]=!done[b.dataset.k]; localStorage.setItem('done-'+s.id,JSON.stringify(done)); renderStage();});
  }
}
const bar=(l,w,v,col)=>`<div class="bar" style="--c:${col}"><span>${l}</span><b>${v}</b><span class="tr"><i style="width:${Math.max(2,Math.min(100,w))}%"></i></span></div>`;

/* ---------- history, model ---------- */
function renderHistory(){
  const p=S.st.params[S.param], H=p.history, n=H.t.length;
  $('hist-sub').textContent=`${p.label} at ${S.st.area}: daily worst reading. Red dots are days the critical limit was crossed.`;
  if(S.hist) S.hist.destroy();
  const o=chartOpts(); o.scales.x.ticks.maxTicksLimit=9;
  S.hist=new Chart($('hist'),{type:'line',data:{labels:H.t.map(t=>when(t,{day:'2-digit',month:'short'})),datasets:[
    ln('Daily worst',H.v,'#38e1c8',{w:1.8,pointRadius:H.v.map(v=>p.sign*(v-p.crit)>0?4:0),pointBackgroundColor:'#f43f5e'}),flat(n,p.warn,'#fbbf24','Warn'),flat(n,p.crit,'#f43f5e','Critical')]},options:o});
}
init();
