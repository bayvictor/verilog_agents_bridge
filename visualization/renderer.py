"""Generate a self-contained HTML visualisation for Verilog-A modules."""

import json
from pathlib import Path
from typing import List

from .parser import VerilogAModule

# ── Serialisation helpers ────────────────────────────────────────────────────

def _module_to_dict(mod: VerilogAModule) -> dict:
    return {
        'name': mod.name,
        'port_names': mod.port_names,
        'ports': [{'name': p.name, 'direction': p.direction, 'discipline': p.discipline}
                  for p in mod.ports],
        'parameters': [{'name': p.name, 'ptype': p.ptype, 'default': p.default}
                       for p in mod.parameters],
        'nets': mod.nets,
        'branches': [{'name': b.name, 'node_plus': b.node_plus, 'node_minus': b.node_minus}
                     for b in mod.branches],
        'contributions': [{'nature': c.nature, 'target': c.target, 'expression': c.expression}
                          for c in mod.contributions],
        'instances': [{'module_name': i.module_name, 'inst_name': i.inst_name,
                       'connections': i.connections}
                      for i in mod.instances],
    }


# ── HTML template ─────────────────────────────────────────────────────────────

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VA Visualizer — __TITLE__</title>
<style>
/* ── Reset & base ──────────────────────────────────────────────────── */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}
/* ── Themes ────────────────────────────────────────────────────────── */
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#21262d;--surface3:#30363d;
  --border:#30363d;--accent:#58a6ff;--accent2:#f78166;
  --text:#c9d1d9;--text-dim:#8b949e;--text-bright:#f0f6fc;
  --inp:#4fc3f7;--out:#ef9a9a;--io:#a5d6a7;
  --kw:#ff7b72;--str:#a5d6a7;--num:#79c0ff;--cmt:#8b949e;--nat:#ffa657;
  --v-color:#ffd700;--i-color:#87ceeb;
  --shadow:0 4px 12px rgba(0,0,0,.4);
}
[data-theme="light"]{
  --bg:#f6f8fa;--surface:#fff;--surface2:#f6f8fa;--surface3:#eaeef2;
  --border:#d0d7de;--accent:#0969da;--accent2:#cf222e;
  --text:#1f2328;--text-dim:#656d76;--text-bright:#1f2328;
  --inp:#0969da;--out:#cf222e;--io:#1a7f37;
  --kw:#cf222e;--str:#0a3069;--num:#0550ae;--cmt:#57606a;--nat:#953800;
  --v-color:#8a5c00;--i-color:#0550ae;
  --shadow:0 2px 8px rgba(0,0,0,.1);
}
/* ── Layout ────────────────────────────────────────────────────────── */
body{background:var(--bg);color:var(--text);display:flex;flex-direction:column}
#app{display:flex;flex-direction:column;height:100vh;overflow:hidden}
header{
  background:var(--surface);border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px;padding:6px 14px;
  flex-shrink:0;flex-wrap:wrap;z-index:10;box-shadow:var(--shadow);
}
.logo{font-weight:700;font-size:15px;color:var(--accent);letter-spacing:.5px;white-space:nowrap}
.file-label{color:var(--text-dim);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:280px}
#module-selector{
  background:var(--surface2);border:1px solid var(--border);color:var(--text);
  padding:3px 8px;border-radius:6px;cursor:pointer;font-size:13px;
}
.tab-bar{display:flex;gap:2px;margin-left:auto}
.tab-btn{
  background:transparent;border:1px solid transparent;color:var(--text-dim);
  padding:4px 12px;border-radius:6px;cursor:pointer;font-size:13px;
  transition:all .15s;white-space:nowrap;
}
.tab-btn:hover{background:var(--surface2);color:var(--text)}
.tab-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
#theme-btn{
  background:var(--surface2);border:1px solid var(--border);color:var(--text);
  padding:3px 8px;border-radius:6px;cursor:pointer;font-size:13px;
  margin-left:6px;white-space:nowrap;
}
main{flex:1;overflow:hidden;position:relative}
.tab-panel{display:none;width:100%;height:100%;overflow:auto}
.tab-panel.active{display:flex;flex-direction:column}

