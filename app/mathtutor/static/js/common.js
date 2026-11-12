// Shared UI: API, Markdown+KaTeX, interactive plots, math input, camera, voice, chat.
import { html, render, useState, useEffect, useRef, useCallback, useMemo } from '../vendor/preact-htm.js';
import { marked } from '../vendor/marked.js';
import DOMPurify from '../vendor/purify.js';

export { html, render, useState, useEffect, useRef, useCallback, useMemo };

// ───────────── API ─────────────
export async function api(path, opts = {}) {
  const o = { headers: {}, ...opts };
  if (o.body && !(o.body instanceof FormData) && typeof o.body !== 'string') {
    o.body = JSON.stringify(o.body);
    o.headers['Content-Type'] = 'application/json';
  }
  let r;
  try { r = await fetch(path, o); } catch (e) {
    logRequest({ method: o.method || 'GET', path, status: 0, ok: false, msg: 'Netzwerkfehler: ' + e.message });
    throw new Error('Keine Verbindung zum Server.');
  }
  if (r.status === 401 || r.status === 302) { location.reload(); throw new Error('Nicht angemeldet'); }
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (!path.startsWith('/api/photo')) logRequest({ method: o.method || 'GET', path, status: r.status, ok: r.ok, msg: r.ok ? '' : String((data && data.error) || '').slice(0, 200) });
  if (!r.ok) throw new Error((data && data.error) || `Fehler ${r.status}`);
  return data;
}

// POST + Server-Sent Events: calls onEvent for every parsed event.
export async function stream(path, body, onEvent, signal) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  if (!r.ok) { onEvent({ t: 'error', message: `Fehler ${r.status}` }); return; }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) { try { onEvent(JSON.parse(line.slice(6))); } catch (e) { /* ignore */ } }
      }
    }
  }
}

export async function uploadPhoto(file, exerciseId) {
  const fd = new FormData();
  fd.append('file', file);
  return api('/api/photo' + (exerciseId ? `?exercise_id=${encodeURIComponent(exerciseId)}` : ''), { method: 'POST', body: fd });
}

