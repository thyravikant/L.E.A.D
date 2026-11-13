"use strict";
// Shared code: store (localStorage), client-side port of the Python validator, nav.
const $ = (s) => document.querySelector(s);
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
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + "%");
const colour = (s) => ({ auto_accepted: "#2e8b57", needs_review: "#d68910", verified: "#2a6fb0", edited: "#2a6fb0", rejected: "#c0392b" }[s] || "#888");
const label = (s) => ({ auto_accepted: "auto-accepted", needs_review: "needs review", verified: "verified", edited: "edited", rejected: "rejected" }[s] || s);
let toastTimer;
function toast(msg, err = false) {
  let t = $("#toast"); if (!t) { t = el("div", { id: "toast", class: "toast" }); document.body.append(t); }
  t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 3000);
}

// ---- config + units (mirrors app/config.py, app/units.py)
const CFG = { ALPHA: 0.5, AUTO: 0.80, FLOOR: 0.5, FC_OK: 0.85, FC_LOW: 0.70, TOL: 0.02, WARN: 0.10 };
const SARSAHI = 5.5 ** 2 * 0.09290304, MARLA = 9 * SARSAHI, KANAL = 20 * MARLA;
const UF = { sarsahi: SARSAHI, marla: MARLA, kanal: KANAL, killa: 8 * KANAL, hectare: 1e4, sqm: 1, sqft: 0.09290304 };
const ALIAS = { kanal: "kanal", k: "kanal", kn: "kanal", marla: "marla", m: "marla", sarsahi: "sarsahi", s: "sarsahi", sar: "sarsahi",
  killa: "killa", acre: "killa", acres: "killa", ha: "hectare", hectare: "hectare", sqm: "sqm", m2: "sqm", sqft: "sqft" };
function parseArea(text) {
  if (!text) return null;
  const t = text.trim().replace(/[‐-―−]/g, "-");
  const m = t.match(/^\s*(\d+)\s*-\s*(\d+)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*$/);
  if (m) {
    const [k, ma, s] = [+m[1], +m[2], +(m[3] || 0)];
    if (ma >= 20 || s >= 9) return null;
    return +(k * KANAL + ma * MARLA + s * SARSAHI).toFixed(3);
  }
  let sum = 0, any = false;
  for (const [, n, w] of t.matchAll(/(\d+(?:\.\d+)?)\s*(\p{L}+)/gu)) {
    const u = ALIAS[w.toLowerCase()]; if (u) { sum += +n * UF[u]; any = true; }
  }
  return any ? +sum.toFixed(3) : null;
}

// ---- validation (mirrors app/validate.py)
function validate(r, index, docKhasras) {
  const rules = [], add = (name, weight, score, detail, hard = false) => rules.push({ name, weight, score, detail, hard });
  const khasra = (r.khasra || "").trim(), owner = (r.owner || "").trim(), a = r.area_m2, fmt = (x) => x.toLocaleString(undefined, { maximumFractionDigits: 1 });
  const okF = /^\d{1,5}(?:\/\d{1,3})*$/.test(khasra);
  add("Khasra format", 1, okF ? 1 : 0, okF ? "digits with optional /sub-number" : "unexpected Khasra pattern");
  const p = index[khasra] || null;
  add("Khasra exists in cadastral layer", 3, p ? 1 : 0, p ? `parcel found in ${p.village}` : "no matching parcel polygon", true);
  add("Area parsed to SI units", 2, a ? 1 : 0, a ? `${fmt(a)} m²` : "area text not understood");
  if (p && a) {
    const rel = Math.abs(a - p.area_m2) / p.area_m2, d = `ledger ${fmt(a)} vs GIS ${fmt(p.area_m2)} m² (${(rel * 100).toFixed(1)}% apart)`;
    if (rel <= CFG.TOL) add("Ledger area matches GIS polygon", 3, 1, d);
    else if (rel <= CFG.WARN) add("Ledger area matches GIS polygon", 3, 0.5, d + ": check");
    else add("Ledger area matches GIS polygon", 3, 0, "MISMATCH: " + d);
  } else add("Ledger area matches GIS polygon", 3, 0, "cannot compare (missing parcel or area)");
  const okO = owner.length >= 3 && !/\d/.test(owner);
  add("Owner name plausible", 1, okO ? 1 : 0, okO ? "alphabetic name" : "empty or contains digits");
  const fc = r.field_conf || {}, keys = Object.keys(fc);
  if (keys.length) {
    const w = keys.reduce((x, y) => (fc[y] < fc[x] ? y : x)), low = fc[w];
    add("OCR confidence of every field", 2, low >= CFG.FC_OK ? 1 : low >= CFG.FC_LOW ? 0.4 : 0, `weakest field: ${w} at ${pct(low)}`);
  }
  const dup = docKhasras.filter((k) => k === khasra).length > 1;
  add("Khasra unique in document", 1, dup ? 0 : 1, dup ? "duplicate Khasra in this document" : "unique");
  const tot = rules.reduce((s, x) => s + x.weight, 0);
  let c_s = rules.reduce((s, x) => s + x.weight * x.score, 0) / tot;
  if (rules.some((x) => x.hard && x.score === 0)) c_s = 0;
  return { rules, c_s: +c_s.toFixed(4), parcel: p };
}
const joint = (cv, cs) => (cs <= 0 || cv <= 0 ? 0 : +(cv ** CFG.ALPHA * cs ** (1 - CFG.ALPHA)).toFixed(4));
const route = (c, rules) => (c >= CFG.AUTO && Math.min(...rules.map((x) => x.score)) >= CFG.FLOOR ? "auto_accepted" : "needs_review");