/* ── Block diagram panel ────────────────────────────────────────────── */
#panel-block{align-items:center;justify-content:flex-start;padding:16px;gap:0;overflow:auto}
#diagram-wrap{
  background:var(--surface);border:1px solid var(--border);border-radius:10px;
  box-shadow:var(--shadow);padding:16px;min-width:500px;max-width:1200px;width:100%;
}
#diagram-svg{width:100%;display:block}
#no-modules-msg{color:var(--text-dim);text-align:center;padding:40px;font-size:16px}

/* ── SVG element classes ─────────────────────────────────────────────── */
.module-box{fill:var(--surface2);stroke:var(--border);stroke-width:2}
.module-title-bar{fill:var(--surface3);stroke:none}
.module-name-text{font-size:14px;font-weight:700;fill:var(--text-bright)}
.port-wire{stroke:var(--text-dim);stroke-width:1.5;fill:none}
.port-label{font-size:12px;fill:var(--text)}
.port-dot-input{fill:var(--inp)}
.port-dot-output{fill:var(--out)}
.port-dot-inout{fill:var(--io)}
.arrow-input{fill:var(--inp)}
.arrow-output{fill:var(--out)}
.arrow-inout{fill:var(--io)}
.section-label{font-size:10px;fill:var(--text-dim);font-weight:600;letter-spacing:.5px}
.param-text{font-size:11px;fill:var(--num)}
.branch-text{font-size:11px;fill:var(--nat)}
.net-text{font-size:11px;fill:var(--io)}
.inst-text{font-size:11px;fill:var(--str)}
.contrib-legend-title{font-size:11px;font-weight:600;fill:var(--text-dim)}
.contrib-v{font-size:11px;fill:var(--v-color)}
.contrib-i{font-size:11px;fill:var(--i-color)}
.discipline-badge{font-size:9px;fill:var(--text-dim)}

/* ── Code view ───────────────────────────────────────────────────────── */
#panel-code{overflow:auto}
#code-container{
  display:flex;font-family:'Cascadia Code','Fira Code','JetBrains Mono',monospace;
  font-size:13px;line-height:1.55;white-space:pre;overflow:auto;
  background:var(--surface);border:1px solid var(--border);margin:12px;
  border-radius:8px;box-shadow:var(--shadow);
}
#line-numbers{
  user-select:none;text-align:right;padding:12px 10px 12px 12px;
  color:var(--text-dim);border-right:1px solid var(--border);min-width:42px;
}
#code-content{padding:12px 16px;overflow:visible;flex:1}
/* Syntax highlighting */
.hl-kw{color:var(--kw);font-weight:600}
.hl-str{color:var(--str)}
.hl-num{color:var(--num)}
.hl-cmt{color:var(--cmt);font-style:italic}
.hl-nat{color:var(--nat);font-weight:600}
.hl-dir{color:var(--inp);font-style:italic}

/* ── Details panel ────────────────────────────────────────────────────── */
#panel-details{overflow:auto;padding:14px}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px;align-items:start}
.detail-card{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  overflow:hidden;box-shadow:var(--shadow);
}
.detail-card h3{
  background:var(--surface2);color:var(--accent);font-size:13px;font-weight:600;
  padding:8px 12px;border-bottom:1px solid var(--border);letter-spacing:.3px;
}
.detail-card table{width:100%;border-collapse:collapse;font-size:12px}
.detail-card th{background:var(--surface3);color:var(--text-dim);padding:5px 10px;text-align:left;font-weight:600}
.detail-card td{padding:5px 10px;border-top:1px solid var(--border);color:var(--text)}
.detail-card tr:hover td{background:var(--surface2)}
.badge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:11px;font-weight:600}
.badge-input{background:rgba(79,195,247,.15);color:var(--inp)}
.badge-output{background:rgba(239,154,154,.15);color:var(--out)}
.badge-inout{background:rgba(165,214,167,.15);color:var(--io)}
.badge-v{background:rgba(255,215,0,.12);color:var(--v-color)}
.badge-i{background:rgba(135,206,235,.12);color:var(--i-color)}
.empty-msg{padding:12px;color:var(--text-dim);font-size:12px;text-align:center}

