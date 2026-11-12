import {
  html, render, useState, useEffect, useMemo, api, useRoute, go, Md, Chat, SolutionSteps, Bar, Ring, ProgressChart, Loading, useApi,
  userText, MathText, FeedbackButton, pct, fmtDate, fmtDateTime, fmtIso, ago, levelColor, levelText, toast, Thumbs,
} from './common.js';

const NAV = [
  ['/', 'Übersicht'], ['/schwachstellen', 'Schwachstellen'], ['/briefing', 'Session-Briefing'], ['/verlauf', 'Verlauf'],
  ['/aufgaben', 'Aufgaben'], ['/fehler', 'Fehlermeldungen'], ['/feedback', 'Feedback'], ['/auftraege', 'Aufträge'], ['/chats', 'Tutor-Chats'], ['/coach', 'Coach-Assistent'], ['/einstellungen', 'Einstellungen'],
];

let CUR = null;
let STUDENT = 'Student';
function useCurriculum() {
  const [c, setC] = useState(CUR);
  useEffect(() => { if (!CUR) api('/api/curriculum').then((d) => { CUR = d; setC(d); }); }, []);
  return c;
}
const skillTitle = (id) => { if (!CUR) return id; for (const ch of CUR.chapters) for (const s of ch.skills) if (s.id === id) return s.title; return id; };
const errTitle = (id) => (CUR && CUR.error_categories[id]) || id || '–';

function App() {
  const route = useRoute();
  const cur = useCurriculum();
  useEffect(() => { api('/api/me').then((m) => { window.__appVersion = m.version; }).catch(() => {}); }, []);
  const p = route.parts;
  const active = (h) => (h === '/' ? route.path === '/' : route.path.startsWith(h));
  let page;
  if (!cur) page = html`<${Loading} />`;
  else switch (p[0]) {
    case undefined: page = html`<${Overview} />`; break;
    case 'schwachstellen': page = html`<${Struggles} />`; break;
    case 'briefing': page = html`<${Briefing} />`; break;
    case 'verlauf': page = html`<${History} q=${route.q} />`; break;
    case 'versuch': page = html`<${AttemptDetail} id=${+p[1]} />`; break;
    case 'aufgaben': page = p[1] ? html`<${ExerciseView} id=${decodeURIComponent(p[1])} />` : html`<${Catalogue} q=${route.q} />`; break;
    case 'auftraege': page = html`<${Assignments} />`; break;
    case 'fehler': page = html`<${Reports} />`; break;
    case 'feedback': page = html`<${FeedbackPage} />`; break;
    case 'chats': page = p[1] ? html`<${ChatView} id=${+p[1]} />` : html`<${Chats} />`; break;
    case 'coach': page = html`<${Coach} chatId=${p[1] ? +p[1] : null} />`; break;
    case 'einstellungen': page = html`<${Settings} />`; break;
    default: page = html`<p>Nicht gefunden.</p>`;
  }
  return html`<header class="topbar"><a class="brand" href="#/"><span class="tri"></span>Coach</a>
      <a class="me" href="/">Schülersicht ↗</a></header>
    <div class="noprint" style="background:var(--card);border-bottom:1px solid var(--line);overflow-x:auto"><div class="chips" style="padding:.4rem 1rem">
      ${NAV.map(([h, l]) => html`<a class=${`chip ${active(h) ? 'on' : ''}`} href=${'#' + h}>${l}</a>`)}</div></div>
    <main>${page}</main>
    <${FeedbackButton} />`;
}

// ───────────── overview ─────────────
function Overview() {
  const { data: d } = useApi('/api/admin/overview');
  const { data: hist } = useApi('/api/admin/history?days=45');
  if (!d) return html`<${Loading} />`;
  const errs = Object.entries(d.errors.categories).sort((a, b) => b[1] - a[1]);
  const maxErr = Math.max(1, ...errs.map((e) => e[1]));
  const act = Object.fromEntries((d.activity || []).map((a) => [a.day, a.seconds]));
  const days = []; for (let i = 59; i >= 0; i--) { const dd = new Date(Date.now() - i * 864e5); days.push(dd.toISOString().slice(0, 10)); }
  return html`<div class="row between wrap gap"><h1>${d.student}: Lernstand</h1><span class="muted small">Zuletzt aktiv: ${ago(d.last_activity)}</span></div>
    <div class="grid g4" style="margin-bottom:1rem">
      <div class="kpi"><div class="l">Prüfungsfit</div><div class="v">${pct(d.readiness)}</div><div class="d muted">${d.mastered}/${d.skills_total} Themen sicher</div></div>
      <div class="kpi"><div class="l">Diese Woche</div><div class="v">${d.week.correct}/${d.week.parts}</div><div class="d muted">richtig · ${d.week.minutes} min</div></div>
      <div class="kpi"><div class="l">Trefferquote</div><div class="v">${pct(d.week.accuracy)}</div><div class="d muted">Vorwoche ${pct(d.last_week.accuracy)}</div></div>
      <div class="kpi"><div class="l">Rang</div><div class="v" style="font-size:1.2rem">${d.rank.rank.name}</div><div class="d muted">${d.rank.xp} XP · Serie ${d.streak} T.</div></div>
    </div>
    ${d.disagreements > 0 && html`<div class="feedback fast">⚠️ ${d.disagreements} Korrektur(en), bei denen KI und Antwortprüfer uneinig waren – <a href="#/verlauf?flag=1">ansehen</a>.</div>`}
    <section class="card"><h2>Beherrschung pro Thema</h2><p class="small muted">Farbe = Beherrschung (grün ≥ 80 %, gelb ≥ 50 %, rot darunter, grau = noch nie geübt). Klick → Versuche.</p>
      ${CUR.chapters.filter((c) => !c.optional).map((c) => html`<div style="margin:.5rem 0"><div class="row between"><b>${c.icon} ${c.title}</b><span class="small">${pct(d.chapters[c.id])}</span></div>
        <div class="heat" style=${`grid-template-columns:repeat(${Math.min(c.skills.length, 6)},minmax(0,1fr))`}>
        ${c.skills.map((s) => { const v = d.skills[s.id]; return html`<div class=${`cell ${v.n ? '' : 'neu'}`} style=${`background:${v.n ? levelColor(v.mastery, v.n) : 'var(--muted-bg)'}`}
          title=${`${s.title}: ${pct(v.mastery)} · ${v.n} Versuche · Ø ${v.hints} Hinweise`} onClick=${() => go(`/verlauf?skill=${s.id}`)}>
          <span>${s.title}</span><span>${v.n ? `${pct(v.mastery)} · ${v.n}×` : 'neu'}</span></div>`; })}</div></div>`)}
      <details><summary class="small">Grundlagen (freiwillig)</summary>${CUR.chapters.filter((c) => c.optional).map((c) => html`<div style="margin:.5rem 0"><b>${c.title}</b>
        <div class="heat" style="grid-template-columns:repeat(6,minmax(0,1fr))">${c.skills.map((s) => { const v = d.skills[s.id]; return html`<div class=${`cell ${v.n ? '' : 'neu'}`} style=${`background:${v.n ? levelColor(v.mastery, v.n) : 'var(--muted-bg)'}`}><span>${s.title}</span><span>${v.n ? pct(v.mastery) : 'neu'}</span></div>`; })}</div></div>`)}</details>
    </section>
    <div class="grid g2">
      <section class="card"><h2>Fortschritt (45 Tage)</h2>${hist ? html`<${ProgressChart} data=${hist} />` : html`<${Loading} />`}</section>
      <section class="card"><h2>Häufigste Fehlertypen</h2>${errs.length ? errs.map(([k, n]) => html`<div class="hbar"><span>${errTitle(k)}</span><${Bar} value=${n / maxErr} color="var(--bad)" height=${10} /><b>${n}</b></div>`) : html`<p class="muted">Noch keine kategorisierten Fehler (die Kategorien kommen aus Foto-Korrekturen und dem Vorzeichen-Check).</p>`}</section>
    </div>
    <div class="grid g2">
      <section class="card"><h2>Aktivität (60 Tage)</h2><div class="cal">${days.map((dd) => { const s = act[dd] || 0; return html`<div title=${`${dd}: ${Math.round(s / 60)} min`} style=${s ? `background:var(--accent);opacity:${Math.min(1, 0.3 + s / 3600)}` : ''}></div>`; })}</div>
        <p class="small muted">${d.hints_total} Hinweise genutzt · ${d.chat_count} Tutor-Gespräche · Revanchen: ${d.challenges_open} offen, ${d.challenges_won} gewonnen</p></section>
      <section class="card"><h2>Prüfungssimulationen</h2>${d.exam_runs.length ? html`<ul class="list">${d.exam_runs.map((r) => html`<li class="row between"><span>${r.title}<br/><span class="small muted">${fmtDateTime(r.started_at)}</span></span><b>${Math.round(100 * r.score / r.max_score)} %</b></li>`)}</ul>` : html`<p class="muted">Noch keine.</p>`}</section>
    </div>`;
}