// ───────────── router ─────────────
export function useRoute() {
  const [r, setR] = useState(parseHash());
  useEffect(() => {
    const f = () => { setR(parseHash()); window.scrollTo(0, 0); };
    addEventListener('hashchange', f);
    return () => removeEventListener('hashchange', f);
  }, []);
  return r;
}
function parseHash() {
  const h = location.hash.replace(/^#/, '') || '/';
  const [path, qs] = h.split('?');
  return { path, parts: path.split('/').filter(Boolean), q: Object.fromEntries(new URLSearchParams(qs || '')) };
}
export const go = (h) => { location.hash = h; };

// ───────────── formatting ─────────────
export const pct = (v) => (v == null ? '–' : `${Math.round(v * 100)} %`);
export const fmtDate = (ts) => (ts ? new Date(ts * 1000).toLocaleDateString('de-CH', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '–');
export const fmtDateTime = (ts) => (ts ? new Date(ts * 1000).toLocaleString('de-CH', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '–');
export const fmtIso = (d) => (d ? new Date(d + 'T12:00:00').toLocaleDateString('de-CH', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' }) : '–');
export function ago(ts) {
  if (!ts) return 'nie';
  const s = Date.now() / 1000 - ts;
  if (s < 90) return 'gerade eben';
  if (s < 3600) return `vor ${Math.round(s / 60)} min`;
  if (s < 86400) return `vor ${Math.round(s / 3600)} h`;
  return `vor ${Math.round(s / 86400)} Tagen`;
}
export const levelColor = (m, n) => (n === 0 ? 'var(--muted-bg)' : m >= 0.8 ? 'var(--ok)' : m >= 0.5 ? 'var(--warn)' : 'var(--bad)');
export const levelText = (m, n) => (n === 0 ? 'neu' : m >= 0.8 ? 'sicher' : m >= 0.5 ? 'im Aufbau' : 'unsicher');

// ───────────── Markdown + KaTeX ─────────────
marked.setOptions({ gfm: true, breaks: false });

// KaTeX cannot attach ^ to a spacing command ("20\\,^\\circ"): give it an empty base.
export const fixTex = (t) => String(t).replace(/\\([,;:! ])\^/g, '\\$1{}^');

export function mdToHtml(src) {
  if (!src) return '';
  const store = [];
  const keep = (s) => { store.push(s); return `@@M${store.length - 1}@@`; };
  let t = String(src);
  // fenced plot blocks
  t = t.replace(/```plot\s*\n([\s\S]*?)```/g, (_, spec) => keep({ plot: spec.trim() }));
  // protect code
  t = t.replace(/```[\s\S]*?```/g, (m) => keep({ raw: m }));
  // math
  t = t.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => keep({ tex: m, display: true }));
  t = t.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => keep({ tex: m, display: true }));
  t = t.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => keep({ tex: m, display: false }));
  t = t.replace(/(^|[^\\$])\$(?!\s)((?:\\\$|[^$\n])+?)\$/g, (_, pre, m) => pre + keep({ tex: m, display: false }));
  // put raw code back before markdown
  t = t.replace(/@@M(\d+)@@/g, (m, i) => (store[i].raw ? store[i].raw : m));
  let out = marked.parse(t);
  out = DOMPurify.sanitize(out, { ADD_ATTR: ['target'] });
  out = out.replace(/@@M(\d+)@@/g, (_, i) => {
    const s = store[i];
    if (s.plot) return `<div class="plot-slot" data-spec="${encodeURIComponent(s.plot)}"></div>`;
    try {
      return window.katex.renderToString(fixTex(s.tex), { displayMode: s.display, throwOnError: false, strict: false, trust: false });
    } catch (e) { return `<code>${s.tex.replace(/</g, '&lt;')}</code>`; }
  });
  return out;
}

export function Md({ src, class: cls = '' }) {
  const ref = useRef();
  const h = useMemo(() => mdToHtml(src), [src]);
  useEffect(() => {
    if (!ref.current) return;
    ref.current.querySelectorAll('.plot-slot').forEach((el) => {
      if (el.dataset.mounted) return;
      el.dataset.mounted = '1';
      try { mountPlot(el, JSON.parse(decodeURIComponent(el.dataset.spec))); } catch (e) { el.textContent = 'Diagramm fehlerhaft: ' + e.message; }
    });
  }, [h]);
  return html`<div class="md ${cls}" ref=${ref} dangerouslySetInnerHTML=${{ __html: h }}></div>`;
}

// ───────────── interactive plots (JSXGraph + math.js) ─────────────
let plotId = 0;
function compileExpr(expr) {
  const e = String(expr).replace(/\bln\(/g, 'log(').replace(/\*\*/g, '^').replace(/π/g, 'pi');
  return window.math.compile(e);
}
const COLORS = ['#2563eb', '#e8710a', '#16a34a', '#9333ea', '#dc2626', '#0891b2'];

export function mountPlot(el, spec) {
  const id = `plot${++plotId}`;
  el.innerHTML = `${spec.title ? `<div class="plot-title">${DOMPurify.sanitize(spec.title)}</div>` : ''}<div id="${id}" class="jxgbox plot-box"></div><div class="plot-sliders"></div>`;
  const vals = {};
  const sliderBox = el.querySelector('.plot-sliders');
  (spec.sliders || []).forEach((s) => {
    vals[s.name] = s.value ?? s.min ?? 0;
    const row = document.createElement('label');
    row.className = 'slider-row';
    row.innerHTML = `<span class="sl-name">${DOMPurify.sanitize(s.label || s.name)}</span><input type="range" min="${s.min}" max="${s.max}" step="${s.step || (s.max - s.min) / 100}" value="${vals[s.name]}"><output>${vals[s.name]}</output>`;
    const inp = row.querySelector('input');
    const outp = row.querySelector('output');
    inp.addEventListener('input', () => { vals[s.name] = parseFloat(inp.value); outp.textContent = inp.value; board.update(); });
    sliderBox.appendChild(row);
  });
  const xr = spec.x || [-5, 5];
  const yr = spec.y || [-5, 5];
  const board = window.JXG.JSXGraph.initBoard(id, {
    boundingbox: [xr[0], yr[1], xr[1], yr[0]], axis: true, showCopyright: false, showNavigation: true,
    pan: { enabled: true, needTwoFingers: true }, zoom: { wheel: false, pinch: true }, keepAspectRatio: !!spec.equalAxes,
  });
  const ev = (c, x) => { try { const v = c.evaluate({ ...vals, x }); return typeof v === 'number' ? v : NaN; } catch (e) { return NaN; } };
  const num = (v) => { if (typeof v === 'number') return () => v; const c = compileExpr(v); return () => ev(c, 0); };
  (spec.functions || []).forEach((f, i) => {
    const c = compileExpr(f.expr);
    board.create('functiongraph', [(x) => ev(c, x)], { strokeColor: f.color || COLORS[i % COLORS.length], strokeWidth: 2.5, name: f.label || '', withLabel: !!f.label });
  });
  (spec.areas || []).forEach((a, i) => {
    const c1 = compileExpr(a.expr); const c2 = compileExpr(a.expr2 ?? '0');
    const from = num(a.from ?? xr[0]); const to = num(a.to ?? xr[1]);
    const curve = board.create('curve', [[], []], { fillColor: a.color || COLORS[(i + 1) % COLORS.length], fillOpacity: 0.25, strokeWidth: 0, highlight: false });
    curve.updateDataArray = function () {
      const A = from(); const B = to(); const n = 120; const xs = []; const ys = [];
      for (let k = 0; k <= n; k++) { const x = A + (B - A) * k / n; xs.push(x); ys.push(ev(c1, x)); }
      for (let k = n; k >= 0; k--) { const x = A + (B - A) * k / n; xs.push(x); ys.push(ev(c2, x)); }
      this.dataX = xs; this.dataY = ys;
    };
  });
  (spec.points || []).forEach((p) => {
    board.create('point', [num(p.x), num(p.y)], { name: p.label || '', fixed: true, size: 3, color: p.color || '#111' });
  });
  (spec.vectors || []).forEach((v, i) => {
    const f = (v.from || [0, 0]).map(num); const t = (v.to || [1, 1]).map(num);
    board.create('arrow', [[f[0], f[1]], [t[0], t[1]]], { strokeColor: v.color || COLORS[i % COLORS.length], strokeWidth: 2.5, name: v.label || '', withLabel: !!v.label, lastArrow: { type: 2, size: 6 } });
  });
  if (spec.tangent) {
    const c = compileExpr(spec.tangent.expr); const at = num(spec.tangent.at);
    const p0 = () => at(); const y0 = () => ev(c, p0()); const m = () => (ev(c, p0() + 1e-5) - ev(c, p0() - 1e-5)) / 2e-5;
    board.create('functiongraph', [(x) => y0() + m() * (x - p0())], { strokeColor: '#dc2626', dash: 2, strokeWidth: 2 });
    board.create('point', [p0, y0], { name: '', fixed: true, size: 3, color: '#dc2626' });
  }
  board.update();
}

export function Plot({ spec }) {
  const ref = useRef();
  useEffect(() => { if (ref.current) { ref.current.innerHTML = ''; mountPlot(ref.current, spec); } }, [JSON.stringify(spec)]);
  return html`<div class="plot" ref=${ref}></div>`;
}

// ───────────── math input (MathLive) ─────────────
export function MathInput({ value, onInput, placeholder, onEnter, autofocus }) {
  const ref = useRef();
  useEffect(() => {
    const mf = ref.current;
    if (!mf) return;
    mf.smartFence = true;
    mf.mathVirtualKeyboardPolicy = 'auto';
    mf.setAttribute('math-virtual-keyboard-policy', 'auto');
    const f = () => onInput(mf.value);
    const k = (e) => { if (e.key === 'Enter' && onEnter) { e.preventDefault(); onEnter(); } };
    mf.addEventListener('input', f);
    mf.addEventListener('keydown', k);
    if (autofocus) setTimeout(() => mf.focus(), 50);
    return () => { mf.removeEventListener('input', f); mf.removeEventListener('keydown', k); };
  }, [onInput, onEnter]);
  useEffect(() => { if (ref.current && ref.current.value !== value) ref.current.value = value || ''; }, [value]);
  return html`<math-field ref=${ref} class="mathfield" placeholder=${placeholder || ''}></math-field>`;
}

// ───────────── camera / photos ─────────────
export function PhotoPicker({ onPhoto, exerciseId, label = 'Foto' }) {
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState(false);
  const fileRef = useRef();
  const handle = async (file) => {
    if (!file) return;
    setBusy(true);
    try { onPhoto(await uploadPhoto(file, exerciseId)); } catch (e) { alertBox(e.message); }
    setBusy(false);
  };
  const isTouch = matchMedia('(pointer: coarse)').matches;
  return html`<span class="photo-picker">
    <input type="file" accept="image/*" capture=${isTouch ? 'environment' : undefined} ref=${fileRef} hidden
      onChange=${(e) => { handle(e.target.files[0]); e.target.value = ''; }} />
    <button class="btn" disabled=${busy} onClick=${() => (isTouch || !navigator.mediaDevices ? fileRef.current.click() : setLive(true))}>
      📷 ${busy ? 'Lädt…' : label}</button>
    ${!isTouch && html`<button class="btn ghost small" title="Bilddatei wählen" onClick=${() => fileRef.current.click()}>📁</button>`}
    ${live && html`<${CameraModal} onClose=${() => setLive(false)} onShot=${(f) => { setLive(false); handle(f); }} />`}
  </span>`;
}

function CameraModal({ onClose, onShot }) {
  const vid = useRef();
  const [err, setErr] = useState(null);
  useEffect(() => {
    let st;
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1440 } } })
      .then((s) => { st = s; vid.current.srcObject = s; })
      .catch((e) => setErr('Kamera nicht verfügbar: ' + e.message));
    return () => st && st.getTracks().forEach((t) => t.stop());
  }, []);
  const shoot = () => {
    const v = vid.current;
    const c = document.createElement('canvas');
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext('2d').drawImage(v, 0, 0);
    c.toBlob((b) => onShot(new File([b], 'kamera.jpg', { type: 'image/jpeg' })), 'image/jpeg', 0.9);
  };
  return html`<div class="modal-bg" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div class="modal camera">
      ${err ? html`<p>${err}</p>` : html`<video ref=${vid} autoplay playsinline muted></video>`}
      <p class="muted small">Halte das Blatt flach und gut beleuchtet ins Bild. Alles muss lesbar sein.</p>
      <div class="row gap"><button class="btn primary" onClick=${shoot} disabled=${!!err}>Aufnehmen</button><button class="btn" onClick=${onClose}>Abbrechen</button></div>
    </div></div>`;
}