/* ── Footer ──────────────────────────────────────────────────────────── */
footer{
  background:var(--surface);border-top:1px solid var(--border);
  padding:4px 14px;font-size:11px;color:var(--text-dim);flex-shrink:0;
  display:flex;gap:16px;flex-wrap:wrap;
}
footer span{white-space:nowrap}
</style>
</head>
<body>
<div id="app">
  <header>
    <span class="logo">&#x2B21; VA Visualizer</span>
    <span class="file-label" title="__FILEPATH__">__TITLE__</span>
    <select id="module-selector" onchange="selectModule(+this.value)"></select>
    <nav class="tab-bar">
      <button class="tab-btn active" onclick="showTab('block',this)">&#x25A6; Block Diagram</button>
      <button class="tab-btn" onclick="showTab('code',this)">&#x276F;_ Code View</button>
      <button class="tab-btn" onclick="showTab('details',this)">&#x2261; Details</button>
    </nav>
    <button id="theme-btn" onclick="toggleTheme()">&#9728;/&#9790;</button>
  </header>

  <main>
    <div id="panel-block" class="tab-panel active">
      <div id="diagram-wrap">
        <svg id="diagram-svg" xmlns="http://www.w3.org/2000/svg"></svg>
        <div id="no-modules-msg" style="display:none">No modules found in this file.</div>
      </div>
    </div>
    <div id="panel-code" class="tab-panel">
      <div id="code-container">
        <div id="line-numbers"></div>
        <div id="code-content"></div>
      </div>
    </div>
    <div id="panel-details" class="tab-panel">
      <div class="detail-grid" id="detail-grid"></div>
    </div>
  </main>

  <footer>
    <span id="ft-file"></span>
    <span id="ft-modules"></span>
    <span id="ft-ports"></span>
    <span id="ft-params"></span>
    <span id="ft-contribs"></span>
  </footer>
</div>

<script>
/* ── Data injected by Python renderer ─────────────────────────────── */
const DATA = __JSON_DATA__;
/* ────────────────────────────────────────────────────────────────── */

let currentIdx = 0;

/* ─── Initialisation ─────────────────────────────────────────────── */
(function init() {
  populateSelector();
  renderCode();
  selectModule(0);
})();

function populateSelector() {
  const sel = document.getElementById('module-selector');
  if (!DATA.modules.length) { sel.style.display = 'none'; return; }
  DATA.modules.forEach((m, i) => {
    const opt = document.createElement('option');
    opt.value = i; opt.textContent = m.name;
    sel.appendChild(opt);
  });
}

function selectModule(idx) {
  currentIdx = idx;
  const mod = DATA.modules[idx];
  if (!mod) { document.getElementById('diagram-svg').innerHTML = '';
              document.getElementById('no-modules-msg').style.display = 'block'; return; }
  document.getElementById('no-modules-msg').style.display = 'none';
  renderBlockDiagram(mod);
  renderDetails(mod);
  renderFooter(mod);
}

/* ─── Tab switching ──────────────────────────────────────────────── */
function showTab(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
}

/* ─── Theme toggle ───────────────────────────────────────────────── */
function toggleTheme() {
  const h = document.documentElement;
  h.dataset.theme = h.dataset.theme === 'dark' ? 'light' : 'dark';
  renderBlockDiagram(DATA.modules[currentIdx]);
}

