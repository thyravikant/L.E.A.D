"use strict";
// Land Record Workbench: plain JS, no build step. All OCR text is inserted with
// textContent (never innerHTML), so scanned content cannot inject markup.

const $ = (s) => document.querySelector(s);
const state = { docs: [], doc: null, selected: null, view: "processed", img: null, parcels: null, onlyReview: false };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) n.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined) n.append(k.nodeType ? k : document.createTextNode(String(k)));
  return n;
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}
const jpost = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

let toastTimer;
function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), err ? 7000 : 3000);
}

const statusOf = (r) => r.status;
const colour = (s) => ({ auto_accepted: "#2e8b57", needs_review: "#d68910", verified: "#2a6fb0", edited: "#2a6fb0", rejected: "#c0392b" }[s] || "#888");
const label = (s) => ({ auto_accepted: "auto-accepted", needs_review: "needs review", verified: "verified", edited: "edited", rejected: "rejected" }[s] || s);
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");

// ------------------------------------------------------------------ loading
async function health() {
  try {
    const h = await api("/api/health");
    const p = $("#engine");
    const t = h.tesseract || {};
    if (t.available) { p.textContent = `Tesseract ${t.version} · ${h.ocr_langs}`; p.className = "pill good"; }
    else { p.textContent = "Tesseract not installed (sample only)"; p.className = "pill bad"; p.title = "Install Tesseract to process your own scans. See README."; }
  } catch (e) { $("#engine").textContent = "backend unreachable"; }
}

async function loadDocs(selectId) {
  state.docs = await api("/api/documents");
  renderDocs();
  const pick = selectId || (state.doc && state.doc.id) || (state.docs[0] && state.docs[0].id);
  if (pick) await openDoc(pick); else { state.doc = null; renderAll(); }
}

async function openDoc(id) {
  state.doc = await api("/api/documents/" + id);
  state.selected = state.doc.records.length ? state.doc.records[0].id : null;
  await loadImage();
  renderDocs(); renderAll();
}

function loadImage() {
  return new Promise((resolve) => {
    if (!state.doc) return resolve();
    const img = new Image();
    img.onload = () => { state.img = img; resolve(); };
    img.onerror = () => { state.img = null; resolve(); };
    img.src = `/api/documents/${state.doc.id}/image?kind=${state.view}&t=${Date.now()}`;
  });
}

async function refreshDoc() {
  const keep = state.selected;
  state.doc = await api("/api/documents/" + state.doc.id);
  state.selected = keep;
  state.docs = await api("/api/documents");
  renderDocs(); renderAll();
}

// ---------------------------------------------------------------- rendering
function renderDocs() {
  const ul = $("#docList"); ul.replaceChildren();
  $("#docEmpty").hidden = state.docs.length > 0;
  for (const d of state.docs) {
    const li = el("li", { class: state.doc && state.doc.id === d.id ? "sel" : "", onclick: () => openDoc(d.id) },
      el("b", { title: d.filename }, d.filename),
      el("span", {}, `${d.n_records} rows · ${d.n_review} to review`));
    ul.append(li);
  }
}

function renderAll() { drawScan(); renderMetrics(); renderRecords(); drawMap(); }

function drawScan() {
  const c = $("#scan"), ctx = c.getContext("2d");
  $("#scanEmpty").hidden = !!state.img;
  if (!state.img || !state.doc) { c.width = c.height = 0; return; }
  c.width = state.img.naturalWidth; c.height = state.img.naturalHeight;
  ctx.drawImage(state.img, 0, 0);
  for (const r of state.doc.records) {
    const [x, y, w, h] = r.box, sel = r.id === state.selected;
    ctx.lineWidth = sel ? 5 : 3; ctx.strokeStyle = colour(statusOf(r));
    ctx.strokeRect(x - 4, y - 4, w + 8, h + 8);
    if (sel) { ctx.fillStyle = colour(statusOf(r)) + "22"; ctx.fillRect(x - 4, y - 4, w + 8, h + 8); }
    for (const [k, b] of Object.entries(r.field_boxes || {})) {
      if ((r.field_conf || {})[k] < 0.85) { ctx.lineWidth = 2; ctx.strokeStyle = "#d68910"; ctx.setLineDash([6, 4]); ctx.strokeRect(b[0] - 2, b[1] - 2, b[2] + 4, b[3] + 4); ctx.setLineDash([]); }
    }
  }
}