export function Thumbs({ ids, onRemove }) {
  if (!ids || !ids.length) return null;
  return html`<div class="thumbs">${ids.map((p) => html`<span class="thumb"><img src=${`/api/photo/${p}`} />${onRemove && html`<button onClick=${() => onRemove(p)}>×</button>`}</span>`)}</div>`;
}

// ───────────── voice input (browser speech recognition) ─────────────
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
export function MicButton({ onText }) {
  const [on, setOn] = useState(false);
  const rec = useRef();
  if (!SR) return null;
  const toggle = () => {
    if (on) { rec.current && rec.current.stop(); return; }
    const r = new SR();
    r.lang = 'de-CH'; r.interimResults = false; r.continuous = true;
    r.onresult = (e) => { let t = ''; for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) t += e.results[i][0].transcript; if (t) onText(t.trim()); };
    r.onend = () => setOn(false);
    r.onerror = () => setOn(false);
    rec.current = r; r.start(); setOn(true);
  };
  return html`<button class=${`btn icon ${on ? 'rec' : ''}`} title=${on ? 'Aufnahme stoppen' : 'Spracheingabe'} onClick=${toggle}>${on ? '⏹' : '🎤'}</button>`;
}

// ───────────── small UI bits ─────────────
export function alertBox(msg) { const d = document.createElement('div'); d.className = 'toast'; d.textContent = msg; document.body.appendChild(d); setTimeout(() => d.remove(), 4200); }
export function toast(msg, kind = '') { const d = document.createElement('div'); d.className = `toast ${kind}`; d.innerHTML = msg; document.body.appendChild(d); setTimeout(() => d.remove(), 4200); }

