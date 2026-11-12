import {
  html, render, useState, useEffect, useRef, useCallback, api, stream, useRoute, go, Md, MathInput, PhotoPicker, Thumbs,
  Chat, SolutionSteps, ReportButton, FeedbackButton, Bar, Ring, ProgressChart, Loading, useApi, pct, fmtIso, fmtDateTime, ago, levelColor, levelText, toast,
} from './common.js';

let ME = null;

// ───────────── shell ─────────────
function App() {
  const route = useRoute();
  const [me, setMe] = useState(null);
  const [rank, setRank] = useState(null);
  const refreshRank = useCallback(() => api('/api/rank').then(setRank).catch(() => {}), []);
  useEffect(() => { api('/api/me').then((m) => { ME = m; window.__appVersion = m.version; setMe(m); }); refreshRank(); }, []);
  useEffect(() => { window.__refreshRank = refreshRank; }, [refreshRank]);
  if (!me) return html`<${Loading} />`;
  const p = route.parts;
  const nav = [['/', '🏠', 'Start'], ['/ueben', '✏️', 'Üben'], ['/revanche', '🎯', 'Revanche'], ['/tutor', '💬', 'Tutor'], ['/mehr', '☰', 'Mehr']];
  const active = (h) => (h === '/' ? route.path === '/' : route.path.startsWith(h));
  let page;
  switch (p[0]) {
    case undefined: page = html`<${Home} rank=${rank} />`; break;
    case 'kapitel': page = p[1] ? html`<${ChapterPage} cid=${p[1]} tab=${route.q.tab} />` : html`<${Chapters} />`; break;
    case 'ueben': page = html`<${Practice} q=${route.q} />`; break;
    case 'aufgabe': page = html`<${Practice} q=${{ id: p[1] }} />`; break;
    case 'tutor': page = html`<${TutorPage} chatId=${p[1] ? +p[1] : null} />`; break;
    case 'revanche': page = html`<${ChallengePage} play=${p[1] === 'los'} />`; break;
    case 'pruefung': page = p[1] === 'lauf' ? html`<${ExamRun} rid=${+p[2]} />` : html`<${Exams} />`; break;
    case 'formeln': page = html`<${Formeln} />`; break;
    case 'trainer': page = html`<${FormulaTrainer} chapter=${route.q.kapitel} skill=${route.q.skill} />`; break;
    case 'grundlagen': page = html`<${Basics} />`; break;
    case 'medaillen': page = html`<${MedalsPage} />`; break;
    case 'mehr': page = html`<${MorePage} />`; break;
    case 'rang': page = html`<${RankPage} />`; break;
    default: page = html`<p>Seite nicht gefunden.</p>`;
  }
  return html`
    <header class="topbar">
      <a class="brand" href="#/"><span class="tri"></span>Mathe-Trainer</a>
      <nav>${nav.filter(([h]) => h !== '/mehr').map(([h, , l]) => html`<a href=${'#' + h} class=${active(h) ? 'on' : ''}>${l}</a>`)}<a href="#/kapitel" class=${active('/kapitel') ? 'on' : ''}>Kapitel</a>
        <a href="#/trainer" class=${active('/trainer') ? 'on' : ''}>Formeltrainer</a><a href="#/grundlagen" class=${active('/grundlagen') ? 'on' : ''}>Grundlagen</a>
        <a href="#/pruefung" class=${active('/pruefung') ? 'on' : ''}>Prüfung</a><a href="#/formeln" class=${active('/formeln') ? 'on' : ''}>Formeln</a></nav>
      <a class="me" href="#/rang" title="Dein Rang">
        ${rank && rank.rank.badge ? html`<img src=${rank.rank.badge} alt="" />` : null}
        <span>${rank ? rank.rank.name : ''}</span><span class="xp-pill">${rank ? rank.xp : 0} XP</span>
      </a>
      ${me.admin && html`<a class="btn small" href="/admin" style="margin-left:.5rem">Coach</a>`}
    </header>
    ${me.preview && html`<div style="background:var(--warn-soft);color:var(--warn);padding:.35rem 1rem;font-size:.85rem;text-align:center">Vorschau als Coach – deine Eingaben zählen nicht zu ${me.student}s Fortschritt.</div>`}
    <main>${page}</main>
    <nav class="bottomnav">${nav.map(([h, i, l]) => html`<a href=${'#' + h} class=${active(h) ? 'on' : ''}><span>${i}</span>${l}</a>`)}</nav>
    <${FeedbackButton} />`;
}

// ───────────── home / dashboard ─────────────
function Home({ rank }) {
  const { data: d } = useApi('/api/dashboard');
  const { data: hist } = useApi('/api/history?days=30');
  if (!d) return html`<${Loading} />`;
  const r = d.rank;
  const wk = d.week; const lw = d.last_week;
  const trend = (a, b) => (a == null || b == null ? null : a - b);
  const accTrend = trend(wk.accuracy, lw.accuracy);
  const hour = new Date().getHours();
  const greet = hour < 11 ? 'Guten Morgen' : hour < 18 ? 'Hallo' : 'Guten Abend';
  const nextUp = r.next;
  return html`
    <section class="card hero">
      <div class="row gap" style="align-items:flex-start">
        <div class="hero-figure"><${Avatar} rankId=${r.rank.id} size=${150} cls="idle" />
        ${r.rank.badge ? html`<img class="badge-big" src=${r.rank.badge} alt=${r.rank.name} />` : html`<div class="badge-none">kein<br/>Abzeichen</div>`}</div>
        <div class="grow">
          <div class="muted small">${greet}, ${ME.student}!</div>
          <div class="rank-name">${r.rank.name}</div>
          <div class="muted small">${r.xp} XP${nextUp ? ` · nächster Grad: ${nextUp.name}` : ' · höchster Grad erreicht 🎉'}</div>
          ${nextUp && html`<div style="margin-top:.5rem"><${Bar} value=${r.xp / nextUp.xp} height=${10} /></div>
            <ul class="checks">${r.next_checks.map((c) => html`<li><span class=${`ck ${c.ok ? 'ok' : ''}`}>${c.ok ? '✓' : ''}</span>${c.text}${!c.ok && c.progress > 0 ? html` <span class="muted">(${Math.round(c.progress * 100)} %)</span>` : ''}</li>`)}</ul>`}
        </div>
      </div>
    </section>

    <div class="grid g4" style="margin-bottom:1rem">
      <div class="kpi"><div class="l">Serie</div><div class="v">${d.streak} 🔥</div><div class="d muted">${d.streak === 1 ? 'Tag' : 'Tage'} am Stück</div></div>
      <div class="kpi"><div class="l">Diese Woche</div><div class="v">${wk.correct}</div>
        <div class="d ${wk.correct >= lw.correct ? 'up' : 'down'}">${wk.correct >= lw.correct ? '▲' : '▼'} ${lw.correct} letzte Woche</div></div>
      <div class="kpi"><div class="l">Trefferquote 7 T.</div><div class="v">${pct(wk.accuracy)}</div>
        <div class="d ${accTrend == null ? 'muted' : accTrend >= 0 ? 'up' : 'down'}">${accTrend == null ? 'noch keine Daten' : `${accTrend >= 0 ? '▲' : '▼'} ${Math.abs(Math.round(accTrend * 100))} Punkte`}</div></div>
      <div class="kpi"><div class="l">Prüfungsfit</div><div class="v">${pct(d.readiness)}</div><div class="d muted">${d.mastered}/${d.skills_total} Themen sicher</div></div>
    </div>

    <section class="card">
      <div class="row between wrap gap"><h2 style="margin:0">Heute</h2><a class="small" href="#/medaillen">🏅 Medaillen</a></div>
      <div class="grid g4" style="margin-top:.6rem;align-items:center">
        <div class="row gap"><${Ring} value=${d.goal.done / d.goal.goal} size=${64} label=${`${d.goal.done}/${d.goal.goal}`} color=${d.goal.reached ? 'var(--ok)' : 'var(--accent)'} />
          <div><b>Tagesziel</b><div class="small muted">${d.goal.reached ? 'erreicht! 🎉' : `${d.goal.goal - d.goal.done} richtige Antworten fehlen`}</div></div></div>
        ${d.quests.map((qq) => html`<div class=${`quest ${qq.done ? 'done' : ''}`}><div class="small"><b>${qq.done ? '✅' : '⚔️'} ${qq.title}</b></div>
          <${Bar} value=${qq.progress / qq.target} color=${qq.done ? 'var(--ok)' : 'var(--accent)'} /><div class="small muted">${qq.progress}/${qq.target} · +${qq.xp} XP</div></div>`)}
      </div>
    </section>

    <div class="grid g2">
      <section class="card">
        <h2>Heute empfohlen</h2>
        <ul class="list">
          ${d.challenges_due > 0 && html`<li class="row between"><span>🎯 <b>${d.challenges_due} Revanche${d.challenges_due > 1 ? 'n' : ''}</b> fällig – zeig, dass du es jetzt kannst!</span><a class="btn primary small" href="#/revanche/los">Los</a></li>`}
          ${d.assignments.filter((a) => !a.archived).map((a) => html`<li class="row between gap"><span>📌 <b>${a.title}</b><br/><span class="small muted">${a.description || ''} ${a.target ? `· ${Math.min(a.done, a.target)}/${a.target}` : ''}</span></span>
            <a class="btn small" href=${'#/ueben?' + (a.skills && a.skills.length ? `skill=${a.skills[0]}` : a.exercise_ids.length ? `id=${a.exercise_ids[0]}` : '')}>Üben</a></li>`)}
          ${d.recommend.weak.map((w) => html`<li class="row between gap"><span>💪 ${w.title} <span class="tag bad">${pct(w.mastery)}</span></span><a class="btn small" href=${`#/ueben?skill=${w.skill}`}>Üben</a></li>`)}
          ${d.recommend.new.map((w) => html`<li class="row between gap"><span>✨ Neu: ${w.title}</span><a class="btn small" href=${`#/ueben?skill=${w.skill}`}>Starten</a></li>`)}
          <li class="row between"><span>🎲 Gemischte Aufgaben nach deinem Stand</span><a class="btn small" href="#/ueben">Los</a></li>
          <li class="row between"><span>🧠 Formeln auffrischen (60-Sekunden-Sprint)</span><a class="btn small" href="#/trainer">Los</a></li>
        </ul>
      </section>
      <section class="card">
        <h2>Termine</h2>
        <div class="row gap wrap">
          <div class="kpi grow"><div class="l">Nächste Lernsession</div><div class="v">${d.dates.days_to_session ?? '–'}<span class="small"> Tage</span></div><div class="d muted">${fmtIso(d.dates.next_session)}</div></div>
          <div class="kpi grow"><div class="l">Prüfung (vorauss.)</div><div class="v">${d.dates.days_to_exam ?? '–'}<span class="small"> Tage</span></div><div class="d muted">${fmtIso(d.dates.exam)}</div></div>
        </div>
        <p class="small muted" style="margin-bottom:0">Faustregel: 20–30 Minuten pro Tag bringen mehr als 3 Stunden am Wochenende.</p>
      </section>
    </div>

    <section class="card">
      <div class="row between"><h2>Dein Fortschritt (30 Tage)</h2><span class="small muted">Linie: Beherrschung · Balken: gelöste Aufgaben</span></div>
      ${hist ? html`<${ProgressChart} data=${hist} />` : html`<${Loading} />`}
    </section>

    <section class="card">
      <h2>Kapitel</h2>
      <div class="grid g3">${Object.entries(d.chapters).map(([cid, m], i) => html`
        <a class="row gap clickable" style="padding:.4rem;border-radius:10px;color:inherit" href=${`#/kapitel/${cid}`}>
          <${Ring} value=${m} size=${56} color=${levelColor(m, 1)} /><div><b>Kapitel ${i + 1}</b><div class="small muted">${CH_TITLES[cid] || ''}</div></div></a>`)}
      </div>
    </section>`;
}
const CH_TITLES = { k1: 'Polynomfunktionen', k2: 'Trigonometrie', k3: 'Exponentialfunktion', k4: 'Differentialrechnung', k5: 'Integralrechnung', k6: 'Vektoren' };