// ───────────── struggles ─────────────
function Struggles() {
  const { data: d } = useApi('/api/admin/struggles');
  const [open, setOpen] = useState(null);
  if (!d) return html`<${Loading} />`;
  return html`<h1>Wo ${STUDENT} kämpft</h1>
    <section class="card"><h2>Themen (schwächste zuerst)</h2>
      <div class="table-wrap"><table class="t"><thead><tr><th>Thema</th><th>Beherrschung</th><th>Versuche</th><th>Falsch</th><th>Ø Hinweise</th><th>Fehlertypen</th><th></th></tr></thead><tbody>
      ${d.skills.map((s) => html`<tr>
        <td><b>${s.title}</b><div class="small muted">${s.chapter}</div></td>
        <td style="min-width:110px"><${Bar} value=${s.mastery} color=${levelColor(s.mastery, s.n)} /><span class="small">${pct(s.mastery)}</span></td>
        <td>${s.n}</td><td>${s.wrong}</td><td>${s.hints}</td>
        <td class="small">${Object.entries(s.errors).sort((a, b) => b[1] - a[1]).map(([k, n]) => html`<span class="tag bad" style="margin:1px">${errTitle(k)} ${n}</span>`)}</td>
        <td><button class="btn small" onClick=${() => setOpen(open === s.skill ? null : s.skill)}>${open === s.skill ? 'zu' : 'Details'}</button></td></tr>
        ${open === s.skill && html`<tr><td colspan="7"><b>Letzte Fehler:</b><ul class="list small">${s.recent_wrong.map((r) => html`<li class="clickable" onClick=${() => go(`/versuch/${r.id}`)}>
          ${fmtDateTime(r.created_at)} · <b>${r.title}</b>${r.part ? ` (${r.part})` : ''} · Eingabe: <code>${r.input ?? '–'}</code> ${r.error_category ? html`<span class="tag bad">${errTitle(r.error_category)}</span>` : ''}
          ${r.feedback ? html`<div class="muted">${r.feedback}</div>` : ''}</li>`)}</ul>
          ${s.repeat_fail.length ? html`<p class="small"><b>Mehrfach falsch:</b> ${s.repeat_fail.map((e) => html`<a href=${`#/aufgaben/${encodeURIComponent(e)}`}>${e}</a> `)}</p>` : ''}</td></tr>`}`)}
      </tbody></table></div></section>
    <section class="card"><h2>Revanchen – Lehrer-Ansicht</h2><p class="small muted">Aufgaben, die ${STUDENT} nicht konnte, mit Lösung und seinen Eingaben – zur Vorbereitung. Deine Ansicht verändert seinen Fortschritt nicht.</p>
      ${d.challenges.length ? d.challenges.map((c) => html`<details class="card" style="margin:.5rem 0"><summary><b>${c.title}</b>${c.part ? ` (${c.part})` : ''} · ${c.skill_title}
          <span class=${`tag ${c.status === 'beaten' ? 'ok' : 'bad'}`}>${c.status === 'beaten' ? 'gewonnen' : `${c.fails}× falsch, ${c.wins}/2`}</span></summary>
        ${c.exercise && html`<${ExerciseReveal} ex=${c.exercise} highlight=${c.part} />`}
        <h4>Seine Versuche</h4><ul class="list small">${c.inputs.map((a) => html`<li>${fmtDateTime(a.created_at)} · <code>${a.input ?? '(Lösung angezeigt)'}</code> <span class=${`tag ${a.status === 'richtig' ? 'ok' : 'bad'}`}>${a.status}</span>
          ${a.error_category ? html`<span class="tag">${errTitle(a.error_category)}</span>` : ''}${a.feedback ? html`<div class="muted">${a.feedback}</div>` : ''}</li>`)}</ul></details>`) : html`<p class="muted">Keine Revanchen.</p>`}
    </section>`;
}

function ExerciseReveal({ ex, highlight }) {
  return html`<div><div class="small muted">${ex.source.doc} ${ex.source.ref || ''} · ${ex.id}${ex.note ? html` · <span class="tag warn" title=${ex.note}>Hinweis</span>` : ''}</div>
    <${Md} src=${ex.statement} />${(ex.figures || []).map((f) => html`<img class="figure" src=${`/figures/${f}`} />`)}
    ${ex.note && html`<div class="feedback fast small">${ex.note}</div>`}
    ${ex.parts.map((p) => html`<div class="part" style=${highlight !== undefined && highlight === p.label ? 'background:var(--warn-soft);border-radius:8px;padding:.5rem' : ''}>
      ${p.label && html`<span class="label">${p.label})</span>`}<${Md} src=${p.prompt} />
      <div class="small"><b>Erwartet:</b> <code>${Array.isArray(p.expected) ? p.expected.join('; ') : String(p.expected)}</code> ${p.answer.unit || ''}</div>
      <details><summary class="small">Lösungsweg & Hinweise</summary><${SolutionSteps} sol=${{ md: p.solution, steps: p.steps }} />${(p.hints || []).map((h, i) => html`<div class="hintbox small"><b>H${i + 1}:</b> <${Md} src=${h} /></div>`)}</details></div>`)}</div>`;
}

// ───────────── briefing ─────────────
function Briefing() {
  const { data: b, reload } = useApi('/api/admin/briefing');
  const { data: sessions, reload: rs } = useApi('/api/admin/sessions');
  const [aiChat, setAiChat] = useState(null);
  const [notes, setNotes] = useState('');
  if (!b) return html`<${Loading} />`;
  const active = (sessions || []).find((s) => s.started_at && !s.ended_at);
  const sessionAction = async (action) => {
    const body = { action, title: `Session ${fmtIso(b.dates.next_session)}`, date: b.dates.next_session };
    if (active) body.id = active.id;
    if (action === 'end') body.notes = notes;
    await api('/api/admin/sessions', { method: 'POST', body }); rs(); reload();
  };
  const startAi = async () => {
    const r = await api('/api/chats', { method: 'POST', body: { title: `Briefing ${new Date().toLocaleDateString('de-CH')}`, kind: 'admin' } });
    setAiChat(r.id);
  };
  const st = b.stats;
  return html`<div class="row between wrap gap"><h1>Session-Briefing</h1><div class="row gap noprint"><button class="btn" onClick=${() => print()}>🖨 Drucken</button>
      ${active ? html`<button class="btn primary" onClick=${() => sessionAction('end')}>Session beenden</button>` : html`<button class="btn primary" onClick=${() => sessionAction('start')}>Session starten</button>`}</div></div>
    <p class="muted">Seit ${fmtDateTime(b.since)} · nächste Session: <b>${fmtIso(b.dates.next_session)}</b> (in ${b.dates.days_to_session ?? '–'} Tagen) · Prüfung in ${b.dates.days_to_exam} Tagen · Prüfungsfit ${pct(b.readiness)}</p>
    ${active && html`<section class="card" style="border-color:var(--accent)"><b>🔴 Session läuft seit ${fmtDateTime(active.started_at)}</b> – ${STUDENT}s Aufgaben werden ihr zugeordnet.
      <label class="field">Notizen zur Session<textarea rows="3" value=${notes} onInput=${(e) => setNotes(e.target.value)} placeholder="Was habt ihr gemacht, was ist aufgefallen?"></textarea></label></section>`}
    <div class="grid g4" style="margin-bottom:1rem">
      <div class="kpi"><div class="l">Teilaufgaben</div><div class="v">${st.correct}/${st.parts}</div><div class="d muted">richtig</div></div>
      <div class="kpi"><div class="l">Lernzeit</div><div class="v">${st.minutes}<span class="small"> min</span></div><div class="d muted">an ${st.days_active} Tagen</div></div>
      <div class="kpi"><div class="l">Hinweise</div><div class="v">${st.hints}</div><div class="d muted">${st.solutions_shown}× Lösung angezeigt</div></div>
      <div class="kpi"><div class="l">Offene Revanchen</div><div class="v">${b.challenges_open.length}</div></div>
    </div>
    <div class="grid g2">
      <section class="card"><h2>Veränderung pro Thema</h2>${b.skill_changes.length ? html`<table class="t"><tbody>${b.skill_changes.map((c) => html`<tr><td>${c.title}</td>
        <td class="small">${pct(c.before)} → <b>${pct(c.now)}</b></td><td>${c.now > c.before + 0.02 ? html`<span class="up">▲</span>` : c.now < c.before - 0.02 ? html`<span class="down">▼</span>` : '·'}</td></tr>`)}</tbody></table>` : html`<p class="muted">Keine Veränderungen.</p>`}</section>
      <section class="card"><h2>Fehlertypen</h2>${Object.keys(b.errors).length ? Object.entries(b.errors).sort((a, x) => x[1] - a[1]).map(([k, n]) => html`<div class="row between"><span>${b.error_titles[k] || k}</span><b>${n}</b></div>`) : html`<p class="muted">Keine.</p>`}
        ${b.explain_back.length ? html`<h3 style="margin-top:1rem">«Erklär's zurück»-Versuche</h3>${b.explain_back.map((e) => html`<blockquote class="small">${e.content}</blockquote>`)}` : ''}</section>
    </div>
    <section class="card"><h2>Woran er gescheitert ist</h2>${b.failed.length ? html`<ul class="list">${b.failed.map((f) => html`<li><a href=${`#/aufgaben/${encodeURIComponent(f.exercise_id)}`}><b>${f.title}</b></a>${f.part ? ` (${f.part})` : ''} · <span class="muted">${skillTitle(f.skill)}</span>
      <div class="small">Eingaben: ${f.inputs.map((i) => html`<code style="margin-right:.3rem">${i ?? '(Lösung)'}</code>`)} ${f.errors.map((e) => html`<span class="tag bad">${b.error_titles[e] || e}</span>`)}</div>
      ${f.feedback.slice(0, 2).map((fb) => html`<div class="small muted">${fb}</div>`)}</li>`)}</ul>` : html`<p class="muted">Nichts – entweder alles richtig oder nicht geübt.</p>`}</section>
    <section class="card"><h2>Vorschlag für die Session</h2><p class="small muted">Je zwei Aufgaben zu den drei schwächsten Themen – mit Lösung, zum gemeinsamen Durchgehen.</p>
      ${b.suggestions.map((s) => html`<details class="card" style="margin:.4rem 0"><summary><b>${s.skill_title}</b>: ${s.title} <span class="muted small">(${s.id})</span></summary><${SuggestedEx} id=${s.id} /></details>`)}</section>
    <section class="card noprint"><h2>🤖 KI-Briefing</h2><p class="small muted">Der Assistent bekommt alle Daten oben und schreibt dir eine Analyse: Fehlvorstellungen, Erklärungsstrategien, Ablauf für die Session. Du kannst nachfragen.</p>
      ${aiChat ? html`<${Chat} chatId=${aiChat} adminKind=${true} modes=${false} compact=${true} prefill="Bitte erstelle mir ein kompaktes Briefing für die nächste Lernsession mit ${STUDENT}: 1) Stand in 3 Sätzen, 2) die 3 wichtigsten Baustellen mit vermuteter Fehlvorstellung, 3) Ablaufvorschlag für 2 Stunden mit konkreten Aufgaben, 4) wie ich die Themen am besten erkläre." />`
        : html`<button class="btn primary" onClick=${startAi}>KI-Briefing starten</button>`}</section>
    <section class="card"><h2>Bisherige Sessions</h2>${(sessions || []).length ? html`<ul class="list">${sessions.map((s) => html`<li><b>${s.title || s.date}</b> <span class="small muted">${fmtDateTime(s.started_at)} – ${s.ended_at ? fmtDateTime(s.ended_at) : 'läuft'}${s.stats ? ` · ${s.stats.ok || 0}/${s.stats.n} richtig` : ''}</span>${s.notes ? html`<div class="small">${s.notes}</div>` : ''}</li>`)}</ul>` : html`<p class="muted">Noch keine.</p>`}</section>`;
}
function SuggestedEx({ id }) {
  const { data } = useApi(`/api/exercise/${encodeURIComponent(id)}?reveal=true`);
  return data ? html`<${ExerciseReveal} ex=${data} />` : html`<${Loading} />`;
}

// ───────────── history ─────────────
function History({ q }) {
  const [skill, setSkill] = useState(q.skill || '');
  const [wrong, setWrong] = useState(false);
  const { data } = useApi(`/api/admin/attempts?limit=300${skill ? `&skill=${skill}` : ''}${wrong ? '&only_wrong=true' : ''}`, [skill, wrong]);
  const rows = (data || []).filter((r) => !q.flag || r.admin_note);
  return html`<h1>Verlauf</h1>
    <div class="row gap wrap" style="margin-bottom:.6rem"><select style="max-width:320px" value=${skill} onChange=${(e) => setSkill(e.target.value)}><option value="">Alle Themen</option>
      ${CUR.chapters.map((c) => html`<optgroup label=${c.title}>${c.skills.map((s) => html`<option value=${s.id}>${s.title}</option>`)}</optgroup>`)}</select>
      <label class="row gap small"><input type="checkbox" checked=${wrong} onChange=${(e) => setWrong(e.target.checked)} /> nur falsche</label></div>
    <section class="card table-wrap">${!data ? html`<${Loading} />` : html`<table class="t"><thead><tr><th>Zeit</th><th>Aufgabe</th><th>Eingabe</th><th>Ergebnis</th><th>Hilfe</th><th>Quelle</th></tr></thead><tbody>
      ${rows.map((r) => html`<tr class="clickable" onClick=${() => go(`/versuch/${r.id}`)}><td class="small">${fmtDateTime(r.created_at)}</td>
        <td><b>${r.title}</b>${r.part ? ` (${r.part})` : ''}<div class="small muted">${skillTitle(r.skills[0])} · ${r.mode}</div></td>
        <td><code class="small">${r.input ? String(r.input).slice(0, 40) : '–'}</code></td>
        <td><span class=${`tag ${r.correct ? 'ok' : 'bad'}`}>${r.status}</span>${r.error_category ? html` <span class="tag">${errTitle(r.error_category)}</span>` : ''}${r.admin_note ? html` <span class="tag warn">!</span>` : ''}</td>
        <td class="small">${r.hints ? `${r.hints} H.` : ''}${r.solution_shown ? ' Lösung' : ''}</td><td class="small">${r.source}</td></tr>`)}</tbody></table>`}</section>`;
}

function AttemptDetail({ id }) {
  const { data: d, reload } = useApi(`/api/admin/attempt/${id}`);
  const [cat, setCat] = useState('');
  const [note, setNote] = useState('');
  if (!d) return html`<${Loading} />`;
  const a = d.attempt;
  const override = async (correct) => {
    await api(`/api/admin/attempt/${id}/override`, { method: 'POST', body: { correct, error_category: cat || a.error_category, note } });
    toast('Gespeichert', 'ok'); reload();
  };
  return html`<button class="btn small ghost" onClick=${() => history.back()}>← zurück</button>
    <h1>Versuch vom ${fmtDateTime(a.created_at)}</h1>
    <div class="grid g2">
      <section class="card"><h3>${STUDENT}s Antwort</h3>
        <p><span class=${`tag ${a.correct ? 'ok' : 'bad'}`}>${a.status}</span> Teil ${a.part || '–'} · Modus ${a.mode} · Quelle ${a.source} · ${a.hints} Hinweise${a.solution_shown ? ' · Lösung angezeigt' : ''} · ${a.duration_s ? `${Math.round(a.duration_s / 60 * 10) / 10} min` : ''}</p>
        <p>Eingabe: <code>${a.input ?? '–'}</code></p>
        ${a.feedback && html`<div class="hintbox">${a.feedback}</div>`}
        ${a.admin_note && html`<div class="feedback fast">${a.admin_note}</div>`}
        ${d.review && html`<h3>Foto-Korrektur</h3><${Thumbs} ids=${d.review.photo_ids} />
          <details open><summary>Transkription</summary><${Md} src=${d.review.result.transcription || ''} /></details>
          ${(d.review.result.parts || []).map((p) => html`<div class="small"><b>${p.label || '–'}:</b> ${p.correct ? '✅' : '❌'} Score ${p.score} · Endresultat <code>${p.final_answer || '–'}</code> ${p.first_error_line ? `· erster Fehler Zeile ${p.first_error_line}` : ''}<div class="muted">${p.feedback}</div></div>`)}
          <p class="small"><b>Zusammenfassung:</b> ${d.review.result.summary}</p>`}
        <h3>Bewertung korrigieren</h3>
        <div class="row gap wrap"><select style="max-width:260px" value=${cat} onChange=${(e) => setCat(e.target.value)}><option value="">Fehlertyp…</option>${Object.entries(CUR.error_categories).map(([k, v]) => html`<option value=${k}>${v}</option>`)}</select>
          <input type="text" style="max-width:260px" placeholder="Notiz" value=${note} onInput=${(e) => setNote(e.target.value)} /></div>
        <div class="row gap" style="margin-top:.5rem"><button class="btn ok" onClick=${() => override(true)}>Als richtig werten</button><button class="btn" onClick=${() => override(false)}>Als falsch werten</button></div>
        ${d.chats.length ? html`<h3>Tutor-Gespräche zu dieser Aufgabe</h3><ul class="list small">${d.chats.map((c) => html`<li><a href=${`#/chats/${c.id}`}>${c.title}</a> · ${fmtDateTime(c.updated_at)}</li>`)}</ul>` : ''}
      </section>
      <section class="card"><h3>Aufgabe</h3>${d.exercise ? html`<${ExerciseReveal} ex=${d.exercise} highlight=${a.part} />` : '–'}</section>
    </div>`;
}

// ───────────── catalogue / exercise view ─────────────
function Catalogue({ q }) {
  const [term, setTerm] = useState(q.q || '');
  const [chapter, setChapter] = useState('');
  const { data } = useApi(`/api/admin/exercises?q=${encodeURIComponent(term)}${chapter ? `&chapter=${chapter}` : ''}`, [term, chapter]);
  return html`<h1>Aufgaben (${data ? data.total : '…'})</h1>
    <div class="row gap wrap" style="margin-bottom:.6rem"><input type="text" style="max-width:320px" placeholder="Suchen…" value=${term} onInput=${(e) => setTerm(e.target.value)} />
      <select style="max-width:260px" value=${chapter} onChange=${(e) => setChapter(e.target.value)}><option value="">Alle Kapitel</option>${CUR.chapters.map((c) => html`<option value=${c.id}>${c.title}</option>`)}</select></div>
    <section class="card table-wrap">${!data ? html`<${Loading} />` : html`<table class="t"><thead><tr><th>Aufgabe</th><th>Quelle</th><th>Thema</th><th></th><th>${STUDENT}</th></tr></thead><tbody>
      ${data.items.map((e) => html`<tr class="clickable" onClick=${() => go(`/aufgaben/${encodeURIComponent(e.id)}`)}><td><b>${e.title}</b><div class="small muted">${e.id}</div></td>
        <td class="small">${e.source.doc} ${e.source.ref || ''}</td><td class="small">${skillTitle(e.skills[0])}</td>
        <td class="small">${e.calculator === 'mit' ? '🧮' : '✍️'} ${'★'.repeat(e.difficulty || 1)}${e.note ? html` <span class="tag warn" title=${e.note}>korr.</span>` : ''}</td>
        <td><span class=${`tag ${e.status === 'geloest' ? 'ok' : e.status === 'offen' ? 'bad' : ''}`}>${e.status}</span></td></tr>`)}</tbody></table>`}</section>
    ${data && html`<section class="card"><h2>Generatoren (${data.generators.length})</h2><p class="small muted">Erzeugen unbegrenzt neue Varianten, Lösungen von SymPy berechnet.</p>
      <ul class="list small">${data.generators.map((g) => html`<li>${g.title} <span class="muted">· ${g.skills.map(skillTitle).join(', ')}</span></li>`)}</ul></section>`}`;
}
function ExerciseView({ id }) {
  const { data } = useApi(`/api/exercise/${encodeURIComponent(id)}?reveal=true`);
  if (!data) return html`<${Loading} />`;
  return html`<button class="btn small ghost" onClick=${() => history.back()}>← zurück</button><section class="card"><h2>${data.title}</h2><${ExerciseReveal} ex=${data} />
    <h3>${STUDENT}s Versuche</h3>${data.attempts.length ? html`<ul class="list small">${data.attempts.map((a) => html`<li>${fmtDateTime(a.created_at)} · ${a.part || ''} <code>${a.input ?? '–'}</code> <span class=${`tag ${a.correct ? 'ok' : 'bad'}`}>${a.status}</span></li>`)}</ul>` : html`<p class="muted small">Keine (Versuche des Coaches werden nicht gezählt).</p>`}</section>`;
}

// ───────────── assignments ─────────────
function Assignments() {
  const { data, reload } = useApi('/api/admin/assignments');
  const [f, setF] = useState({ title: '', description: '', skill: '', target: 10, due: '' });
  const save = async () => {
    if (!f.title) return toast('Titel fehlt', 'bad');
    await api('/api/admin/assignments', { method: 'POST', body: { title: f.title, description: f.description, skills: f.skill ? [f.skill] : [], exercise_ids: [], target: +f.target, due_at: f.due ? new Date(f.due + 'T23:59').getTime() / 1000 : null } });
    setF({ title: '', description: '', skill: '', target: 10, due: '' }); reload();
  };
  const archive = async (a) => { await api('/api/admin/assignments', { method: 'POST', body: { id: a.id, archived: 1 } }); reload(); };
  return html`<h1>Aufträge an ${STUDENT}</h1>
    <section class="card"><h2>Neuer Auftrag</h2><div class="grid g2">
      <label class="field">Titel<input type="text" value=${f.title} onInput=${(e) => setF({ ...f, title: e.target.value })} placeholder="z.B. Kettenregel festigen" /></label>
      <label class="field">Thema<select value=${f.skill} onChange=${(e) => setF({ ...f, skill: e.target.value })}><option value="">–</option>${CUR.chapters.map((c) => html`<optgroup label=${c.title}>${c.skills.map((s) => html`<option value=${s.id}>${s.title}</option>`)}</optgroup>`)}</select></label>
      <label class="field">Anzahl richtige Teilaufgaben<input type="number" value=${f.target} onInput=${(e) => setF({ ...f, target: e.target.value })} /></label>
      <label class="field">Bis<input type="date" value=${f.due} onInput=${(e) => setF({ ...f, due: e.target.value })} /></label></div>
      <label class="field">Nachricht an ${STUDENT}<textarea rows="2" value=${f.description} onInput=${(e) => setF({ ...f, description: e.target.value })}></textarea></label>
      <button class="btn primary" onClick=${save}>Auftrag erteilen</button></section>
    <section class="card"><h2>Aktiv</h2>${data && data.length ? html`<ul class="list">${data.map((a) => html`<li class="row between gap"><span><b>${a.title}</b> ${a.skills.map((s) => html`<span class="tag">${skillTitle(s)}</span>`)}<br/>
      <span class="small muted">${a.done}/${a.target || '–'} · bis ${a.due_at ? fmtDate(a.due_at) : 'offen'}</span><${Bar} value=${a.target ? a.done / a.target : 0} /></span><button class="btn small" onClick=${() => archive(a)}>Archivieren</button></li>`)}</ul>` : html`<p class="muted">Keine.</p>`}</section>`;
}

// ───────────── chats ─────────────
function Chats() {
  const { data } = useApi('/api/admin/chats');
  return html`<h1>${STUDENT}s Tutor-Gespräche</h1><section class="card">${data ? html`<ul class="list">${data.map((c) => html`<li class="row between clickable" onClick=${() => go(`/chats/${c.id}`)}>
    <span>${c.kind === 'review' ? '📷 ' : '💬 '}<b>${c.title}</b><br/><span class="small muted">${c.n} Nachrichten${c.exercise_id ? ` · ${c.exercise_id}` : ''}</span></span><span class="small muted">${fmtDateTime(c.updated_at)}</span></li>`)}</ul>` : html`<${Loading} />`}</section>`;
}
function ChatView({ id }) {
  const { data } = useApi(`/api/chats/${id}`);
  if (!data) return html`<${Loading} />`;
  return html`<button class="btn small ghost" onClick=${() => history.back()}>← zurück</button><h1>${data.chat.title}</h1><section class="card">
    ${data.messages.map((m) => html`<div class=${`msg ${m.role}`}>${m.attachments && m.attachments.length && m.role === 'user' ? html`<${Thumbs} ids=${m.attachments} />` : ''}
      ${m.role === 'assistant' ? html`<${Md} src=${m.content} />` : html`<div class="bubble">${m.meta && m.meta.mode ? html`<span class="tag">${m.meta.mode}</span>` : ''}<${MathText} src=${userText(m.content)} /></div>`}
      <span class="small muted">${fmtDateTime(m.created_at)}</span></div>`)}</section>`;
}
function Coach({ chatId }) {
  const { data } = useApi('/api/admin/coach_chats');
  useEffect(() => () => sessionStorage.removeItem('coach-prefill'), []);
  const [k, setK] = useState(0);
  return html`<div class="row between wrap gap"><h1>Coach-Assistent</h1><select style="max-width:280px" value=${chatId || ''} onChange=${(e) => go(e.target.value ? `/coach/${e.target.value}` : '/coach')}>
    <option value="">+ Neues Gespräch</option>${(data || []).map((c) => html`<option value=${c.id}>${c.title}</option>`)}</select></div>
    <p class="small muted">Der Assistent kennt ${STUDENT}s kompletten Lernstand (beim ersten Satz eines Gesprächs mitgeschickt). Frag z.B. «Wie erkläre ich ihm die Kettenregel?» oder «Stell mir 5 Aufgaben zu seinen Fehlern zusammen».</p>
    <section class="card" style="padding:.6rem"><${Chat} key=${(chatId || 'n') + k} chatId=${chatId} adminKind=${true} modes=${false} prefill=${chatId ? '' : (sessionStorage.getItem('coach-prefill') || '')} /></section>`;
}


// ───────────── error reports ─────────────
function Reports() {
  const { data, reload } = useApi('/api/admin/reports');
  const [filter, setFilter] = useState('offen');
  if (!data) return html`<${Loading} />`;
  const upd = async (r, body) => { await api(`/api/admin/reports/${r.id}`, { method: 'POST', body }); reload(); };
  const items = data.items.filter((r) => filter === 'alle' || r.status === filter);
  return html`<h1>Fehlermeldungen ${data.open ? html`<span class="tag bad">${data.open} offen</span>` : ''}</h1>
    <p class="muted small">Meldungen von ${STUDENT} (und dir) zu Aufgaben, Lösungen und Formelkarten. «Aus dem Training nehmen» versteckt die Aufgabe (bzw. den ganzen Generator) beim Üben und in der Revanche, bis du sie wieder freigibst.</p>
    <div class="chips">${[['offen', 'Offen'], ['erledigt', 'Erledigt'], ['abgelehnt', 'Abgelehnt'], ['alle', 'Alle']].map(([k, l]) => html`<button class=${`chip ${filter === k ? 'on' : ''}`} onClick=${() => setFilter(k)}>${l}</button>`)}</div>
    ${items.length ? items.map((r) => html`<section class="card">
      <div class="row between wrap gap"><div><b>${r.title}</b>${r.part ? ` (${r.part})` : ''} <span class="tag ${r.status === 'offen' ? 'bad' : r.status === 'erledigt' ? 'ok' : ''}">${r.status}</span>
        ${r.disabled ? html` <span class="tag warn">aus dem Training genommen</span>` : ''}
        <div class="small muted">${fmtDateTime(r.created_at)} · ${r.user} · ${r.exercise_id}${r.context.source ? ` · ${r.context.source.doc} ${r.context.source.ref || ''}` : ''}</div></div>
        ${!r.exercise_id.startsWith('card:') ? html`<a class="btn small" href=${`#/aufgaben/${encodeURIComponent(r.exercise_id)}`}>Aufgabe mit Lösung ansehen</a>` : ''}</div>
      <p><b>${r.kind_title}</b>${r.comment ? html`: «${r.comment}»` : ''}</p>
      ${r.context.input ? html`<div class="small">Eingabe: <code>${r.context.input}</code> · erwartet: <code>${r.context.expected}</code>
        ${r.context.checker ? html` · Prüfer las <code>${r.context.checker.parsed || '–'}</code> → <span class=${`tag ${r.context.checker.ok ? 'ok' : 'bad'}`}>${r.context.checker.status}</span>` : ''}</div>` : ''}
      ${r.context.attempts && r.context.attempts.length ? html`<details><summary class="small">Letzte Versuche</summary><ul class="list small">${r.context.attempts.map((a) => html`<li>${fmtDateTime(a.created_at)} · ${a.part || '–'} · <code>${a.input ?? '–'}</code> · ${a.status}</li>`)}</ul></details>` : ''}
      <label class="field">Notiz<input type="text" value=${r.admin_note || ''} onChange=${(e) => upd(r, { admin_note: e.target.value })} placeholder="z.B. Lösung korrigiert in Version …" /></label>
      <div class="row gap wrap">
        ${r.status === 'offen' ? html`<button class="btn small ok" onClick=${() => upd(r, { status: 'erledigt' })}>Erledigt</button><button class="btn small" onClick=${() => upd(r, { status: 'abgelehnt' })}>Kein Fehler</button>`
          : html`<button class="btn small" onClick=${() => upd(r, { status: 'offen' })}>Wieder öffnen</button>`}
        ${!r.exercise_id.startsWith('card:') ? html`<button class="btn small" onClick=${() => upd(r, { disable: !r.disabled })}>${r.disabled ? 'Wieder ins Training aufnehmen' : (r.generated ? 'Generator aus dem Training nehmen' : 'Aus dem Training nehmen')}</button>` : ''}
        <a class="btn small ghost" href=${`#/coach`} onClick=${() => sessionStorage.setItem('coach-prefill', `${STUDENT} meldet einen Fehler in Aufgabe ${r.exercise_id}${r.part ? ' (' + r.part + ')' : ''}: ${r.kind_title}${r.comment ? ' – «' + r.comment + '»' : ''}${r.context.input ? `. Eingabe: ${r.context.input}, erwartet: ${r.context.expected}` : ''}. Prüfe bitte mit deinen Tools, ob die Aufgabe/Lösung korrekt ist.`)}>🤖 Vom Assistenten prüfen lassen</a>
      </div></section>`) : html`<div class="empty card">Keine Meldungen.</div>`}`;
}


// ───────────── feedback & errors ─────────────
function devReport(f) {
  const c = f.context || {};
  const lines = [
    `## Feedback #${f.id} – ${f.kind_title} (${f.status})`,
    `- Von: ${f.user}, ${new Date(f.created_at * 1000).toLocaleString('de-CH')}`,
    `- Seite: ${c.page ? c.page.url : '–'}${c.page && c.page.exercise ? ` · Aufgabe ${c.page.exercise}` : ''}${c.page && c.page.heading ? ` · «${c.page.heading}»` : ''}`,
    `- App-Version: ${c.version || (c.server && c.server.version) || '–'}`,
    `- Gerät: ${c.client ? `${c.client.viewport}, dpr ${c.client.dpr}, ${c.client.touch ? 'touch' : 'mouse'}, ${c.client.dark ? 'dark' : 'light'}, ${c.client.ua}` : '–'}`,
    '', '### Beschreibung', f.text || '(kein Text)', '',
    `### Screenshots`, ...(f.photo_ids || []).map((p) => `- ${location.origin}/api/photo/${p}`),
    '', '### Verlauf (Seiten)', ...((c.routes || []).map((r) => `- ${r.t} ${r.hash}`)),
    '', '### JavaScript-Fehler', ...((c.js_errors || []).length ? c.js_errors.map((e) => `- ${e.t} ${e.msg} ${e.src || ''}\n${e.stack ? '```\n' + e.stack + '\n```' : ''}`) : ['- keine']),
    '', '### Fehlgeschlagene Anfragen', ...((c.failed_requests || []).length ? c.failed_requests.map((r) => `- ${r.t} ${r.method || 'GET'} ${r.path} → ${r.status} ${r.msg || ''}`) : ['- keine']),
    '', '### Serverfehler (letzte Stunde)', ...(((c.server || {}).recent_server_errors || []).length ? c.server.recent_server_errors.map((e) => `- #${e.id} ${e.method} ${e.path}: ${e.error}`) : ['- keine']),
  ];
  return lines.join('\n');
}

function FeedbackPage() {
  const { data, reload } = useApi('/api/admin/feedback');
  const [filter, setFilter] = useState('offen');
  const [big, setBig] = useState(null);
  if (!data) return html`<${Loading} />`;
  const upd = async (f, body) => { await api(`/api/admin/feedback/${f.id}`, { method: 'POST', body }); reload(); };
  const copy = async (f) => { try { await navigator.clipboard.writeText(devReport(f)); toast('Kopiert – füge es im Chat mit dem Entwickler ein.', 'ok'); } catch (e) { toast('Kopieren nicht möglich', 'bad'); } };
  const items = data.items.filter((f) => filter === 'alle' || (filter === 'offen' ? f.status !== 'erledigt' : f.status === filter));
  return html`<div class="row between wrap gap"><h1>Feedback & Fehler ${data.open ? html`<span class="tag bad">${data.open} offen</span>` : ''}</h1><span class="small muted">App-Version ${data.version}</span></div>
    <div class="chips">${[['offen', 'Offen'], ['erledigt', 'Erledigt'], ['alle', 'Alle']].map(([k, l]) => html`<button class=${`chip ${filter === k ? 'on' : ''}`} onClick=${() => setFilter(k)}>${l}</button>`)}</div>
    ${items.length ? items.map((f) => { const c = f.context || {}; return html`<section class="card">
      <div class="row between wrap gap"><div><b>${f.kind_title}</b> <span class=${`tag ${f.status === 'erledigt' ? 'ok' : f.status === 'in_arbeit' ? 'warn' : 'bad'}`}>${f.status.replace('_', ' ')}</span>
        <div class="small muted">#${f.id} · ${fmtDateTime(f.created_at)} · ${f.user} · ${c.page ? c.page.area : ''} <code>${c.page ? c.page.hash : ''}</code>${c.page && c.page.exercise ? html` · <a href=${`#/aufgaben/${encodeURIComponent(c.page.exercise)}`}>${c.page.exercise}</a>` : ''}</div></div>
        <span class="row gap">${(c.js_errors || []).length ? html`<span class="tag bad">${c.js_errors.length} JS-Fehler</span>` : ''}${(c.failed_requests || []).length ? html`<span class="tag warn">${c.failed_requests.length} Anfragen fehlgeschlagen</span>` : ''}</span></div>
      <p style="white-space:pre-wrap">${f.text || html`<span class="muted">(kein Text)</span>`}</p>
      ${f.photo_ids.length ? html`<div class="thumbs">${f.photo_ids.map((p) => html`<span class="thumb clickable" onClick=${() => setBig(p)}><img src=${`/api/photo/${p}`} style="height:110px" /></span>`)}</div>` : ''}
      <details class="small"><summary>Technische Details</summary>
        <p>Gerät: ${c.client ? `${c.client.viewport} · ${c.client.touch ? 'Touch' : 'Maus'} · ${c.client.dark ? 'dunkel' : 'hell'} · ${c.client.ua}` : '–'} · Version ${c.version || '–'}</p>
        <p><b>Verlauf:</b> ${(c.routes || []).map((r) => html`<code style="margin-right:.3rem">${r.hash}</code>`)}</p>
        ${(c.js_errors || []).map((e) => html`<div class="feedback falsch small"><b>${e.msg}</b> ${e.src || ''}${e.stack ? html`<pre>${e.stack}</pre>` : ''}</div>`)}
        ${(c.failed_requests || []).map((r) => html`<div class="feedback fast small">${r.method || 'GET'} ${r.path} → ${r.status} ${r.msg || ''}</div>`)}
        ${((c.server || {}).recent_server_errors || []).map((e) => html`<div class="feedback falsch small">Server #${e.id}: ${e.method} ${e.path} – ${e.error}</div>`)}
      </details>
      <label class="field">Notiz<input type="text" value=${f.admin_note || ''} onChange=${(e) => upd(f, { admin_note: e.target.value })} placeholder="Was wurde gemacht?" /></label>
      <div class="row gap wrap">
        ${f.status !== 'in_arbeit' && f.status !== 'erledigt' ? html`<button class="btn small" onClick=${() => upd(f, { status: 'in_arbeit' })}>In Arbeit</button>` : ''}
        ${f.status !== 'erledigt' ? html`<button class="btn small ok" onClick=${() => upd(f, { status: 'erledigt' })}>Erledigt</button>` : html`<button class="btn small" onClick=${() => upd(f, { status: 'neu' })}>Wieder öffnen</button>`}
        <button class="btn small" onClick=${() => copy(f)}>📋 Für Entwickler kopieren</button></div>
    </section>`; }) : html`<div class="empty card">Kein Feedback.</div>`}
    <section class="card"><div class="row between"><h2 style="margin:0">Serverfehler (${data.server_errors.length})</h2>
      ${data.server_errors.length ? html`<button class="btn small" onClick=${async () => { await api('/api/admin/server_errors/clear', { method: 'POST' }); reload(); }}>Liste leeren</button>` : ''}</div>
      ${data.server_errors.length ? html`<ul class="list small">${data.server_errors.map((e) => html`<li><b>${e.method} ${e.path}</b> · ${e.user || '–'} · ${fmtDateTime(e.created_at)}<div>${e.error}</div>
        <details><summary>Traceback</summary><pre>${e.traceback}</pre></details></li>`)}</ul>` : html`<p class="muted small">Keine – alles läuft.</p>`}</section>
    ${big && html`<div class="modal-bg" onClick=${() => setBig(null)}><img src=${`/api/photo/${big}`} style="max-width:96vw;max-height:92vh;border-radius:8px" /></div>`}`;
}

// ───────────── settings ─────────────

function Settings() {
  const { data, reload } = useApi('/api/admin/settings');
  const [s, setS] = useState(null);
  useEffect(() => { if (data) setS({ sessions: data.dates.sessions.join('\n'), exam: data.dates.exam, notify: data.notify_enabled, goal: data.daily_goal, weights: data.chapter_weights }); }, [data]);
  if (!s) return html`<${Loading} />`;
  const save = async (extra = {}) => {
    await api('/api/admin/settings', { method: 'POST', body: { session_dates: s.sessions.split(/\s+/).filter(Boolean), exam_date: s.exam, notify_enabled: s.notify, chapter_weights: s.weights, daily_goal: +s.goal, ...extra } });
    toast('Gespeichert', 'ok'); reload();
  };
  return html`<h1>Einstellungen</h1>
    <section class="card"><h2>Termine</h2><div class="grid g2">
      <label class="field">Lernsessions (ein Datum pro Zeile, JJJJ-MM-TT)<textarea rows="5" value=${s.sessions} onInput=${(e) => setS({ ...s, sessions: e.target.value })}></textarea></label>
      <label class="field">Prüfung (voraussichtlich)<input type="date" value=${s.exam} onInput=${(e) => setS({ ...s, exam: e.target.value })} /></label></div></section>
    <section class="card"><h2>Motivation</h2><label class="field">Tagesziel (richtige Teilaufgaben)<input type="number" value=${s.goal} onInput=${(e) => setS({ ...s, goal: e.target.value })} /></label></section>
    <section class="card"><h2>Gewichtung für «Prüfungsfit»</h2><p class="small muted">Punkte pro Kapitel in den Probeprüfungen (2024/2025: K1 5/0, K2 20/13, K3 13/21, K4 29/30, K5 21/18, K6 16/18).</p>
      <div class="grid g3">${CUR.chapters.filter((c) => !c.optional).map((c) => html`<label class="field">${c.title}<input type="number" value=${s.weights[c.id] ?? 1} onInput=${(e) => setS({ ...s, weights: { ...s.weights, [c.id]: +e.target.value } })} /></label>`)}</div></section>
    <section class="card"><h2>Telegram</h2>${data.telegram ? html`<label class="row gap"><input type="checkbox" checked=${s.notify} onChange=${(e) => setS({ ...s, notify: e.target.checked })} /> Benachrichtigungen an mich (Tageszusammenfassung 20 Uhr, Kampf-Alarm, Session-Erinnerung, Beförderungen)</label>
      <button class="btn small" style="margin-top:.5rem" onClick=${() => save({ test_telegram: true })}>Testnachricht senden</button>` : html`<p class="muted">Kein Telegram-Bot konfiguriert (Neo-Einstellung des Dienstes).</p>`}</section>
    <button class="btn primary" onClick=${() => save()}>Speichern</button>`;
}

api('/api/me').then((m) => { STUDENT = m.student || 'Student'; window.__appVersion = m.version; })
  .catch(() => {}).finally(() => render(html`<${App} />`, document.getElementById('app')));