/* ─── SVG helpers ────────────────────────────────────────────────── */
const SVGNS = 'http://www.w3.org/2000/svg';
function svgEl(tag, attrs) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}
function svgText(parent, x, y, txt, cls, anchor='middle') {
  const t = svgEl('text', {x, y, class:cls, 'text-anchor':anchor, 'dominant-baseline':'middle'});
  t.textContent = txt;
  parent.appendChild(t); return t;
}
function svgLine(parent, x1, y1, x2, y2, cls) {
  parent.appendChild(svgEl('line', {x1, y1, x2, y2, class:cls}));
}
function svgRect(parent, x, y, w, h, attrs={}) {
  parent.appendChild(svgEl('rect', {x, y, width:w, height:h, ...attrs}));
}
function svgArrow(parent, x, y, dir, cls) {
  /* dir: 'right' | 'left' | 'both' */
  const s = 7;
  let pts;
  if (dir === 'right') pts = `${x-s},${y-s/2} ${x+s},${y} ${x-s},${y+s/2}`;
  else if (dir === 'left') pts = `${x+s},${y-s/2} ${x-s},${y} ${x+s},${y+s/2}`;
  else pts = `${x-s},${y} ${x},${y-s} ${x+s},${y} ${x},${y+s}`;  /* diamond */
  parent.appendChild(svgEl('polygon', {points:pts, class:cls}));
}