// ───────────── chapters ─────────────
function Chapters() {
  const { data } = useApi('/api/curriculum');
  if (!data) return html`<${Loading} />`;
  return html`<h1>Kapitel</h1>
    <div class="grid g2">${data.chapters.map((c) => html`
      <section class="card chapter-card" onClick=${() => go(`/kapitel/${c.id}`)}>
        <div class="row gap"><span class="icon">${c.icon}</span><div class="grow"><h3 style="margin:0">${c.nr}. ${c.title}</h3>
          <div class="small muted">${c.skills.length} Themen · ${c.exercises} Kursaufgaben + unbegrenzt generierte</div></div><${Ring} value=${c.mastery} size=${54} color=${levelColor(c.mastery, 1)} /></div>
        <div class="row gap wrap" style="margin-top:.6rem">${c.skills.map((s) => html`<span class="dot" title=${`${s.title}: ${levelText(s.mastery, s.n)}`} style=${`background:${levelColor(s.mastery, s.n)}`}></span>`)}</div>
      </section>`)}</div>`;
}

function ChapterPage({ cid, tab = 'themen' }) {
  const { data, reload } = useApi(`/api/chapter/${cid}`);
  const [filter, setFilter] = useState('alle');
  if (!data) return html`<${Loading} />`;
  const ch = data.chapter;
  const setTab = (t) => go(`/kapitel/${cid}?tab=${t}`);
  const exs = data.exercises.filter((e) => filter === 'alle' || e.status === filter);
  return html`<div class="row between wrap gap"><h1>${ch.icon} ${ch.nr}. ${ch.title}</h1><a class="btn primary" href=${`#/ueben?chapter=${cid}`}>Kapitel üben</a></div>
    <div class="tabs">${[['themen', 'Themen'], ['theorie', 'Theorie'], ['aufgaben', `Aufgaben (${data.exercises.length})`], ['formeln', 'Formeln']].map(([k, l]) => html`<button class=${tab === k ? 'on' : ''} onClick=${() => setTab(k)}>${l}</button>`)}</div>
    ${tab === 'themen' && html`<section class="card">${ch.skills.map((s) => html`
      <div class="skill"><div><b>${s.title}</b><div class="small muted">Skript ${s.skript} · ${levelText(s.mastery, s.n)}${s.n ? ` · ${s.n} Versuche` : ''}</div></div>
        <${Bar} value=${s.mastery} color=${levelColor(s.mastery, s.n)} />
        <div class="row gap"><a class="btn small" href=${`#/ueben?skill=${s.id}`}>Üben</a><a class="btn small ghost" title="Erklären lassen" href=${`#/tutor?erklaere=${encodeURIComponent(s.title)}`}>💬</a></div></div>`)}</section>`}
    ${tab === 'theorie' && html`<section class="card"><${Md} src=${data.theory || '_Noch keine Theorie vorhanden._'} /></section>`}
    ${tab === 'formeln' && html`<section class="card"><${Md} src=${data.formeln || '_Keine Formeln._'} /></section>`}
    ${tab === 'aufgaben' && html`<section class="card">
      <div class="chips">${[['alle', 'Alle'], ['neu', 'Neu'], ['offen', 'Noch nicht gelöst'], ['geloest', 'Gelöst']].map(([k, l]) => html`<button class=${`chip ${filter === k ? 'on' : ''}`} onClick=${() => setFilter(k)}>${l}</button>`)}</div>
      <ul class="list">${exs.map((e) => html`<li class="row between gap clickable" onClick=${() => go(`/aufgabe/${e.id}`)}>
        <span><b>${e.title}</b><br/><span class="small muted">${e.source.doc} ${e.source.ref || ''} · ${e.calculator === 'mit' ? '🧮 mit Rechner' : '✍️ ohne Rechner'} · ${'★'.repeat(e.difficulty || 1)}</span></span>
        <span class=${`tag ${e.status === 'geloest' ? 'ok' : e.status === 'offen' ? 'bad' : ''}`}>${e.status === 'geloest' ? 'gelöst' : e.status === 'offen' ? 'offen' : 'neu'}</span></li>`)}</ul></section>`}`;
}

// ───────────── practice / exercise player ─────────────
function Practice({ q }) {
  const [ex, setEx] = useState(null);
  const [err, setErr] = useState(null);
  const [n, setN] = useState(0);
  const load = useCallback(async (opts = {}) => {
    setEx(null); setErr(null);
    try {
      let e;
      if (opts.similar) e = await api(`/api/exercise/${opts.similar}/similar`);
      else if (q.id && n === 0) e = await api(`/api/exercise/${q.id}`);
      else {
        const p = new URLSearchParams();
        if (q.skill) p.set('skill', q.skill);
        if (q.chapter) p.set('chapter', q.chapter);
        e = await api(`/api/exercise/next?${p}`);
      }
      setEx(e); setN((x) => x + 1);
    } catch (e) { setErr(e.message); }
  }, [q.id, q.skill, q.chapter, n]);
  useEffect(() => { setN(0); }, [q.id, q.skill, q.chapter]);
  useEffect(() => { if (n === 0) load(); }, [n]);
  if (err) return html`<p>${err}</p>`;
  if (!ex) return html`<${Loading} />`;
  return html`<${Exercise} key=${ex.id + n} ex=${ex} mode="practice"
    onNext=${() => load()} onSimilar=${() => load({ similar: ex.id })} />`;
}

function burst(text) { const d = document.createElement('div'); d.className = 'xp-burst'; d.textContent = text; document.body.appendChild(d); setTimeout(() => d.remove(), 1500); }

function Promotion({ rank, onClose }) {
  return html`<div class="promo" onClick=${onClose}><div class="inner">
    <div class="muted small">BEFÖRDERUNG</div>
    <div class="promo-figure"><${Avatar} rankId=${rank.id} size=${180} cls="levelup" />${rank.badge ? html`<img class="promo-badge" src=${rank.badge} alt="" />` : null}</div>
    <h2>${rank.name}</h2><p>Herzliche Gratulation, ${ME.student}! Du hast dir diesen Grad verdient.</p>
    <button class="btn primary">Weiter</button></div></div>`;
}

export function Exercise({ ex, mode, challenge, onNext, onSimilar, onDone }) {
  const [state, setState] = useState({});      // per part: {input, result, hints:[], solution, done}
  const [tutorOpen, setTutorOpen] = useState(false);
  const [review, setReview] = useState(null);   // {streaming text, result}
  const [photos, setPhotos] = useState([]);
  const [promo, setPromo] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [askText, setAskText] = useState(null);
  const askTutor = (t) => { setAskText(t); setTutorOpen(true); };
  const [combo, setCombo] = useState(0);
  const t0 = useRef(Date.now());
  useEffect(() => { window.__currentExercise = ex.id; return () => { if (window.__currentExercise === ex.id) window.__currentExercise = null; }; }, [ex.id]);
  const ps = (lab) => state[lab] || { input: '', hints: [] };
  const setPs = (lab, patch) => setState((s) => ({ ...s, [lab]: { ...ps(lab), ...(s[lab] || {}), ...patch } }));
  const allDone = ex.parts.every((p) => (state[p.label] || {}).done);
  useEffect(() => { if (allDone && onDone) onDone(); }, [allDone]);

  const submit = async (p) => {
    const st = ps(p.label);
    let input = st.input;
    if (p.answer.type === 'tuple') input = (st.tuple || []).map((v) => v || '').join('; ');
    if (p.answer.type === 'choice') input = st.choice;
    try {
      const r = await api(`/api/exercise/${ex.id}/check`, {
        method: 'POST', body: {
          part: p.label, input, hints: st.hints.length, duration_s: Math.round((Date.now() - t0.current) / 1000), mode,
          challenge_id: challenge && challenge.id,
        },
      });
      setPs(p.label, { result: r, done: r.ok || st.done, solution: r.solution || st.solution });
      if (r.xp > 1) burst(`+${r.xp} XP${r.combo >= 3 ? `  ·  🔥 ${r.combo}er-Serie` : ''}`);
      if (r.combo !== undefined) setCombo(r.combo);
      if (r.combo_bonus) setTimeout(() => toast(`⚡ Combo ×${r.combo}! +${r.combo_bonus} Bonus-XP`, 'ok'), 900);
      (r.new_medals || []).forEach((m, k) => setTimeout(() => toast(`${m.icon} Neue Medaille: <b>${m.title}</b> (+15 XP)`, 'ok'), 1500 + 1200 * k));
      if (r.goal && r.goal.reached && r.goal.done === r.goal.goal) setTimeout(() => toast('🎯 Tagesziel erreicht! +25 XP', 'ok'), 1200);
      if (r.challenge === 'beaten') toast('🎯 Revanche gewonnen! +30 XP', 'ok');
      if (r.promoted) setPromo(r.promoted);
      window.__refreshRank && window.__refreshRank();
      t0.current = Date.now();
    } catch (e) { toast(e.message, 'bad'); }
  };
  const getHint = async (p) => {
    const st = ps(p.label);
    try {
      const r = await api(`/api/exercise/${ex.id}/hint`, { method: 'POST', body: { part: p.label, level: st.hints.length + 1 } });
      setPs(p.label, { hints: [...st.hints, r.text] });
    } catch (e) { toast(e.message); }
  };
  const showSolution = async (p) => {
    if (!confirm('Lösung anzeigen? Die Aufgabe zählt dann als nicht gelöst und kommt später als Revanche wieder.')) return;
    const st = ps(p.label);
    const r = await api(`/api/exercise/${ex.id}/solution`, { method: 'POST', body: { part: p.label, hints: st.hints.length, mode, challenge_id: challenge && challenge.id, duration_s: Math.round((Date.now() - t0.current) / 1000) } });
    setPs(p.label, { solution: r.solution, done: true, shown: true });
  };
  const startReview = async () => {
    if (!photos.length) return;
    setReview({ text: '', tool: null, result: null, busy: true });
    await stream(`/api/exercise/${ex.id}/review`, { photo_ids: photos, mode }, (ev) => {
      if (ev.t === 'text') setReview((r) => ({ ...r, text: r.text + ev.d, tool: null }));
      else if (ev.t === 'replace') setReview((r) => ({ ...r, text: ev.text }));
      else if (ev.t === 'tool') setReview((r) => ({ ...r, tool: ev.name }));
      else if (ev.t === 'error') setReview((r) => ({ ...r, text: r.text + `\n\n⚠️ ${ev.message}` }));
      else if (ev.t === 'result') {
        setReview((r) => ({ ...r, result: ev, busy: false }));
        if (ev.results) {
          ev.results.forEach((x) => setPs(x.label, { done: true, result: { ok: x.correct, status: x.correct ? 'richtig' : 'falsch', message: x.feedback }, solution: ev.solutions && ev.solutions[x.label] }));
        }
        if (ev.promoted) setPromo(ev.promoted);
        window.__refreshRank && window.__refreshRank();
      }
    });
    setReview((r) => ({ ...r, busy: false }));
    setPhotos([]);
  };

  return html`<div class="exercise">
    ${promo && html`<${Promotion} rank=${promo} onClose=${() => setPromo(null)} />`}
    <section class="card">
      <div class="row between wrap gap">
        <div><div class="small muted">${ex.source.doc}${ex.source.ref ? ' · ' + ex.source.ref : ''}</div><h2 style="margin:.1rem 0">${ex.title}</h2></div>
        <div class="row gap wrap">
          ${combo >= 2 && html`<span class="tag acc">🔥 ${combo}er-Serie</span>`}
          ${challenge && html`<span class="tag acc">🎯 Revanche ${challenge.wins}/${challenge.need}</span>`}
          <span class="tag">${ex.calculator === 'mit' ? '🧮 mit Rechner' : '✍️ ohne Rechner'}</span><span class="tag">${'★'.repeat(ex.difficulty || 1)}</span>
          ${ex.minutes ? html`<span class="tag">~${ex.minutes} min</span>` : null}
          <${ReportButton} ex=${ex} inputs=${Object.fromEntries(ex.parts.map((p) => {
            const st = state[p.label] || {};
            return [p.label || '', p.answer.type === 'tuple' ? (st.tuple || []).join('; ') : p.answer.type === 'choice' ? st.choice : st.input];
          }))} />
        </div>
      </div>
      <div class="statement"><${Md} src=${ex.statement} /></div>
      ${(ex.figures || []).map((f) => html`<img class="figure" src=${`/figures/${f}`} alt="Abbildung" />`)}
      ${ex.parts.map((p) => html`<${Part} p=${p} st=${ps(p.label)} set=${(patch) => setPs(p.label, patch)}
          onSubmit=${() => submit(p)} onHint=${() => getHint(p)} onSolution=${() => showSolution(p)} single=${ex.parts.length === 1}
          onAsk=${(t) => askTutor((p.label ? `Teilaufgabe ${p.label}) – ` : '') + t)} />`)}
    </section>

    <section class="card">
      <h3>✍️ Auf Papier gelöst?</h3>
      <p class="small muted" style="margin-top:0">Fotografiere deinen Lösungsweg – der Tutor liest ihn, prüft jeden Schritt und zeigt dir die erste Fehlerstelle.</p>
      <div class="row gap wrap"><${PhotoPicker} label="Foto aufnehmen" exerciseId=${ex.id} onPhoto=${(ph) => setPhotos((x) => [...x, ph.id])} />
        <button class="btn primary" disabled=${!photos.length || (review && review.busy)} onClick=${startReview}>Korrigieren lassen</button></div>
      <${Thumbs} ids=${photos} onRemove=${(id) => setPhotos(photos.filter((x) => x !== id))} />
      ${review && html`<div style="margin-top:.6rem">
        ${review.busy && !review.text && html`<div class="typing"><span></span><span></span><span></span><em> ${review.tool ? 'prüft deine Rechnung…' : 'liest dein Blatt…'}</em></div>`}
        <${Md} src=${review.text} />
        ${review.result && review.result.review && html`<details><summary class="small muted">So hat der Tutor dein Blatt gelesen</summary><${Md} src=${review.result.review.transcription || ''} /></details>`}
      </div>`}
    </section>

    <div class="row gap wrap noprint" style="margin-bottom:1rem">
      <button class="btn" onClick=${() => setFormOpen(true)}>📐 Formeln</button>
      <button class="btn" onClick=${() => setTutorOpen(true)}>💬 Frag den Tutor</button>
      ${onSimilar && html`<button class="btn" onClick=${onSimilar}>🔁 Ähnliche Aufgabe</button>`}
      ${onNext && html`<button class=${`btn ${allDone ? 'primary' : ''}`} onClick=${onNext}>Nächste Aufgabe →</button>`}
    </div>
    ${formOpen && html`<${FormulasDrawer} exId=${ex.id} onClose=${() => setFormOpen(false)} onAsk=${(t) => { setFormOpen(false); askTutor(`Erklär mir bitte: ${t}`); }} />`}
    ${tutorOpen && html`<div class="drawer"><div class="row between"><b>Tutor zu dieser Aufgabe</b><button class="btn small" onClick=${() => { setTutorOpen(false); setAskText(null); }}>Schliessen</button></div>
      <${Chat} key=${askText || 'chat'} exerciseId=${ex.id} mode=${askText ? 'explain' : 'hint'} prefill=${askText || ''} intro=${html`<p>Ich kenne die Aufgabe. Wo hängst du? Schreib deinen Ansatz oder schick ein Foto – ich verrate nicht gleich die Lösung.</p>`} /></div>`}
  </div>`;
}

function Part({ p, st, set, onSubmit, onHint, onSolution, single, onAsk }) {
  const a = p.answer;
  const done = st.done;
  const r = st.result;
  let input;
  if (a.type === 'choice') {
    input = html`<div class="choice">${a.options.map((o, i) => html`<label class=${st.choice === i ? 'sel' : ''}><input type="radio" name=${'c' + p.label} checked=${st.choice === i} disabled=${done} onChange=${() => set({ choice: i })} /><${Md} src=${o} /></label>`)}</div>`;
  } else if (a.type === 'tuple') {
    const names = a.names || Array.from({ length: a.count }, (_, i) => (a.count === 2 ? ['x', 'y'][i] : a.count === 3 ? ['x', 'y', 'z'][i] : `${i + 1}.`));
    input = html`<div class="tuple-inputs">${names.map((nm, i) => html`<label>${nm} <${MathInput} value=${(st.tuple || [])[i] || ''} onInput=${(v) => { const t = (st.tuple || []).slice(); t[i] = v; set({ tuple: t }); }} onEnter=${onSubmit} /></label>`)}</div>`;
  } else if (a.type === 'text') {
    input = html`<p class="small muted" style="margin:.2rem 0">Diese Teilaufgabe (Skizze/Begründung) wird vom Tutor beurteilt: Löse sie auf Papier und lade unten ein Foto hoch, oder schreib deine Antwort in den Tutor-Chat.</p>`;
  } else {
    input = html`<${MathInput} value=${st.input} onInput=${(v) => set({ input: v })} onEnter=${onSubmit}
      placeholder=${a.type === 'set' ? 'Werte, getrennt mit ;' : ''} />`;
  }
  return html`<div class=${single ? '' : 'part'}>
    ${p.prompt && html`<div class="row gap" style="align-items:baseline">${p.label && html`<span class="label">${p.label})</span>`}<${Md} src=${p.prompt} /></div>`}
    <div class="answer-row">${input}
      ${a.type !== 'text' && html`<button class="btn primary" disabled=${done && r && r.ok} onClick=${onSubmit}>Prüfen</button>`}
      ${a.unit && html`<span class="muted" style="align-self:center">${a.unit}</span>`}
    </div>
    ${a.type === 'set' && html`<div class="small muted">Mehrere Werte mit Semikolon trennen, z.B. <code>-2; 0; 5</code></div>`}
    ${r && html`<div class=${`feedback ${r.status}`}>${r.ok ? '✅ ' : r.status === 'falsch' ? '❌ ' : '⚠️ '}${r.message}${r.parsed && !r.ok ? html` <span class="small">(gelesen als <code>${r.parsed}</code>)</span>` : ''}</div>`}
    ${st.hints.map((h, i) => html`<div class="hintbox"><b>Hinweis ${i + 1}:</b> <${Md} src=${h} /></div>`)}
    ${st.solution && html`<${SolutionSteps} sol=${st.solution} onAsk=${onAsk} />`}
    ${!(r && r.ok) && !st.shown && html`<div class="row gap wrap small">
      ${st.hints.length < (p.hint_count || 3) && html`<button class="btn small" onClick=${onHint}>💡 Hinweis ${st.hints.length + 1}/${p.hint_count || 3}</button>`}
      ${(st.hints.length >= 2 || (r && !r.ok)) && html`<button class="btn small ghost" onClick=${onSolution}>Lösung zeigen</button>`}
    </div>`}
  </div>`;
}

// ───────────── tutor page ─────────────
function TutorPage({ chatId }) {
  const { data: chats, reload } = useApi('/api/chats');
  const q = new URLSearchParams(location.hash.split('?')[1] || '');
  const topic = q.get('erklaere');
  const frage = q.get('frage');
  const [key, setKey] = useState(0);
  return html`<div class="grid" style="grid-template-columns:minmax(0,1fr)">
    <div class="row between wrap gap"><h1>Tutor</h1>
      <div class="row gap"><select style="max-width:260px" value=${chatId || ''} onChange=${(e) => go(e.target.value ? `/tutor/${e.target.value}` : '/tutor')}>
        <option value="">+ Neues Gespräch</option>${(chats || []).map((c) => html`<option value=${c.id}>${c.kind === 'review' ? '📷 ' : ''}${c.title}</option>`)}</select>
        <button class="btn" onClick=${() => { go('/tutor'); setKey((k) => k + 1); }}>Neu</button></div></div>
    <section class="card" style="padding:.6rem">
      <${Chat} key=${(chatId || 'new') + key} chatId=${chatId} mode=${topic ? 'explain' : 'chat'}
        intro=${topic ? html`<p>Tippe auf <b>Senden</b>, um dir <b>${topic}</b> erklären zu lassen.</p>` : null} />
      ${topic && !chatId && html`<${AutoFill} text=${`Erklär mir bitte: ${topic}`} />`}
      ${frage && !chatId && html`<${AutoFill} text=${frage} />`}
    </section></div>`;
}
function AutoFill({ text }) {
  useEffect(() => { const ta = document.querySelector('.chat-input textarea'); if (ta && !ta.value) { ta.value = text; ta.dispatchEvent(new Event('input', { bubbles: true })); } }, []);
  return null;
}

// ───────────── challenge (Revanche) ─────────────
function ChallengePage({ play }) {
  const { data, reload } = useApi('/api/challenges');
  const [ex, setEx] = useState(null);
  const [none, setNone] = useState(false);
  const loadNext = async () => {
    setEx(null);
    try { setEx(await api('/api/challenges/next')); setNone(false); } catch (e) { setNone(true); reload(); }
  };
  useEffect(() => { if (play) loadNext(); }, [play]);
  if (play) {
    if (none) return html`<section class="card center"><h2>Alles erledigt 🎉</h2><p>Gerade ist keine Revanche fällig. Neue kommen, wenn eine Aufgabe nicht klappt – und gelöste kommen nach einigen Tagen zur Bestätigung zurück.</p><a class="btn" href="#/revanche">Zur Übersicht</a></section>`;
    if (!ex) return html`<${Loading} />`;
    return html`<${Exercise} key=${ex.id} ex=${ex} mode="challenge" challenge=${ex.challenge} onNext=${loadNext} />`;
  }
  if (!data) return html`<${Loading} />`;
  const items = data.items;
  const due = items.filter((c) => c.status === 'open' && c.due);
  const waiting = items.filter((c) => c.status === 'open' && !c.due);
  const beaten = items.filter((c) => c.status === 'beaten');
  return html`<div class="row between wrap gap"><h1>🎯 Revanche</h1>${due.length ? html`<a class="btn primary" href="#/revanche/los">${due.length} fällige starten</a>` : null}</div>
    <p class="muted">Aufgaben, die nicht geklappt haben, kommen hier zurück – nach 1, 3 und 7 Tagen. Löse eine Aufgabe <b>zweimal hintereinander</b> richtig, dann ist die Revanche gewonnen (+30 XP).</p>
    <div class="grid g3" style="margin-bottom:1rem">
      <div class="kpi"><div class="l">Fällig</div><div class="v">${due.length}</div></div>
      <div class="kpi"><div class="l">Warten</div><div class="v">${waiting.length}</div></div>
      <div class="kpi"><div class="l">Gewonnen</div><div class="v">${beaten.length} 🏆</div></div>
    </div>
    ${[['Fällig', due], ['Wartet noch', waiting], ['Gewonnen', beaten]].map(([t, list]) => list.length ? html`<section class="card"><h3>${t}</h3><ul class="list">${list.map((c) => html`
      <li class="row between gap"><span><b>${c.title}</b>${c.part ? ` (${c.part})` : ''}<br/><span class="small muted">${c.skill_title} · ${c.fails}× daneben · ${c.wins}/2 bestätigt${c.status === 'open' && !c.due ? ` · fällig ${fmtDateTime(c.due_at)}` : ''}</span></span>
      <span class=${`tag ${c.status === 'beaten' ? 'ok' : c.due ? 'acc' : ''}`}>${c.status === 'beaten' ? 'gewonnen' : c.due ? 'fällig' : 'wartet'}</span></li>`)}</ul></section>` : null)}
    ${!items.length && html`<div class="empty card">Noch keine Revanchen. Super – oder du hast noch nicht genug geübt 😉</div>`}`;
}

// ───────────── exams ─────────────
function Exams() {
  const { data } = useApi('/api/exams');
  const [busy, setBusy] = useState(false);
  if (!data) return html`<${Loading} />`;
  const start = async (body) => {
    setBusy(true);
    try { const r = await api('/api/exams/start', { method: 'POST', body }); go(`/pruefung/lauf/${r.id}`); } catch (e) { toast(e.message, 'bad'); }
    setBusy(false);
  };
  return html`<h1>Prüfungssimulation</h1>
    <p class="muted">Wie an der Prüfung: Zeitlimit, keine Hinweise, kein Tutor. Rechne auf Papier, gib die Resultate ein und fotografiere am Schluss deine Lösungswege – sie werden nach Prüfungsmassstab korrigiert.</p>
    ${data.exams.map((e) => html`<section class="card"><h3>${e.title}</h3><div class="grid g2">${e.parts.map((p, i) => html`
      <div class="kpi"><b>${p.title}</b><div class="small muted">${p.minutes} min · ${p.exercises.length} Aufgaben${p.max_points ? ` · ${p.max_points} Punkte` : ''}</div>
      ${p.rules && html`<div class="small" style="margin:.3rem 0">${p.rules}</div>`}
      <button class="btn primary small" disabled=${busy} onClick=${() => start({ exam_id: e.id, part_index: i })}>Starten</button></div>`)}</div></section>`)}
    <section class="card"><h3>Gemischte Prüfung (neu zusammengestellt)</h3><p class="small muted">Je eine Aufgabe aus jedem Kapitel.</p>
      <div class="row gap wrap"><button class="btn" disabled=${busy} onClick=${() => start({ exam_id: 'mix', calculator: 'ohne', minutes: 45 })}>Ohne Rechner (45 min)</button>
      <button class="btn" disabled=${busy} onClick=${() => start({ exam_id: 'mix', calculator: 'mit', minutes: 45 })}>Mit Rechner (45 min)</button></div></section>
    ${data.runs.length ? html`<section class="card"><h3>Deine Resultate</h3><ul class="list">${data.runs.map((r) => html`<li class="row between clickable" onClick=${() => go(`/pruefung/lauf/${r.id}`)}>
      <span>${fmtDateTime(r.started_at)}</span><span>${r.finished_at ? html`<b>${Math.round(100 * r.score / r.max_score)} %</b> <span class="muted small">(${r.score.toFixed(1)}/${r.max_score})</span>` : html`<span class="tag warn">läuft</span>`}</span></li>`)}</ul></section>` : null}
    ${data.info && html`<section class="card"><details><summary><b>Infos zur Prüfung</b></summary><${Md} src=${data.info} /></details></section>`}`;
}

function ExamRun({ rid }) {
  const [run, setRun] = useState(null);
  const [answers, setAnswers] = useState({});
  const [photos, setPhotos] = useState({});
  const [now, setNow] = useState(Date.now());
  const load = () => api(`/api/exam_runs/${rid}`).then(setRun);
  useEffect(() => { load(); const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [rid]);
  useEffect(() => {
    if (!run || !run.finished_at) return;
    const pending = Object.values((run.details || {}).grading || {}).some((g) => g.status === 'pending');
    if (pending) { const t = setTimeout(load, 5000); return () => clearTimeout(t); }
  }, [run]);
  if (!run) return html`<${Loading} />`;
  const submit = async () => {
    if (!confirm('Prüfung abgeben?')) return;
    await api(`/api/exam_runs/${rid}/submit`, { method: 'POST', body: { answers, photos } });
    load(); window.__refreshRank && window.__refreshRank();
  };
  if (run.finished_at) {
    const g = run.details.grading || {};
    return html`<h1>${run.details.title}</h1>
      <section class="card hero"><div class="rank-name">${Math.round(100 * run.score / run.max_score)} %</div><div class="muted">${run.score.toFixed(1)} von ${run.max_score} Punkten</div>
      ${Object.values(g).some((x) => x.status === 'pending') && html`<p class="small"><span class="spinner"></span> Fotos werden noch korrigiert…</p>`}</section>
      ${Object.entries(run.solutions || {}).map(([eid, ex]) => html`<section class="card">
        <div class="row between"><h3>${ex.title}</h3><span class="row gap"><${ReportButton} ex=${ex} inputs=${Object.fromEntries(Object.entries((g[eid] && g[eid].parts) || {}).map(([k, v]) => [k, v.input]))} /><span class="tag ${g[eid] && g[eid].points >= g[eid].max * 0.99 ? 'ok' : 'warn'}">${g[eid] ? `${g[eid].points}/${g[eid].max}` : ''} P</span></span></div>
        <${Md} src=${ex.statement} />
        ${ex.parts.map((p) => html`<div class="part">${p.label && html`<span class="label">${p.label})</span>`}<${Md} src=${p.prompt} />
          ${g[eid] && g[eid].parts && g[eid].parts[p.label] && html`<div class=${`feedback ${g[eid].parts[p.label].ok ? 'richtig' : 'falsch'}`}>Deine Antwort: <code>${g[eid].parts[p.label].input ?? '–'}</code></div>`}
          ${g[eid] && g[eid].results && (g[eid].results.find((x) => x.label === p.label) || null) && html`<div class="hintbox">${g[eid].results.find((x) => x.label === p.label).feedback}</div>`}
          <details><summary class="small">Lösungsweg</summary><${SolutionSteps} sol=${{ md: p.solution, steps: p.steps }} onAsk=${(t) => go(`/tutor?frage=${encodeURIComponent(`Zur Prüfungsaufgabe «${ex.title}»${p.label ? ` ${p.label})` : ''}: ${t}`)}`)} /></details></div>`)}</section>`)}`;
  }
  const left = Math.max(0, Math.round(run.deadline - now / 1000));
  const mm = String(Math.floor(left / 60)).padStart(2, '0'); const ss = String(left % 60).padStart(2, '0');
  return html`<div class="row between" style="position:sticky;top:52px;z-index:20;background:var(--bg);padding:.4rem 0">
      <h2 style="margin:0">${run.details.title}</h2><span class=${`tag ${left < 300 ? 'bad' : 'info'}`} style="font-size:1.1rem">⏱ ${mm}:${ss}</span></div>
    ${left === 0 && html`<div class="feedback falsch">Die Zeit ist um – gib jetzt ab.</div>`}
    ${run.exercises.map((ex, i) => html`<section class="card exercise"><h3>Aufgabe ${i + 1}: ${ex.title} ${ex.points ? html`<span class="tag">${ex.points} P</span>` : ''}</h3>
      <${Md} src=${ex.statement} />${(ex.figures || []).map((f) => html`<img class="figure" src=${`/figures/${f}`} />`)}
      ${ex.parts.map((p) => html`<div class="part">${p.prompt && html`<div class="row gap" style="align-items:baseline">${p.label && html`<span class="label">${p.label})</span>`}<${Md} src=${p.prompt} /></div>`}
        ${p.answer.type === 'text' ? html`<p class="small muted">Auf Papier lösen und unten fotografieren.</p>`
          : p.answer.type === 'choice' ? html`<div class="choice">${p.answer.options.map((o, k) => html`<label class=${(answers[ex.id] || {})[p.label] === k ? 'sel' : ''}><input type="radio" name=${ex.id + p.label} onChange=${() => setAnswers((a) => ({ ...a, [ex.id]: { ...(a[ex.id] || {}), [p.label]: k } }))} /><${Md} src=${o} /></label>`)}</div>`
          : html`<div class="answer-row"><${MathInput} value=${(answers[ex.id] || {})[p.label] || ''} placeholder=${p.answer.type === 'tuple' || p.answer.type === 'set' ? 'Werte mit ; trennen' : ''}
              onInput=${(v) => setAnswers((a) => ({ ...a, [ex.id]: { ...(a[ex.id] || {}), [p.label]: v } }))} />${p.answer.unit && html`<span class="muted" style="align-self:center">${p.answer.unit}</span>`}</div>`}
      </div>`)}
      <div class="row gap wrap" style="margin-top:.6rem"><${PhotoPicker} label="Lösungsweg fotografieren" exerciseId=${ex.id} onPhoto=${(ph) => setPhotos((x) => ({ ...x, [ex.id]: [...(x[ex.id] || []), ph.id] }))} /></div>
      <${Thumbs} ids=${photos[ex.id] || []} onRemove=${(id) => setPhotos((x) => ({ ...x, [ex.id]: x[ex.id].filter((y) => y !== id) }))} />
      <p class="small muted">Mit Foto wird die ganze Aufgabe inkl. Lösungsweg korrigiert (wie an der Prüfung). Ohne Foto zählt nur das eingegebene Resultat.</p>
    </section>`)}
    <button class="btn primary" onClick=${submit}>Prüfung abgeben</button>`;
}

// ───────────── Formelsammlung ─────────────
function FormulaCard({ k }) {
  return html`<article class="fcard" id=${'f-' + k.id}>
    <div class="row between gap"><h3 style="margin:0">${k.name}</h3>
      <span class="row gap noprint"><a class="btn small ghost" title="Im Formeltrainer üben" href=${`#/trainer?skill=${(k.skills || [])[0] || ''}`}>🧠</a>
        <a class="btn small ghost" title="Vom Tutor erklären lassen" href=${`#/tutor?erklaere=${encodeURIComponent(k.name)}`}>💬</a></span></div>
    <div class="formula-big"><${Md} src=${k.formula} /></div>
    ${k.symbols && k.symbols.length ? html`<table class="symbols"><tbody>${k.symbols.map((s) => html`<tr><td class="sym"><${Md} src=${s.sym} /></td><td><${Md} src=${s.desc} /></td></tr>`)}</tbody></table>` : ''}
    ${k.explain && html`<div class="small"><${Md} src=${k.explain} /></div>`}
    ${(k.example || k.pitfall) && html`<details><summary class="small">Beispiel${k.pitfall ? ' & typischer Fehler' : ''}</summary>
      ${k.example && html`<div class="solution small"><${Md} src=${k.example} /></div>`}${k.pitfall && html`<div class="hintbox small"><b>Achtung:</b> <${Md} src=${k.pitfall} /></div>`}</details>`}
  </article>`;
}

function Formeln() {
  const { data } = useApi('/api/formeln');
  const q0 = new URLSearchParams(location.hash.split('?')[1] || '');
  const [chap, setChap] = useState(q0.get('k') || null);
  const [topic, setTopic] = useState(q0.get('t') || null);
  const [q, setQ] = useState('');
  const [full, setFull] = useState(false);
  const [printing, setPrinting] = useState(q0.get('druck') === '1');
  useEffect(() => {
    if (!printing) return undefined;
    const done = () => setPrinting(false);
    window.addEventListener('afterprint', done);
    const t = setTimeout(() => window.print(), 400);
    return () => { clearTimeout(t); window.removeEventListener('afterprint', done); };
  }, [printing]);
  useEffect(() => {
    if (!data) return;
    const want = sessionStorage.getItem('formel-card');
    if (!want) return;
    sessionStorage.removeItem('formel-card');
    for (const c of data) for (const t of c.topics) if (t.cards.some((k) => k.id === want)) {
      setChap(c.id); setTopic(t.title);
      setTimeout(() => { const el = document.getElementById('f-' + want); if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('flash'); } }, 300);
    }
  }, [data]);
  if (!data) return html`<${Loading} />`;
  const withCards = data.filter((c) => c.topics.length);
  const sel = data.find((c) => c.id === chap);
  const norm = (x) => (x || '').toLowerCase();
  let results = null;
  if (q.trim()) {
    results = [];
    for (const c of data) for (const t of c.topics) for (const k of t.cards) {
      const hay = norm(k.name + ' ' + t.title + ' ' + (k.explain || '') + ' ' + (k.symbols || []).map((s) => s.desc).join(' ') + ' ' + k.formula);
      if (q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) results.push({ ...k, _ch: c.title, _t: t.title });
    }
  }
  const nav = html`<aside class="fnav card">
    <input type="text" placeholder="🔍 Formel suchen…" value=${q} onInput=${(e) => setQ(e.target.value)} />
    <ul class="list">${withCards.map((c) => html`<li>
      <button class=${`fnav-ch ${chap === c.id ? 'on' : ''}`} onClick=${() => { setChap(chap === c.id ? null : c.id); setTopic(null); setQ(''); setFull(false); }}>${c.icon} ${c.title}</button>
      ${chap === c.id && html`<ul class="fnav-topics">
        <li><button class=${!topic && !full ? 'on' : ''} onClick=${() => { setTopic(null); setFull(false); }}>Alle Themen</button></li>
        ${c.topics.map((t) => html`<li><button class=${topic === t.title ? 'on' : ''} onClick=${() => { setTopic(t.title); setFull(false); window.scrollTo(0, 0); }}>${t.title} <span class="muted">${t.cards.length}</span></button></li>`)}
        ${c.md && html`<li><button class=${full ? 'on' : ''} onClick=${() => { setFull(true); setTopic(null); }}>📄 Ganze Seite (Skript-Stil)</button></li>`}</ul>`}</li>`)}</ul>
  </aside>`;
  let body;
  if (printing) {
    const chs = sel ? [sel] : withCards;
    body = chs.map((c) => html`<h2>${c.icon} ${c.title}</h2>${c.topics.filter((t) => !topic || t.title === topic).map((t) => html`
      <h3 class="print-topic">${t.title}</h3>${t.cards.map((k) => html`<${FormulaCard} k=${k} />`)}`)}`);
  } else if (results) {
    body = html`<h2>${results.length} Treffer für «${q}»</h2>${results.map((k) => html`<div class="small muted">${k._ch} › ${k._t}</div><${FormulaCard} k=${k} />`)}`;
  } else if (!sel) {
    body = html`<h2>Übersicht</h2><p class="muted">Wähle ein Kapitel und ein Thema – oder suche direkt (z.B. «Vektorprodukt», «Kettenregel», «Halbwertszeit»).</p>
      <div class="grid g2">${withCards.map((c) => html`<section class="card clickable" onClick=${() => setChap(c.id)}><h3>${c.icon} ${c.title}${c.optional ? html` <span class="tag">Grundlagen</span>` : ''}</h3>
        <div class="row gap wrap">${c.topics.map((t) => html`<button class="chip" onClick=${(e) => { e.stopPropagation(); setChap(c.id); setTopic(t.title); }}>${t.title}</button>`)}</div></section>`)}</div>
      ${!withCards.length && html`<div class="card"><p class="muted">Die strukturierten Formelkarten werden gerade erstellt. Hier die Formelsammlung pro Kapitel:</p>${data.map((c) => c.md && html`<details><summary><b>${c.title}</b></summary><${Md} src=${c.md} /></details>`)}</div>`}`;
  } else if (full) {
    body = html`<h2>${sel.title}</h2><section class="card"><${Md} src=${sel.md} /></section>`;
  } else {
    const topics = sel.topics.filter((t) => !topic || t.title === topic);
    body = html`<div class="small muted"><a href="#/formeln" onClick=${(e) => { e.preventDefault(); setChap(null); setTopic(null); }}>Formelsammlung</a> › ${sel.title}${topic ? ` › ${topic}` : ''}</div>
      ${topics.map((t) => html`<h2 style="margin-top:1rem">${t.title}</h2>${t.cards.map((k) => html`<${FormulaCard} k=${k} />`)}`)}`;
  }
  const scope = sel ? `${sel.title}${topic ? ' – ' + topic : ''}` : 'ganze Formelsammlung';
  return html`<div class="row between wrap gap"><h1>📐 Formelsammlung${printing ? html` <span class="small muted">· Mathematik II</span>` : ''}</h1>
      <button class="btn small noprint" title=${`Drucken: ${scope}`} onClick=${() => setPrinting(true)}>🖨 Drucken (${scope})</button></div>
    <div class="fwrap">${nav}<div class="fbody">${body}</div></div>`;
}

// ───────────── rank ladder ─────────────
function RankPage() {
  const { data: r } = useApi('/api/rank');
  if (!r) return html`<${Loading} />`;
  return html`<h1>Dienstgrade</h1><p class="muted">Du startest als Rekrut. Für jede Beförderung brauchst du XP <b>und</b> echtes Können – XP allein reichen nicht.</p>
    <div class="ladder">${r.ranks.slice().reverse().map((x, i) => { const idx = r.ranks.length - 1 - i; return html`
      <div class=${`step ${idx === r.index ? 'cur' : ''} ${idx > r.index ? 'locked' : ''}`}>
        <span class="ladder-fig"><${Avatar} rankId=${x.id} size=${84} cls=${idx > r.index ? 'locked-fig' : ''} />${x.badge ? html`<img src=${x.badge} alt="" />` : html`<div class="nob"></div>`}</span>
        <div><b>${x.name}</b> <span class="muted small">(${x.abbr})</span>
          ${idx > 0 && html`<ul class="checks" style="color:var(--fg)">${x.checks.map((c) => html`<li><span class=${`ck ${c.ok ? 'ok' : ''}`} style=${c.ok ? '' : 'background:var(--muted-bg)'}>${c.ok ? '✓' : ''}</span>${c.text}</li>`)}</ul>`}</div>
        <span>${idx === r.index ? html`<span class="tag acc">aktuell</span>` : idx < r.index ? '✅' : '🔒'}</span></div>`; })}</div>`;
}


// ───────────── avatar ─────────────
let AVATARS = null;
function useAvatars() {
  const [a, setA] = useState(AVATARS);
  useEffect(() => { if (!AVATARS) api('/api/avatar').then((d) => { AVATARS = d.images; setA(d.images); }).catch(() => {}); }, []);
  return a || {};
}
export function Avatar({ rankId, size = 120, cls = '' }) {
  const imgs = useAvatars();
  const src = imgs[rankId] || imgs['default'];
  if (!src) return null;
  return html`<img class=${`avatar ${cls}`} src=${src} style=${`height:${size}px`} alt="Dein Charakter" />`;
}

// ───────────── formula trainer ─────────────
function FormulaTrainer({ chapter, skill }) {
  const { data } = useApi('/api/cards');
  const [mode, setMode] = useState(null);
  if (mode) return html`<${CardSession} chapter=${chapter} skill=${skill} mode=${mode} onExit=${() => setMode(null)} />`;
  if (!data) return html`<${Loading} />`;
  const decks = data.decks;
  const pick = (cid, m) => { go(`/trainer?kapitel=${cid || ''}`); setMode(m); };
  return html`<h1>🧠 Formeltrainer</h1>
    <p class="muted">Formeln sitzen erst, wenn du sie abrufen kannst. Karteikarten kommen nach dem Lernkartei-Prinzip zurück: was du gut kannst seltener, was wackelt bald wieder.</p>
    <div class="grid g3" style="margin-bottom:1rem">
      <button class="card clickable" style="text-align:left;font:inherit;color:inherit" onClick=${() => pick(null, 'flip')}><h3>🃏 Karteikarten</h3><div class="small muted">Alle fälligen Karten aus allen Kapiteln</div></button>
      <button class="card clickable" style="text-align:left;font:inherit;color:inherit" onClick=${() => pick(null, 'drill')}><h3>✏️ Schnell-Drill</h3><div class="small muted">Formel anwenden: kurze Rechnungen, sofort geprüft</div></button>
      <button class="card clickable" style="text-align:left;font:inherit;color:inherit" onClick=${() => pick(null, 'sprint')}><h3>⏱️ 60-Sekunden-Sprint</h3><div class="small muted">Wie viele schaffst du in einer Minute?</div></button>
    </div>
    <section class="card"><h2>Nach Kapitel</h2><ul class="list">${decks.map((d) => html`<li class="row between gap wrap">
      <span>${d.icon} <b>${d.title}</b>${d.optional ? html` <span class="tag">Grundlagen</span>` : ''}<br/><span class="small muted">${d.total} Karten · ${d.learned} sitzen · ${d.new} neu</span></span>
      <span class="row gap">${d.due ? html`<span class="tag acc">${d.due} fällig</span>` : html`<span class="tag ok">✓</span>`}
        <button class="btn small" onClick=${() => pick(d.chapter, 'flip')}>Karten</button><button class="btn small" onClick=${() => pick(d.chapter, 'drill')}>Drill</button><button class="btn small" onClick=${() => pick(d.chapter, 'sprint')}>Sprint</button></span></li>`)}</ul></section>`;
}

function CardSession({ chapter, skill, mode, onExit }) {
  const [cards, setCards] = useState(null);
  const [i, setI] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [di, setDi] = useState(0);
  const [inp, setInp] = useState('');
  const [res, setRes] = useState(null);
  const [score, setScore] = useState({ ok: 0, total: 0 });
  const [end, setEnd] = useState(mode === 'sprint' ? Date.now() + 60000 : null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const p = new URLSearchParams(); if (chapter) p.set('chapter', chapter); if (skill) p.set('skill', skill); p.set('limit', mode === 'flip' ? 20 : 60);
    api(`/api/cards/session?${p}`).then((c) => { const list = mode === 'flip' ? c : c.filter((k) => k.drill.length); if (mode !== 'flip') list.sort(() => Math.random() - 0.5); setCards(list); });
  }, []);
  useEffect(() => { if (!end) return; const t = setInterval(() => setNow(Date.now()), 250); return () => clearInterval(t); }, [end]);
  if (!cards) return html`<${Loading} />`;
  const timeUp = end && now >= end;
  if (!cards.length) return html`<section class="card center"><p>Keine Karten gefunden.</p><button class="btn" onClick=${onExit}>Zurück</button></section>`;
  if (i >= cards.length || timeUp) {
    return html`<section class="card center"><h2>${mode === 'sprint' ? '⏱️ Zeit um!' : 'Geschafft! 🎉'}</h2>
      ${mode !== 'flip' && html`<div class="rank-name">${score.ok} / ${score.total}</div><p class="muted">richtig${mode === 'sprint' ? ' in 60 Sekunden' : ''}</p>`}
      ${mode === 'sprint' && html`<p class="small muted">Bestwert schlagen? Gleich nochmal!</p>`}
      <div class="row gap" style="justify-content:center"><button class="btn primary" onClick=${() => { setI(0); setScore({ ok: 0, total: 0 }); setRes(null); setInp(''); if (mode === 'sprint') setEnd(Date.now() + 60000); setCards(cards.slice().sort(() => Math.random() - 0.5)); }}>Nochmal</button><button class="btn" onClick=${onExit}>Fertig</button></div></section>`;
  }
  const k = cards[i];
  const next = () => { setI(i + 1); setFlipped(false); setRes(null); setInp(''); setDi(Math.floor(Math.random() * Math.max(1, (cards[i + 1] || k).drill.length))); };
  const rate = async (grade) => { await api(`/api/cards/${k.id}/rate`, { method: 'POST', body: { grade, kind: mode } }); next(); };
  const drill = k.drill[di % Math.max(1, k.drill.length)];
  const check = async () => {
    if (!drill) return;
    const r = await api(`/api/cards/${k.id}/drill`, { method: 'POST', body: { index: di % k.drill.length, input: inp } });
    if (r.status === 'format') { setRes(r); return; }
    setRes(r); setScore((s) => ({ ok: s.ok + (r.ok ? 1 : 0), total: s.total + 1 }));
    api(`/api/cards/${k.id}/rate`, { method: 'POST', body: { grade: r.ok ? 'good' : 'again', kind: mode } });
    if (r.ok && mode === 'sprint') setTimeout(next, 450);
  };
  const left = end ? Math.max(0, Math.ceil((end - now) / 1000)) : null;
  return html`<div class="row between"><button class="btn small ghost" onClick=${onExit}>← Zurück</button>
      <span class="small muted">${mode === 'sprint' ? html`<span class=${`tag ${left < 10 ? 'bad' : 'info'}`}>⏱ ${left}s</span> · ${score.ok} richtig` : `${i + 1} / ${cards.length}`}</span></div>
    <section class="card flashcard">
      <div class="row between"><span class="small muted">${k.topic || ''}</span><${CardReport} k=${k} /></div>
      <h2>${k.name}</h2>
      ${mode === 'flip' ? html`
        ${!flipped ? html`<p class="muted">Wie lautet die Formel? Sag sie dir vor oder schreib sie auf – dann umdrehen.</p>
          <button class="btn primary" onClick=${() => setFlipped(true)}>Umdrehen</button>`
        : html`<div class="formula-big"><${Md} src=${k.formula} /></div>
          ${k.symbols && k.symbols.length ? html`<table class="symbols"><tbody>${k.symbols.map((sy) => html`<tr><td class="sym"><${Md} src=${sy.sym} /></td><td><${Md} src=${sy.desc} /></td></tr>`)}</tbody></table>` : ''}
          ${k.explain && html`<${Md} src=${k.explain} />`}
          ${k.example && html`<div class="solution"><b>Beispiel:</b> <${Md} src=${k.example} /></div>`}
          ${k.pitfall && html`<div class="hintbox"><b>Achtung:</b> <${Md} src=${k.pitfall} /></div>`}
          <p class="small muted">Wie gut wusstest du es?</p>
          <div class="row gap wrap"><button class="btn" style="border-color:var(--bad)" onClick=${() => rate('again')}>Nochmal</button><button class="btn" onClick=${() => rate('hard')}>Schwer</button>
            <button class="btn primary" onClick=${() => rate('good')}>Gut</button><button class="btn ok" onClick=${() => rate('easy')}>Leicht</button></div>`}`
      : html`${drill && html`<${Md} src=${drill.prompt} />
          <div class="answer-row"><${MathInput} key=${k.id + di} value=${inp} onInput=${setInp} onEnter=${res && res.status !== 'format' ? next : check} autofocus=${true}
            placeholder=${drill.answer.type === 'set' || drill.answer.type === 'tuple' ? 'Werte mit ; trennen' : ''} />
            ${!res || res.status === 'format' ? html`<button class="btn primary" onClick=${check}>Prüfen</button>` : html`<button class="btn primary" onClick=${next}>Weiter</button>`}</div>
          ${drill.answer.type === 'choice' && html`<p class="small muted">Antwort als Nummer der Option (0, 1, …)</p>`}
          ${res && html`<div class=${`feedback ${res.status}`}>${res.ok ? '✅ Richtig!' : res.status === 'format' ? '⚠️ ' + res.message : html`❌ Richtig wäre: <code>${res.expected}</code>`}</div>`}
          ${res && !res.ok && res.status !== 'format' && html`<div class="formula-big"><${Md} src=${k.formula} /></div>`}`}
        ${mode === 'drill' && html`<details style="margin-top:.5rem"><summary class="small muted">Formel anzeigen</summary><${Md} src=${k.formula} /></details>`}`}
    </section>`;
}


function CardReport({ k }) {
  const fake = { id: `card:${k.id}`, title: `Formelkarte «${k.name}»`, parts: [{ label: '' }] };
  return html`<${ReportButton} ex=${fake} />`;
}

// ───────────── Grundlagen ─────────────
function Basics() {
  const { data } = useApi('/api/curriculum');
  if (!data) return html`<${Loading} />`;
  const basics = data.chapters.filter((c) => c.optional);
  return html`<h1>🧮 Grundlagen-Training</h1>
    <p class="muted">Freiwilliger Trainingsplatz für das Handwerkszeug: Brüche, Potenzen, Gleichungen, Trigonometrie im Dreieck … Zählt nicht für die Beförderung – aber alles in Mathe II baut darauf auf. Unbegrenzt neue Aufgaben.</p>
    ${basics.map((c) => html`<section class="card"><div class="row between wrap gap"><h2 style="margin:0">${c.icon} ${c.title}</h2>
      <div class="row gap"><a class="btn small" href=${`#/kapitel/${c.id}?tab=theorie`}>Erklärungen</a><a class="btn small" href=${`#/trainer?kapitel=${c.id}`}>Formeln</a><a class="btn primary small" href=${`#/ueben?chapter=${c.id}`}>Mix üben</a></div></div>
      ${c.skills.map((s) => html`<div class="skill"><div><b>${s.title}</b><div class="small muted">${levelText(s.mastery, s.n)}${s.n ? ` · ${s.n} Versuche` : ''}</div></div>
        <${Bar} value=${s.mastery} color=${levelColor(s.mastery, s.n)} /><a class="btn small" href=${`#/ueben?skill=${s.id}`}>Üben</a></div>`)}</section>`)}`;
}

// ───────────── medals ─────────────
function MedalsPage() {
  const { data } = useApi('/api/medals');
  if (!data) return html`<${Loading} />`;
  const earned = data.medals.filter((m) => m.earned).length;
  return html`<h1>🏅 Medaillen</h1><p class="muted">${earned} von ${data.medals.length} gesammelt.</p>
    <div class="medals">${data.medals.map((m) => html`<div class=${`medal ${m.earned ? 'on' : ''}`}><span class="mi">${m.earned ? m.icon : '🔒'}</span><span>${m.title}</span></div>`)}</div>`;
}

function MorePage() {
  const items = [['/trainer', '🧠', 'Formeltrainer'], ['/grundlagen', '🧮', 'Grundlagen'], ['/pruefung', '📝', 'Prüfungssimulation'], ['/formeln', '📐', 'Formelsammlung'], ['/rang', '🎖️', 'Dienstgrade'], ['/medaillen', '🏅', 'Medaillen'], ['/kapitel', '📚', 'Kapitel']];
  return html`<h1>Mehr</h1><div class="grid g2">${items.map(([h, i, l]) => html`<a class="card row gap" style="color:inherit" href=${'#' + h}><span style="font-size:1.6rem">${i}</span><b>${l}</b></a>`)}</div>`;
}

// ───────────── formulas drawer (inside exercises) ─────────────
function FormulasDrawer({ exId, onClose, onAsk }) {
  const { data } = useApi(`/api/exercise/${exId}/formulas`);
  return html`<div class="drawer"><div class="row between"><b>📐 Formeln zu dieser Aufgabe</b><button class="btn small" onClick=${onClose}>Schliessen</button></div>
    <div style="overflow-y:auto;flex:1">
    ${!data ? html`<${Loading} />` : html`
      ${data.cards.length ? data.cards.map((k) => html`<${FormulaCard} k=${k} />`)
        : html`<p class="muted">Für dieses Thema gibt es noch keine Formelkarten.</p>`}
      <div class="card"><b>Mehr dazu</b><ul class="list small">
        ${data.skills.map((s) => html`<li class="row between gap"><span>${s.title} <span class="muted">(Skript ${s.skript})</span></span>
          <span class="row gap"><button class="btn small" onClick=${() => onAsk(s.title)}>💬 Erklär mir</button><a class="btn small" href=${`#/trainer?skill=${s.id}`}>🧠 Üben</a></span></li>`)}
        <li><a href=${`#/kapitel/${data.chapter}?tab=formeln`}>📐 Formelsammlung ${data.chapter_title}</a> · <a href=${`#/kapitel/${data.chapter}?tab=theorie`}>📖 Theorie</a></li></ul></div>`}
    </div></div>`;
}

render(html`<${App} />`, document.getElementById('app'));