function renderMetrics() {
  const m = $("#metrics"); m.replaceChildren();
  if (!state.doc) return;
  const x = state.doc.metrics || {};
  const items = [["engine", state.doc.engine], ["size", `${x.width}×${x.height}`], ["skew corrected", `${x.skew_deg}°`],
    ["table rules removed", pct(x.ruling_ink_removed) + " of ink"], ["OCR words", x.words], ["noise", x.noise_level]];
  for (const [k, v] of items) m.append(el("span", {}, k + ": ", el("b", {}, v)));
}

function bar(name, v) {
  return [el("span", {}, name), el("div", { class: "bar" }, el("i", { style: `width:${Math.round((v || 0) * 100)}%` })), el("span", {}, pct(v))];
}

function ruleList(rules) {
  return el("ul", { class: "rules" }, rules.map((r) => {
    const cls = r.score >= 1 ? "pass" : r.score > 0 ? "half" : "fail";
    const mark = r.score >= 1 ? "✓" : r.score > 0 ? "~" : "✗";
    return el("li", {}, el("span", { class: "m " + cls }, mark), el("span", {}, r.name, " ", el("em", {}, "· " + r.detail)));
  }));
}

function renderRecords() {
  const box = $("#records"); box.replaceChildren();
  if (!state.doc) return;
  for (const r of state.doc.records) {
    const open = r.id === state.selected;
    if (state.onlyReview && r.status !== "needs_review" && !open) continue;
    box.append(recordCard(r, open));
  }
}

function recordCard(r, open) {
  const card = el("div", { class: `rec ${r.status}${open ? " sel" : ""}` });
  card.append(el("header", { onclick: () => { state.selected = r.id; renderAll(); } },
    el("span", { class: "title" }, `Khasra ${r.khasra || "?"} · ${r.owner || "—"}`),
    el("span", { class: "badge " + r.status }, label(r.status))));
  if (!open) return card;

  const body = el("div", { class: "body" });
  body.append(el("div", { class: "bars" }, bar("visual c_v", r.c_v), bar("semantic c_s", r.c_s), bar("joint C", r.c_joint)));

  const inputs = {};
  const mk = (key, name, fk) => {
    const inp = el("input", { value: r[key] || "", class: (r.field_conf[fk] ?? 1) < 0.85 ? "low" : "", title: `OCR confidence ${pct(r.field_conf[fk])}` });
    inputs[key] = inp;
    return el("div", {}, el("label", {}, `${name} (${pct(r.field_conf[fk])})`), inp);
  };
  body.append(el("div", { class: "fields" }, mk("khewat", "Khewat", "khewat"), mk("khasra", "Khasra", "khasra"), mk("owner", "Owner", "owner"), mk("area_raw", "Area (K-M-S)", "area")));
  body.append(el("p", { class: "area-note" }, r.area_m2 ? `= ${r.area_m2.toLocaleString(undefined, { maximumFractionDigits: 1 })} m² (${(r.area_m2 / 4046.856).toFixed(3)} acre)` : "Area not understood"));
  body.append(ruleList(r.rules));

  const note = el("input", { placeholder: "optional note for audit log", value: "" });
  const save = el("button", { class: "btn sm", onclick: async () => {
    const payload = {}; for (const k in inputs) payload[k] = inputs[k].value;
    try { await api("/api/records/" + r.id, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); toast("Saved and re-validated"); await refreshDoc(); } catch (e) { toast(e.message, true); }
  } }, "Save + re-validate");
  const act = (path, msg) => async () => { try { await jpost(`/api/records/${r.id}/${path}`, { note: note.value }); toast(msg); await refreshDoc(); } catch (e) { toast(e.message, true); } };
  body.append(el("div", { class: "fields", style: "margin:8px 0" }, note));
  body.append(el("div", { class: "btns" }, save,
    el("button", { class: "btn sm primary", onclick: act("verify", "Marked verified") }, "Verify"),
    el("button", { class: "btn sm danger", onclick: act("reject", "Marked rejected") }, "Reject")));

  const hist = el("div", { class: "hist" });
  body.append(hist);
  api(`/api/records/${r.id}/audit`).then((rows) => {
    if (rows.length) hist.textContent = "History: " + rows.map((a) => `${a.action}${a.detail ? " (" + a.detail + ")" : ""}`).join(" → ");
  }).catch(() => {});
  card.append(body);
  return card;
}