/* ─── Block Diagram ──────────────────────────────────────────────── */
function renderBlockDiagram(mod) {
  const svg = document.getElementById('diagram-svg');
  svg.innerHTML = '';

  const inputs  = mod.ports.filter(p => p.direction === 'input');
  const outputs = mod.ports.filter(p => p.direction === 'output');
  const inouts  = mod.ports.filter(p => p.direction === 'inout');

  /* distribute inouts: even indices -> left, odd -> right */
  const leftPorts  = [...inputs,  ...inouts.filter((_,i) => i%2===0)];
  const rightPorts = [...outputs, ...inouts.filter((_,i) => i%2===1)];

  const PORT_SPACE = 46, BOX_PAD = 36, MIN_H = 180, MIN_W = 160;
  const PORT_LEN = 60, LBL_GAP = 7;
  const TITLE_H = 28;

  const maxSide = Math.max(leftPorts.length, rightPorts.length, 1);

  /* compute box content height */
  const paramLines = mod.parameters.length
    ? mod.parameters.length + 1 : 0;          /* section label + items */
  const branchLines = mod.branches.length
    ? mod.branches.length + 1 : 0;
  const internalNets = mod.nets.filter(n => !mod.ports.some(p=>p.name===n));
  const netLines = internalNets.length ? 1 + 1 : 0;
  const instLines = mod.instances.length ? mod.instances.length + 1 : 0;
  const contentLines = paramLines + branchLines + netLines + instLines;
  const contentH = contentLines * 16 + 20;

  const portsH = maxSide * PORT_SPACE + BOX_PAD * 2;
  const boxH = Math.max(MIN_H, portsH, TITLE_H + contentH + 20);

  /* estimate box width from content */
  const allContent = [
    mod.name,
    ...mod.parameters.map(p => `${p.name} = ${p.default}`),
    ...mod.branches.map(b => b.node_minus ? `${b.name}(${b.node_plus},${b.node_minus})` : `${b.name}(${b.node_plus})`),
    ...internalNets,
    ...mod.instances.map(i => `${i.inst_name}: ${i.module_name}`),
  ];
  const maxCh = Math.max(...allContent.map(s=>s.length), 10);
  const boxW = Math.max(MIN_W, maxCh * 7 + 24);

  const svgW = boxW + PORT_LEN * 2 + 130;
  const svgH = boxH + (mod.contributions.length ? 16*Math.min(mod.contributions.length,5)+40 : 10) + 30;

  const boxX = PORT_LEN + 65;
  const boxY = 20;

  svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');

  /* ── Module box ────────────────────────────── */
  svgRect(svg, boxX, boxY, boxW, boxH, {rx:8, ry:8, class:'module-box'});

  /* title bar */
  svgRect(svg, boxX, boxY, boxW, TITLE_H, {rx:8, ry:8, class:'module-title-bar'});
  svgRect(svg, boxX, boxY+TITLE_H-8, boxW, 8, {class:'module-title-bar'});
  svgText(svg, boxX+boxW/2, boxY+TITLE_H/2, mod.name, 'module-name-text');

  /* ── Content inside box ────────────────────── */
  let cy = boxY + TITLE_H + 16;
  function addSection(label, items, cls) {
    if (!items.length) return;
    svgText(svg, boxX+boxW/2, cy, label, 'section-label'); cy+=16;
    items.forEach(txt => { svgText(svg, boxX+boxW/2, cy, txt, cls); cy+=15; });
    cy+=4;
  }
  addSection('PARAMETERS',
    mod.parameters.map(p=>`${p.name} = ${p.default}`), 'param-text');
  addSection('BRANCHES',
    mod.branches.map(b=>b.node_minus?`${b.name}(${b.node_plus},${b.node_minus})`:`${b.name}(${b.node_plus})`),
    'branch-text');
  if (internalNets.length) {
    svgText(svg, boxX+boxW/2, cy, 'INTERNAL NODES', 'section-label'); cy+=15;
    svgText(svg, boxX+boxW/2, cy, internalNets.join(', '), 'net-text'); cy+=15;
    cy+=4;
  }
  addSection('INSTANCES',
    mod.instances.map(i=>`${i.inst_name}: ${i.module_name}`), 'inst-text');

  /* ── Left ports ────────────────────────────── */
  leftPorts.forEach((port, i) => {
    const py = boxY + BOX_PAD + i*PORT_SPACE + PORT_SPACE/2;
    svgLine(svg, boxX-PORT_LEN, py, boxX, py, 'port-wire');
    svgArrow(svg, boxX-PORT_LEN*0.4, py,
      port.direction==='input'?'right':'both',
      port.direction==='input'?'arrow-input':'arrow-inout');
    svgText(svg, boxX-PORT_LEN-LBL_GAP, py, port.name, 'port-label', 'end');
    if (port.discipline && port.discipline!=='electrical')
      svgText(svg, boxX-PORT_LEN/2, py-9, port.discipline, 'discipline-badge');
    svg.appendChild(svgEl('circle',{cx:boxX, cy:py, r:4, class:`port-dot-${port.direction}`}));
  });

  /* ── Right ports ───────────────────────────── */
  rightPorts.forEach((port, i) => {
    const py = boxY + BOX_PAD + i*PORT_SPACE + PORT_SPACE/2;
    svgLine(svg, boxX+boxW, py, boxX+boxW+PORT_LEN, py, 'port-wire');
    svgArrow(svg, boxX+boxW+PORT_LEN*0.6, py,
      port.direction==='output'?'right':'both',
      port.direction==='output'?'arrow-output':'arrow-inout');
    svgText(svg, boxX+boxW+PORT_LEN+LBL_GAP, py, port.name, 'port-label', 'start');
    if (port.discipline && port.discipline!=='electrical')
      svgText(svg, boxX+boxW+PORT_LEN/2, py-9, port.discipline, 'discipline-badge');
    svg.appendChild(svgEl('circle',{cx:boxX+boxW, cy:py, r:4, class:`port-dot-${port.direction}`}));
  });

  /* ── Contributions legend below box ─────────── */
  if (mod.contributions.length) {
    let ly = boxY + boxH + 20;
    svgText(svg, svgW/2, ly, 'Analog Contributions', 'contrib-legend-title'); ly+=16;
    const shown = mod.contributions.slice(0, 5);
    shown.forEach(c => {
      const txt = `${c.nature}(${c.target})  <+  ${c.expression}`;
      svgText(svg, svgW/2, ly, txt, c.nature==='V'?'contrib-v':'contrib-i'); ly+=14;
    });
    if (mod.contributions.length > 5)
      svgText(svg, svgW/2, ly, `… and ${mod.contributions.length-5} more`, 'section-label');
  }
}

/* ─── Syntax-highlighted Code View ──────────────────────────────── */
function renderCode() {
  const src = DATA.source;
  const lines = src.split('\n');
  document.getElementById('line-numbers').textContent =
    lines.map((_,i) => i+1).join('\n');
  document.getElementById('code-content').innerHTML = highlightVA(src);
}