export function Bar({ value, color, height = 8 }) {
  return html`<div class="bar" style=${`height:${height}px`}><div style=${`width:${Math.max(0, Math.min(100, (value || 0) * 100))}%;background:${color || 'var(--accent)'}`}></div></div>`;
}

export function Ring({ value, size = 64, label, color }) {
  const r = size / 2 - 6; const c = 2 * Math.PI * r; const v = Math.max(0, Math.min(1, value || 0));
  return html`<svg class="ring" width=${size} height=${size} viewBox=${`0 0 ${size} ${size}`}>
    <circle cx=${size / 2} cy=${size / 2} r=${r} fill="none" stroke="var(--line)" stroke-width="6" />
    <circle cx=${size / 2} cy=${size / 2} r=${r} fill="none" stroke=${color || 'var(--accent)'} stroke-width="6" stroke-linecap="round"
      stroke-dasharray=${`${c * v} ${c}`} transform=${`rotate(-90 ${size / 2} ${size / 2})`} />
    <text x="50%" y="50%" dominant-baseline="central" text-anchor="middle" font-size=${size / 4.2} font-weight="700" fill="var(--fg)">${label ?? Math.round(v * 100) + '%'}</text></svg>`;
}

// Line chart (mastery) with bars (solved) – data: [{day, mastery, solved}]
export function ProgressChart({ data, height = 180 }) {
  if (!data || !data.length) return null;
  const W = 640; const H = height; const pad = 28;
  const n = data.length; const maxS = Math.max(1, ...data.map((d) => d.solved));
  const x = (i) => pad + (W - 2 * pad) * (n === 1 ? 0.5 : i / (n - 1));
  const y = (m) => H - pad - (H - 2 * pad) * m;
  const pts = data.map((d, i) => `${x(i)},${y(d.mastery)}`).join(' ');
  const bw = Math.max(2, (W - 2 * pad) / n - 3);
  return html`<svg class="chart" viewBox=${`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Fortschritt">
    ${[0, 0.25, 0.5, 0.75, 1].map((g) => html`<line x1=${pad} x2=${W - pad} y1=${y(g)} y2=${y(g)} stroke="var(--line)" stroke-width="1" /><text x="2" y=${y(g) + 4} font-size="10" fill="var(--muted)">${g * 100}%</text>`)}
    ${data.map((d, i) => d.solved ? html`<rect x=${x(i) - bw / 2} width=${bw} y=${H - pad - (H - 2 * pad) * 0.35 * d.solved / maxS} height=${(H - 2 * pad) * 0.35 * d.solved / maxS} fill="var(--accent-soft)"><title>${d.day}: ${d.solved} gelöst</title></rect>` : null)}
    <polyline points=${pts} fill="none" stroke="var(--accent)" stroke-width="3" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
    ${[0, Math.floor(n / 2), n - 1].map((i) => html`<text x=${x(i)} y=${H - 6} font-size="10" text-anchor="middle" fill="var(--muted)">${data[i].day.slice(5).split('-').reverse().join('.')}</text>`)}
  </svg>`;
}

export function Loading() { return html`<div class="loading"><span class="spinner"></span> Lädt…</div>`; }

export function useApi(path, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    if (!path) return;
    set((s) => ({ ...s, loading: true }));
    api(path).then((d) => set({ data: d, error: null, loading: false })).catch((e) => set({ data: null, error: e.message, loading: false }));
  }, [path]);
  useEffect(load, [path, ...deps]);
  return { ...state, reload: load };
}

// ───────────── step-by-step solution ─────────────
function tex(t) {
  try { return window.katex.renderToString(fixTex(t), { displayMode: true, throwOnError: false, strict: false }); } catch (e) { return `<code>${t}</code>`; }
}

function RuleChip({ st }) {
  const [open, setOpen] = useState(false);
  if (!st.rule) return null;
  return html`<span class="rule-wrap"><button class=${`rule-chip ${open ? 'on' : ''}`} onClick=${() => setOpen(!open)} title="Angewandte Formel">📐 ${st.rule}</button>
    ${open && st.rule_formula ? html`<div class="rule-formula"><div dangerouslySetInnerHTML=${{ __html: tex(st.rule_formula) }}></div>
      ${st.card ? html`<a class="small" href="#/formeln" onClick=${() => sessionStorage.setItem('formel-card', st.card)}>in der Formelsammlung ↗</a>` : ''}</div>` : ''}</span>`;
}

// sol: {md, steps, formulas} or plain markdown. onAsk(text) opens the tutor. Steps play one by one.
export function SolutionSteps({ sol, onAsk, title = 'Lösungsweg', autoplay = true }) {
  const s = !sol ? null : typeof sol === 'string' ? { md: sol, steps: [] } : sol;
  const steps = (s && s.steps) || [];
  const [plain, setPlain] = useState(false);
  const [shown, setShown] = useState(autoplay ? 1 : steps.length);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return undefined;
    if (shown >= steps.length) { setPlaying(false); return undefined; }
    const t = setTimeout(() => setShown((n) => n + 1), 1100);
    return () => clearTimeout(t);
  }, [playing, shown, steps.length]);
  if (!s) return null;
  const ask = (i, st) => onAsk && onAsk(`Ich verstehe Schritt ${i + 1} des Lösungswegs nicht${st.note ? ` («${st.note.replace(/\$/g, '')}»)` : ''}${st.math ? `: $${st.math}$` : ''}${st.rule ? ` (angewandt: ${st.rule})` : ''}. Warum ist das so, und wie kommt man darauf?`);
  const all = shown >= steps.length;
  const stripDollar = (f) => (f || '').replace(/\$\$/g, '').replace(/^\s*\$|\$\s*$/g, '');
  return html`<div class="solution-steps">
    <div class="row between gap wrap"><b>${title}</b>
      <span class="row gap">${steps.length > 1 && !plain ? html`<span class="small muted">${Math.min(shown, steps.length)}/${steps.length}</span>` : ''}
      ${s.md && steps.length ? html`<button class="btn small ghost" onClick=${() => setPlain(!plain)}>${plain ? 'Schrittweise' : 'Als Text'}</button>` : ''}</span></div>
    ${s.formulas && s.formulas.length && !plain ? html`<div class="used-formulas"><span class="small muted">Benutzte Formeln:</span>
      ${s.formulas.map((f) => html`<${RuleChip} st=${{ rule: f.name, rule_formula: stripDollar(f.formula), card: f.id }} />`)}</div>` : ''}
    ${plain || !steps.length ? html`<${Md} src=${s.md || ''} />` : html`<ol class="steps">${steps.slice(0, shown).map((st, i) => html`
      <li class=${`step ${st.result ? 'result' : ''}`} key=${i}>
        <span class="num">${i + 1}</span>
        <div class="body">
          ${st.note || st.rule ? html`<div class="note-row">${st.note ? html`<span class="note"><${Md} src=${st.note} /></span>` : ''}<${RuleChip} st=${st} /></div>` : ''}
          ${st.math ? html`<div class="math" dangerouslySetInnerHTML=${{ __html: tex(st.math) }}></div>` : ''}
          ${st.calc ? html`<div class="calc">🧮 <code>${st.calc}</code></div>` : ''}
        </div>
        ${onAsk ? html`<button class="ask" title="Frage zu diesem Schritt" onClick=${() => ask(i, st)}>💬</button>` : ''}
      </li>`)}</ol>
      ${!all ? html`<div class="row gap wrap" style="margin-top:.45rem">
        <button class="btn small primary" onClick=${() => { setPlaying(false); setShown(shown + 1); }}>Nächster Schritt ▶</button>
        <button class="btn small" onClick=${() => setPlaying(!playing)}>${playing ? '⏸ Pause' : '⏵ Abspielen'}</button>
        <button class="btn small ghost" onClick=${() => { setPlaying(false); setShown(steps.length); }}>Alle zeigen</button>
        <span class="small muted">Tipp: Überleg dir zuerst selbst, wie der nächste Schritt aussieht.</span></div>` : ''}`}
    ${onAsk && (all || plain || !steps.length) ? html`<div class="row gap wrap" style="margin-top:.45rem">
      <button class="btn small" onClick=${() => onAsk('Ich habe eine Frage zum Lösungsweg: ')}>💬 Frage zur Lösung</button>
      <button class="btn small ghost" onClick=${() => onAsk('Kannst du mir den Lösungsweg nochmals ausführlicher und mit einem ähnlichen Beispiel erklären?')}>🔎 Ausführlicher erklären</button></div>` : ''}
  </div>`;
}


// ───────────── "Fehler melden" ─────────────
const REPORT_KINDS = [
  ['antwort', 'Meine Antwort ist richtig, wird aber nicht akzeptiert'],
  ['loesung', 'Lösung / Lösungsweg ist falsch'],
  ['aufgabe', 'Aufgabe ist unklar oder fehlerhaft'],
  ['darstellung', 'Formel / Darstellung ist kaputt'],
  ['abbildung', 'Abbildung fehlt oder ist falsch'],
  ['anderes', 'Anderes'],
];
export function ReportButton({ ex, inputs = {}, small = true }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('antwort');
  const [part, setPart] = useState(ex.parts.length === 1 ? (ex.parts[0].label || '') : '');
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      const r = await api(`/api/exercise/${ex.id}/report`, { method: 'POST', body: { kind, part, comment, context: { input: inputs[part] ?? null, url: location.hash } } });
      toast(`✅ ${r.message}`, 'ok'); setOpen(false); setComment('');
    } catch (e) { toast(e.message, 'bad'); }
    setBusy(false);
  };
  return html`<span>
    <button class=${`btn ${small ? 'small' : ''} ghost`} title="Fehler in dieser Aufgabe melden" onClick=${() => setOpen(true)}>⚠️ Fehler melden</button>
    ${open && html`<div class="modal-bg" onClick=${(e) => e.target === e.currentTarget && setOpen(false)}><div class="modal" style="max-width:520px">
      <h2 style="margin-top:0">Fehler melden</h2>
      <p class="small muted" style="margin-top:0">«${ex.title}» – dein Coach bekommt die Meldung und prüft die Aufgabe.</p>
      <div class="choice">${REPORT_KINDS.map(([k, l]) => html`<label class=${kind === k ? 'sel' : ''}><input type="radio" name="rk" checked=${kind === k} onChange=${() => setKind(k)} />${l}</label>`)}</div>
      ${ex.parts.length > 1 && html`<label class="field">Teilaufgabe<select value=${part} onChange=${(e) => setPart(e.target.value)}>
        <option value="">ganze Aufgabe</option>${ex.parts.map((p) => html`<option value=${p.label || ''}>${p.label ? p.label + ')' : 'Teil'}</option>`)}</select></label>`}
      ${kind === 'antwort' && inputs[part] ? html`<p class="small">Deine Eingabe: <code>${inputs[part]}</code> wird mitgeschickt.</p>` : ''}
      <label class="field">Was ist falsch? (optional)<textarea rows="3" value=${comment} onInput=${(e) => setComment(e.target.value)} placeholder="z.B. «In der Lösung steht −4, es müsste +4 sein»"></textarea></label>
      <div class="row gap"><button class="btn primary" disabled=${busy} onClick=${send}>Melden</button><button class="btn" onClick=${() => setOpen(false)}>Abbrechen</button></div>
    </div></div>`}
  </span>`;
}

// ───────────── chat ─────────────
// Coach chats carry the student data as a JSON preamble: show only what was typed.
// Plain text with only $…$ / $$…$$ rendered as math (no Markdown: "x^2*sin(x)" must stay as typed).
export function MathText({ src }) {
  const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const parts = String(src || '').split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g);
  const h = parts.map((p) => {
    const d = p.startsWith('$$') && p.endsWith('$$') && p.length > 4;
    const i = !d && p.startsWith('$') && p.endsWith('$') && p.length > 2;
    if (d || i) {
      try { return window.katex.renderToString(fixTex(p.slice(d ? 2 : 1, d ? -2 : -1)), { displayMode: d, throwOnError: false, strict: false }); } catch (e) { return esc(p); }
    }
    return esc(p);
  }).join('');
  return html`<span class="mathtext" dangerouslySetInnerHTML=${{ __html: h }}></span>`;
}
export const userText = (t) => (t && t.startsWith('[DATEN ZUM LERNSTAND') ? t.slice(t.lastIndexOf('\n\n') + 2) : t || '');

const TOOL_LABEL = { python: 'rechnet nach…', check_answer: 'prüft das Resultat…', equivalent: 'vergleicht Ausdrücke…', plot: 'zeichnet ein Diagramm…', submit_review: 'schreibt die Korrektur…' };

export function Chat({ chatId, exerciseId, mode: initialMode = 'chat', modes = true, compact = false, intro, onReview, adminKind = false, prefill = '' }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState(prefill);
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  const [tool, setTool] = useState(null);
  const [mode, setMode] = useState(initialMode);
  const [cid, setCid] = useState(chatId);
  const endRef = useRef();
  // A chat created by our own first message must not be reloaded from the server: that would
  // replace the streaming reply and the next text deltas would land in the user's bubble.
  const created = useRef(null);
  useEffect(() => { setCid(chatId); }, [chatId]);
  useEffect(() => {
    if (!cid) { setMsgs([]); return; }
    if (created.current === cid) return;
    api(`/api/chats/${cid}`).then((d) => setMsgs(d.messages)).catch(() => {});
  }, [cid]);
  useEffect(() => { endRef.current && endRef.current.scrollIntoView({ block: 'end', behavior: 'smooth' }); }, [msgs, tool]);

  const send = async (overrideText, overrideMode) => {
    const t = (overrideText ?? text).trim();
    if (!t && !photos.length) return;
    let id = cid;
    if (!id) {
      const r = await api('/api/chats', { method: 'POST', body: { title: t.slice(0, 60) || 'Foto', exercise_id: exerciseId, kind: adminKind ? 'admin' : 'chat' } });
      id = r.id; created.current = id; setCid(id);
    }
    const m = overrideMode || mode;
    setMsgs((x) => [...x, { role: 'user', content: t, attachments: photos, meta: { mode: m } }, { role: 'assistant', content: '', streaming: true }]);
    setText(''); const ph = photos; setPhotos([]); setBusy(true);
    const upd = (f) => setMsgs((x) => {
      const y = x.slice();
      const i = y.length - 1;
      if (i < 0 || y[i].role !== 'assistant') return y;
      y[i] = f(y[i]);
      return y;
    });
    await stream(`/api/chats/${id}/send`, { text: t, photo_ids: ph, mode: m, exercise_id: exerciseId }, (ev) => {
      if (ev.t === 'text') { setTool(null); upd((a) => ({ ...a, content: a.content + ev.d })); }
      else if (ev.t === 'replace') upd((a) => ({ ...a, content: ev.text }));
      else if (ev.t === 'tool') setTool(ev.name);
      else if (ev.t === 'error') upd((a) => ({ ...a, content: (a.content ? a.content + '\n\n' : '') + `⚠️ ${ev.message}` }));
      else if (ev.t === 'review' && onReview) onReview(ev.data);
      else if (ev.t === 'done') upd((a) => ({ ...a, streaming: false }));
    });
    setTool(null); setBusy(false);
  };

  const modeChips = [
    ['chat', '💬 Frage'], ['explain', '📖 Erklär mir'], ['check_step', '🔍 Schritt prüfen'], ['hint', '💡 Hinweis'], ['explain_back', '🗣️ Erklär\'s zurück'],
  ];
  return html`<div class=${`chat ${compact ? 'compact' : ''}`}>
    <div class="chat-msgs">
      ${!msgs.length && html`<div class="chat-intro">${intro || html`<p><b>Hallo!</b> Ich bin dein Mathe-Coach. Frag mich alles zu Mathe II – schreib, sprich 🎤 oder fotografiere 📷 deine Rechnung.</p>`}</div>`}
      ${msgs.map((m) => html`<div class=${`msg ${m.role}`}>
        ${m.attachments && m.attachments.length && m.role === 'user' ? html`<${Thumbs} ids=${m.attachments} />` : null}
        ${m.role === 'assistant' ? html`<${Md} src=${m.content || ''} />` : html`<div class="bubble">${m.meta && m.meta.mode && m.meta.mode !== 'chat' && m.meta.mode !== 'admin' ? html`<span class="tag">${(modeChips.find((c) => c[0] === m.meta.mode) || [0, m.meta.mode])[1]}</span>` : ''}<${MathText} src=${userText(m.content)} /></div>`}
        ${m.streaming && !m.content && html`<div class="typing"><span></span><span></span><span></span>${tool ? html`<em> ${TOOL_LABEL[tool] || tool}</em>` : ''}</div>`}
        ${m.streaming && m.content && tool ? html`<div class="typing"><em>${TOOL_LABEL[tool] || tool}</em></div>` : null}
      </div>`)}
      <div ref=${endRef}></div>
    </div>
    ${modes && html`<div class="chips">${modeChips.map(([k, l]) => html`<button class=${`chip ${mode === k ? 'on' : ''}`} onClick=${() => setMode(k)}>${l}</button>`)}</div>`}
    <${Thumbs} ids=${photos} onRemove=${(p) => setPhotos(photos.filter((x) => x !== p))} />
    <div class="chat-input">
      <textarea rows="2" value=${text} placeholder=${mode === 'explain_back' ? 'Erklär das Thema in deinen eigenen Worten…' : 'Nachricht schreiben… (Mathe z.B. als x^2 oder $x^2$)'}
        onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!busy) send(); } }}></textarea>
      <div class="chat-actions">
        <${MicButton} onText=${(t) => setText((x) => (x ? x + ' ' : '') + t)} />
        <${PhotoPicker} label="" onPhoto=${(p) => setPhotos((x) => [...x, p.id])} exerciseId=${exerciseId} />
        <button class="btn primary" disabled=${busy} onClick=${() => send()}>${busy ? '…' : 'Senden'}</button>
      </div>
    </div>
  </div>`;
}

// ───────────── diagnostics (for feedback reports) ─────────────
const DIAG = { errors: [], requests: [], routes: [], started: new Date().toISOString() };
const pushLimited = (arr, item, n = 15) => { arr.push(item); if (arr.length > n) arr.shift(); };
window.addEventListener('error', (e) => pushLimited(DIAG.errors, { t: new Date().toISOString(), msg: String(e.message), src: `${e.filename || ''}:${e.lineno || ''}:${e.colno || ''}`, stack: e.error && e.error.stack ? String(e.error.stack).slice(0, 1500) : null }));
window.addEventListener('unhandledrejection', (e) => pushLimited(DIAG.errors, { t: new Date().toISOString(), msg: 'Promise: ' + String(e.reason && e.reason.message ? e.reason.message : e.reason), stack: e.reason && e.reason.stack ? String(e.reason.stack).slice(0, 1500) : null }));
const origConsoleError = console.error.bind(console);
console.error = (...a) => { pushLimited(DIAG.errors, { t: new Date().toISOString(), msg: 'console.error: ' + a.map((x) => (x && x.message) || String(x)).join(' ').slice(0, 500) }); origConsoleError(...a); };
const trackRoute = () => pushLimited(DIAG.routes, { t: new Date().toISOString(), hash: location.hash || '#/' }, 12);
window.addEventListener('hashchange', trackRoute); trackRoute();
export function logRequest(entry) { pushLimited(DIAG.requests, { t: new Date().toISOString(), ...entry }); }

export function diagnostics() {
  const h1 = document.querySelector('main h1, main h2');
  return {
    page: { url: location.pathname + location.hash, hash: location.hash || '#/', title: document.title, heading: h1 ? h1.innerText.slice(0, 120) : null,
      exercise: window.__currentExercise || null, area: location.pathname.startsWith('/admin') ? 'coach' : 'student' },
    client: { ua: navigator.userAgent, viewport: `${innerWidth}x${innerHeight}`, dpr: devicePixelRatio, lang: navigator.language,
      dark: matchMedia('(prefers-color-scheme: dark)').matches, touch: matchMedia('(pointer: coarse)').matches, online: navigator.onLine },
    version: window.__appVersion || null, opened: DIAG.started, at: new Date().toISOString(),
    js_errors: DIAG.errors.slice(), failed_requests: DIAG.requests.filter((r) => !r.ok).slice(-8), recent_requests: DIAG.requests.slice(-6), routes: DIAG.routes.slice(),
  };
}

let h2cLoading = null;
function loadHtml2canvas() {
  if (window.html2canvas) return Promise.resolve(window.html2canvas);
  if (!h2cLoading) {
    h2cLoading = new Promise((res, rej) => {
      const s = document.createElement('script'); s.src = '/static/vendor/html2canvas.min.js';
      s.onload = () => res(window.html2canvas); s.onerror = rej; document.head.appendChild(s);
    });
  }
  return h2cLoading;
}
async function capturePage() {
  const h2c = await loadHtml2canvas();
  const bg = getComputedStyle(document.body).backgroundColor;
  const canvas = await h2c(document.body, {
    backgroundColor: bg, scale: Math.min(1.5, devicePixelRatio || 1), useCORS: true, logging: false,
    x: scrollX, y: scrollY, width: innerWidth, height: innerHeight, windowWidth: innerWidth, windowHeight: innerHeight,
    ignoreElements: (el) => el.dataset && el.dataset.html2canvasIgnore !== undefined,
  });
  const blob = await new Promise((r) => canvas.toBlob(r, 'image/png'));
  return new File([blob], 'bildschirm.png', { type: 'image/png' });
}

const FB_KINDS = [['bug', '🐞 Etwas ist kaputt'], ['wunsch', '💡 Verbesserungsvorschlag'], ['frage', '❓ Frage'], ['lob', '🎉 Lob']];

export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState('bug');
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState([]);
  const [shot, setShot] = useState('idle'); // idle | busy | done | failed
  const [ctx, setCtx] = useState(null);
  const [busy, setBusy] = useState(false);
  const start = async () => {
    const c = diagnostics();       // context of the page as it is now, before the dialog opens
    setCtx(c); setShot('busy'); setOpen(true);
    try { const f = await capturePage(); const r = await uploadPhoto(f); setPhotos((p) => [r.id, ...p]); setShot('done'); } catch (e) { setShot('failed'); }
  };
  const onPaste = async (e) => {
    const items = [...(e.clipboardData ? e.clipboardData.items : [])].filter((i) => i.type.startsWith('image/'));
    if (!items.length) return;
    e.preventDefault();
    for (const it of items) { const r = await uploadPhoto(it.getAsFile()); setPhotos((p) => [...p, r.id]); }
  };
  const send = async () => {
    if (!text.trim() && !photos.length) { toast('Schreib kurz, was passiert ist.', 'bad'); return; }
    setBusy(true);
    try {
      const r = await api('/api/feedback', { method: 'POST', body: { kind, text, photo_ids: photos, context: ctx } });
      toast(`✅ ${r.message}`, 'ok'); setOpen(false); setText(''); setPhotos([]); setShot('idle');
    } catch (e) { toast(e.message, 'bad'); }
    setBusy(false);
  };
  return html`<div data-html2canvas-ignore>
    <button class="feedback-fab noprint" title="Feedback geben oder Fehler melden" onClick=${start}>💬 Feedback</button>
    ${open && html`<div class="modal-bg" onClick=${(e) => e.target === e.currentTarget && setOpen(false)}><div class="modal" style="max-width:560px">
      <h2 style="margin-top:0">Feedback</h2>
      <div class="chips" style="flex-wrap:wrap">${FB_KINDS.map(([k, l]) => html`<button class=${`chip ${kind === k ? 'on' : ''}`} onClick=${() => setKind(k)}>${l}</button>`)}</div>
      <label class="field">${kind === 'bug' ? 'Was ist passiert? Was hast du erwartet?' : kind === 'wunsch' ? 'Was wünschst du dir?' : 'Deine Nachricht'}
        <textarea rows="4" value=${text} onInput=${(e) => setText(e.target.value)} onPaste=${onPaste}
          placeholder=${kind === 'bug' ? 'z.B. «Beim Klick auf Prüfen passiert nichts» – Screenshots kannst du hier auch einfügen (Strg+V)' : ''}></textarea></label>
      <div class="row gap wrap"><span class="small muted">${shot === 'busy' ? '📸 Screenshot der Seite wird erstellt…' : shot === 'done' ? '📸 Screenshot der aktuellen Seite ist angehängt' : shot === 'failed' ? 'Automatischer Screenshot ging nicht – füge selbst einen ein' : ''}</span></div>
      <${Thumbs} ids=${photos} onRemove=${(id) => setPhotos(photos.filter((x) => x !== id))} />
      <div class="row gap wrap" style="margin:.4rem 0"><${PhotoPicker} label="Bild hinzufügen" onPhoto=${(p) => setPhotos((x) => [...x, p.id])} /></div>
      ${ctx && html`<details class="small"><summary>Technische Infos, die mitgeschickt werden</summary>
        <ul class="list small"><li>Seite: <code>${ctx.page.hash}</code>${ctx.page.exercise ? html` · Aufgabe <code>${ctx.page.exercise}</code>` : ''}</li>
        <li>Gerät: ${ctx.client.viewport}, ${ctx.client.touch ? 'Touch' : 'Maus'}, ${ctx.client.dark ? 'Dunkel' : 'Hell'} · Version ${ctx.version || '–'}</li>
        <li>${ctx.js_errors.length} JavaScript-Fehler, ${ctx.failed_requests.length} fehlgeschlagene Anfragen</li></ul></details>`}
      <div class="row gap" style="margin-top:.6rem"><button class="btn primary" disabled=${busy || shot === 'busy'} onClick=${send}>Senden</button><button class="btn" onClick=${() => setOpen(false)}>Abbrechen</button></div>
    </div></div>`}
  </div>`;
}
