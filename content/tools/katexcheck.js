// Render every LaTeX snippet in content/ with the app's own KaTeX and report failures.
// Usage: node content/tools/katexcheck.js   (exit code 1 on errors)
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const katex = require(path.resolve(ROOT, '../app/mathtutor/static/vendor/katex/katex.min.js'));

const errors = [];
let count = 0;
function render(tex, display, where) {
  count++;
  try { katex.renderToString(tex, { displayMode: display, throwOnError: true, strict: false }); } catch (e) {
    errors.push(`${where}: ${e.message.split('\n')[0]}  ::  ${tex.slice(0, 90)}`);
  }
}
function scanText(t, where) {
  if (typeof t !== 'string' || !t) return;
  const s = t.replace(/```[\s\S]*?```/g, '');
  for (const m of s.matchAll(/\$\$([\s\S]+?)\$\$/g)) render(m[1], true, where);
  const rest = s.replace(/\$\$[\s\S]+?\$\$/g, '');
  for (const m of rest.matchAll(/(^|[^\\$])\$(?!\s)((?:\\\$|[^$\n])+?)\$/g)) render(m[2], false, where);
}
function walk(obj, where) {
  if (Array.isArray(obj)) obj.forEach((v, i) => walk(v, `${where}[${i}]`));
  else if (obj && typeof obj === 'object') {
    for (const [k, v] of Object.entries(obj)) {
      if ((k === 'math' || k === 'rule_formula') && typeof v === 'string') render(v, true, `${where}.${k}`);
      else if (k === 'value' || k === 'id' || k === 'skills' || k === 'figures' || k === 'calc') continue;
      else if (typeof v === 'string') scanText(v, `${where}.${k}`);
      else walk(v, `${where}.${k}`);
    }
  }
}
for (const dir of ['exercises', 'formula-cards']) {
  for (const f of fs.readdirSync(path.join(ROOT, dir)).filter((x) => x.endsWith('.json'))) {
    walk(JSON.parse(fs.readFileSync(path.join(ROOT, dir, f), 'utf8')), `${dir}/${f}`);
  }
}
for (const dir of ['theory', 'formeln']) {
  for (const f of fs.readdirSync(path.join(ROOT, dir)).filter((x) => x.endsWith('.md'))) {
    scanText(fs.readFileSync(path.join(ROOT, dir, f), 'utf8'), `${dir}/${f}`);
  }
}
for (const e of errors) console.log(e);
console.log(`${count} snippets, ${errors.length} errors`);
process.exit(errors.length ? 1 : 0);