function highlightVA(src) {
  const KEYWORDS = new Set([
    'module','endmodule','analog','begin','end','if','else','for','while',
    'case','casex','casez','endcase','parameter','localparam','real','integer',
    'string','electrical','branch','generate','endgenerate','genvar',
    'assign','initial','always','function','endfunction','task','endtask',
    'specify','endspecify','supply0','supply1',
  ]);
  const DIRS = new Set(['input','output','inout','wire','reg']);

  const e = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

  /* tokeniser: block comments, line comments, strings, numbers, words, other */
  const re = /\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'[^']*'|\b\d[\d.]*(?:[eEpPfFTGMkumnaKt]|[eE][+-]?\d+)?\b|\b[A-Za-z_]\w*\b|<\+|[-+*\/=<>!&|^~%?:.,;()[\]{}\\]|\n|\s+/g;
  let out = '';
  let tok;
  while ((tok = re.exec(src)) !== null) {
    const t = tok[0];
    if (t.startsWith('/*') || t.startsWith('//'))
      out += `<span class="hl-cmt">${e(t)}</span>`;
    else if (t.startsWith('"') || t.startsWith("'"))
      out += `<span class="hl-str">${e(t)}</span>`;
    else if (DIRS.has(t))
      out += `<span class="hl-dir">${e(t)}</span>`;
    else if (KEYWORDS.has(t))
      out += `<span class="hl-kw">${e(t)}</span>`;
    else if (/^\d/.test(t))
      out += `<span class="hl-num">${e(t)}</span>`;
    else if (/^[VI]$/.test(t))
      out += `<span class="hl-nat">${e(t)}</span>`;
    else
      out += e(t);
  }
  return out;
}

/* ─── Details tables ─────────────────────────────────────────────── */
function renderDetails(mod) {
  const grid = document.getElementById('detail-grid');
  grid.innerHTML = '';

  grid.appendChild(buildPortTable(mod.ports));
  grid.appendChild(buildParamTable(mod.parameters));
  if (mod.branches.length || mod.contributions.length)
    grid.appendChild(buildAnalogTable(mod.branches, mod.contributions));
  if (mod.instances.length)
    grid.appendChild(buildInstanceTable(mod.instances));
  if (mod.nets.length) {
    const internal = mod.nets.filter(n => !mod.ports.some(p=>p.name===n));
    if (internal.length) grid.appendChild(buildNetTable(internal));
  }
}

function card(title, body) {
  const d = document.createElement('div'); d.className='detail-card';
  const h = document.createElement('h3'); h.textContent=title; d.appendChild(h);
  d.appendChild(body); return d;
}

function buildPortTable(ports) {
  if (!ports.length) {
    const b=document.createElement('div'); b.className='empty-msg'; b.textContent='No ports declared.';
    return card('Ports',b);
  }
  const t=document.createElement('table');
  t.innerHTML=`<thead><tr><th>#</th><th>Name</th><th>Direction</th><th>Discipline</th></tr></thead>`;
  const tb=document.createElement('tbody');
  ports.forEach((p,i)=>{
    const cls=`badge badge-${p.direction}`;
    tb.innerHTML+=`<tr><td>${i+1}</td><td><strong>${esc(p.name)}</strong></td>
      <td><span class="${cls}">${esc(p.direction)}</span></td>
      <td>${esc(p.discipline)}</td></tr>`;
  });
  t.appendChild(tb);
  return card(`Ports (${ports.length})`, t);
}

function buildParamTable(params) {
  if (!params.length) {
    const b=document.createElement('div'); b.className='empty-msg'; b.textContent='No parameters declared.';
    return card('Parameters',b);
  }
  const t=document.createElement('table');
  t.innerHTML=`<thead><tr><th>#</th><th>Name</th><th>Type</th><th>Default</th></tr></thead>`;
  const tb=document.createElement('tbody');
  params.forEach((p,i)=>{
    tb.innerHTML+=`<tr><td>${i+1}</td><td><strong>${esc(p.name)}</strong></td>
      <td>${esc(p.ptype)}</td><td><code>${esc(p.default)}</code></td></tr>`;
  });
  t.appendChild(tb);
  return card(`Parameters (${params.length})`, t);
}