// ---- store: ships a pre-processed sample; edits persist in this browser only
const KEY = "lr_demo_v1", FIELD_KEY = { khewat: "khewat", khasra: "khasra", owner: "owner", area_raw: "area" };
const Store = {
  async init() {
    const get = async (u) => (await fetch(u)).json();
    this.parcels = await get("data/parcels.json");
    this.index = Object.fromEntries(this.parcels.features.map((f) => [f.properties.khasra_no, f.properties]));
    let s = null; try { s = JSON.parse(localStorage.getItem(KEY)); } catch (_) {}
    if (!s) {
      const doc = await get("data/doc.json"); s = { doc, corrections: [], audit: {} };
      doc.records.forEach((r) => (s.audit[r.id] = [{ action: "extracted", detail: `route=${r.route} C=${r.c_joint}`, ts: Date.now() }]));
    }
    Object.assign(this, s);
  },
  save() { try { localStorage.setItem(KEY, JSON.stringify({ doc: this.doc, corrections: this.corrections, audit: this.audit })); } catch (_) {} },
  reset() { try { localStorage.removeItem(KEY); } catch (_) {} location.reload(); },
  rec: (id) => Store.doc.records.find((r) => r.id === id),
  log(id, action, detail = "") { (this.audit[id] ||= []).push({ action, detail, ts: Date.now() }); },
  edit(id, ch) {
    const r = this.rec(id), changed = Object.entries(ch).filter(([f, v]) => v.trim() !== r[f]);
    if (!changed.length) return;
    for (const [f, v] of changed) {
      const k = FIELD_KEY[f];
      this.corrections.unshift({ doc_id: r.doc_id, record_id: id, field: k, old_value: r[f], new_value: v.trim(), field_conf: r.field_conf[k], ts: Date.now() });
      this.log(id, "edited", `${f}: '${r[f]}' -> '${v.trim()}'`);
      r[f] = v.trim(); r.field_conf[k] = 1;
    }
    r.area_m2 = parseArea(r.area_raw);
    const res = validate(r, this.index, this.doc.records.map((x) => x.khasra));
    r.rules = res.rules; r.c_s = res.c_s; r.parcel = res.parcel; r.c_joint = joint(r.c_v, res.c_s);
    r.route = route(r.c_joint, r.rules); r.status = "edited"; this.save();
  },
  setStatus(id, status, note) { const r = this.rec(id); r.status = status; r.note = note; this.log(id, status, note); this.save(); },
  stats() {
    const R = this.doc.records, n = R.length, by = {};
    R.forEach((r) => (by[r.status] = (by[r.status] || 0) + 1));
    const avg = (k) => (n ? R.reduce((s, r) => s + r[k], 0) / n : null);
    return { records: n, by, auto: n ? (by.auto_accepted || 0) / n : null, cv: avg("c_v"), cs: avg("c_s"), cj: avg("c_joint"), corrections: this.corrections.length };
  },
};

function nav(page) {
  const links = [
    ["index.html", "Overview / Proposal", "proposal"],
    ["workbench.html", "Dashboard", "dash"],
    ["review.html", "Review", "review"],
    ["search.html", "Search records", "search"]
  ];
  document.body.prepend(el("header", {},
    el("div", { class: "brand" }, el("h1", {}, "Land Record Workbench"), el("span", { class: "sub" }, "SIH 26018 prototype · digitize, validate, review")),
    el("nav", {}, links.map(([h, t, p]) => el("a", { href: h, class: p === page ? "active" : "" }, t))),
    el("div", { class: "actions" }, el("span", { class: "pill", title: "Pre-processed sample; edits are saved in this browser only." }, "Static demo"),
      el("button", { class: "btn sm", onclick: () => confirm("Discard all edits and reload the original sample?") && Store.reset() }, "Reset demo"))));
}
async function boot(page, fn) { nav(page); try { await Store.init(); fn(); } catch (e) { document.body.append(el("p", { class: "center muted" }, "Failed to load data: " + e.message)); } }