// ---------------------------------------------------------------------- map
async function drawMap() {
  const svg = $("#map"); svg.replaceChildren();
  if (!state.parcels) { try { state.parcels = await api("/api/parcels"); } catch (_) { return; } }
  const feats = state.parcels.features;
  const pts = feats.flatMap((f) => f.geometry.coordinates[0]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const pad = 14, W = 400 - 2 * pad, H = 260 - 2 * pad;
  const k = Math.min(W / (maxX - minX), H / (maxY - minY));
  const X = (x) => pad + (x - minX) * k, Y = (y) => 260 - pad - (y - minY) * k;
  const selRec = state.doc && state.doc.records.find((r) => r.id === state.selected);
  const sel = selRec ? selRec.khasra : null;
  const NS = "http://www.w3.org/2000/svg";
  for (const f of feats) {
    const ring = f.geometry.coordinates[0];
    const poly = document.createElementNS(NS, "polygon");
    poly.setAttribute("points", ring.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" "));
    if (f.properties.khasra_no === sel) poly.setAttribute("class", "sel");
    const t = document.createElementNS(NS, "title"); t.textContent = `Khasra ${f.properties.khasra_no} · ${f.properties.area_m2.toFixed(0)} m²`;
    poly.append(t); svg.append(poly);
    const cx = ring.reduce((a, p) => a + p[0], 0) / ring.length, cy = ring.reduce((a, p) => a + p[1], 0) / ring.length;
    const tx = document.createElementNS(NS, "text"); tx.setAttribute("x", X(cx)); tx.setAttribute("y", Y(cy) + 3); tx.textContent = f.properties.khasra_no; svg.append(tx);
  }
}

// ---------------------------------------------------------------- dashboard
async function loadDash() {
  const [s, hard] = await Promise.all([api("/api/stats"), api("/api/hard-examples")]);
  const cards = [
    ["Documents", s.documents], ["Records", s.records],
    ["Row auto-accept rate", pct(s.record_stp_rate)], ["Fully auto pages", pct(s.page_stp_rate)],
    ["Mean visual c_v", s.avg_visual ?? "–"], ["Mean semantic c_s", s.avg_semantic ?? "–"], ["Corrections logged", s.corrections],
  ];
  const sc = $("#statCards"); sc.replaceChildren(...cards.map(([k, v]) => el("div", { class: "stat" }, el("b", {}, v), el("span", {}, k))));
  const tb = $("#hardTable tbody"); tb.replaceChildren();
  $("#hardEmpty").hidden = hard.length > 0;
  for (const h of hard) tb.append(el("tr", {}, el("td", {}, new Date(h.ts * 1000).toLocaleString()), el("td", {}, "#" + h.doc_id), el("td", {}, h.field),
    el("td", {}, h.old_value), el("td", {}, h.new_value), el("td", {}, pct(h.field_conf))));
}

// ------------------------------------------------------------------ events
async function run(promise, msg) {
  const btns = document.querySelectorAll(".actions .btn"); btns.forEach((b) => (b.disabled = true));
  toast("Processing… (preprocess, OCR, validate)");
  try { const d = await promise; toast(msg); await loadDocs(d.id); } catch (e) { toast(e.message, true); }
  finally { btns.forEach((b) => (b.disabled = false)); }
}

$("#sampleBtn").onclick = () => run(jpost("/api/demo/sample"), "Sample processed");
$("#fileIn").onchange = (e) => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  run(api("/api/documents", { method: "POST", body: fd }), "Document processed");
  e.target.value = "";
};
$("#onlyReview").onchange = (e) => { state.onlyReview = e.target.checked; renderRecords(); };
for (const [id, v] of [["#vProcessed", "processed"], ["#vOriginal", "original"]]) {
  $(id).onclick = async () => {
    state.view = v; $("#vProcessed").classList.toggle("active", v === "processed"); $("#vOriginal").classList.toggle("active", v === "original");
    await loadImage(); drawScan();
  };
}
document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
  $("#review").hidden = t.dataset.tab !== "review"; $("#dash").hidden = t.dataset.tab !== "dash";
  if (t.dataset.tab === "dash") loadDash();
}));
// clicking a row on the scan selects it
$("#scan").addEventListener("click", (e) => {
  if (!state.doc) return;
  const c = e.target, rc = c.getBoundingClientRect();
  const x = (e.clientX - rc.left) * (c.width / rc.width), y = (e.clientY - rc.top) * (c.height / rc.height);
  const hit = state.doc.records.find((r) => x >= r.box[0] && x <= r.box[0] + r.box[2] && y >= r.box[1] - 4 && y <= r.box[1] + r.box[3] + 4);
  if (hit) { state.selected = hit.id; renderAll(); }
});

health();
loadDocs();