function buildAnalogTable(branches, contribs) {
  const wrap=document.createElement('div');
  if (branches.length) {
    const t=document.createElement('table');
    t.style.marginBottom='8px';
    t.innerHTML=`<thead><tr><th>Branch</th><th>Node +</th><th>Node −</th></tr></thead>`;
    const tb=document.createElement('tbody');
    branches.forEach(b=>{
      tb.innerHTML+=`<tr><td><strong>${esc(b.name)}</strong></td>
        <td>${esc(b.node_plus)}</td><td>${esc(b.node_minus||'—')}</td></tr>`;
    });
    t.appendChild(tb); wrap.appendChild(t);
  }
  if (contribs.length) {
    const t=document.createElement('table');
    t.innerHTML=`<thead><tr><th>Nature</th><th>Target</th><th>Expression</th></tr></thead>`;
    const tb=document.createElement('tbody');
    contribs.forEach(c=>{
      const cls=`badge badge-${c.nature.toLowerCase()}`;
      tb.innerHTML+=`<tr><td><span class="${cls}">${esc(c.nature)}</span></td>
        <td>${esc(c.target)}</td><td><code>${esc(c.expression)}</code></td></tr>`;
    });
    t.appendChild(tb); wrap.appendChild(t);
  }
  return card(`Analog (${branches.length} branches, ${contribs.length} contributions)`, wrap);
}

function buildInstanceTable(instances) {
  const t=document.createElement('table');
  t.innerHTML=`<thead><tr><th>Instance</th><th>Module</th><th>Connections</th></tr></thead>`;
  const tb=document.createElement('tbody');
  instances.forEach(i=>{
    tb.innerHTML+=`<tr><td><strong>${esc(i.inst_name)}</strong></td>
      <td>${esc(i.module_name)}</td>
      <td>${i.connections.map(esc).join(', ')}</td></tr>`;
  });
  t.appendChild(tb);
  return card(`Instances (${instances.length})`, t);
}

function buildNetTable(nets) {
  const t=document.createElement('table');
  t.innerHTML=`<thead><tr><th>#</th><th>Node Name</th><th>Type</th></tr></thead>`;
  const tb=document.createElement('tbody');
  nets.forEach((n,i)=>{
    tb.innerHTML+=`<tr><td>${i+1}</td><td>${esc(n)}</td><td>electrical</td></tr>`;
  });
  t.appendChild(tb);
  return card(`Internal Nodes (${nets.length})`, t);
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* ─── Footer ─────────────────────────────────────────────────────── */
function renderFooter(mod) {
  document.getElementById('ft-file').textContent    = DATA.filepath || '';
  document.getElementById('ft-modules').textContent = `Modules: ${DATA.modules.length}`;
  document.getElementById('ft-ports').textContent   = `Ports: ${mod.ports.length}`;
  document.getElementById('ft-params').textContent  = `Params: ${mod.parameters.length}`;
  document.getElementById('ft-contribs').textContent= `Contributions: ${mod.contributions.length}`;
}
</script>
</body>
</html>
"""


def render_html(modules: List[VerilogAModule], source: str, filepath: str = '') -> str:
    """Return a self-contained HTML string visualising the given modules."""
    title = Path(filepath).name if filepath else 'Verilog-A'

    payload = {
        'modules': [_module_to_dict(m) for m in modules],
        'source': source,
        'filepath': filepath,
    }
    json_data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

    html = _TEMPLATE
    html = html.replace('__TITLE__', title)
    html = html.replace('__FILEPATH__', filepath.replace("'", "\\'"))
    html = html.replace('__JSON_DATA__', json_data)
    return html
