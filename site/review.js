"use strict";
const S = { selected: null, view: "data/processed.png", img: null, only: false };

function loadImg() {
  return new Promise((ok) => { const i = new Image(); i.onload = () => { S.img = i; ok(); }; i.onerror = ok; i.src = S.view; });
}
function renderAll() { drawScan(); renderRecords(); drawMap(); }

function drawScan() {
  const c = $("#scan"), ctx = c.getContext("2d");
  if (!S.img) return;
  c.width = S.img.naturalWidth; c.height = S.img.naturalHeight; ctx.drawImage(S.img, 0, 0);
  for (const r of Store.doc.records) {
    const [x, y, w, h] = r.box, sel = r.id === S.selected;
    ctx.lineWidth = sel ? 5 : 3; ctx.strokeStyle = colour(r.status); ctx.strokeRect(x - 4, y - 4, w + 8, h + 8);
    if (sel) { ctx.fillStyle = colour(r.status) + "22"; ctx.fillRect(x - 4, y - 4, w + 8, h + 8); }
    for (const [k, b] of Object.entries(r.field_boxes || {}))
      if ((r.field_conf || {})[k] < 0.85) { ctx.lineWidth = 2; ctx.strokeStyle = "#d68910"; ctx.setLineDash([6, 4]); ctx.strokeRect(b[0] - 2, b[1] - 2, b[2] + 4, b[3] + 4); ctx.setLineDash([]); }
  }
}
function renderMetrics() {
  const x = Store.doc.metrics || {};
  $("#metrics").replaceChildren(...[["engine", Store.doc.engine], ["size", `${x.width}×${x.height}`], ["skew corrected", `${x.skew_deg}°`], ["table rules removed", pct(x.ruling_ink_removed) + " of ink"], ["OCR words", x.words], ["noise", x.noise_level]]
    .map(([k, v]) => el("span", {}, k + ": ", el("b", {}, v))));
}
const bar = (n, v) => [el("span", {}, n), el("div", { class: "bar" }, el("i", { style: `width:${Math.round((v || 0) * 100)}%` })), el("span", {}, pct(v))];

function renderRecords() {
  const box = $("#records"); box.replaceChildren();
  for (const r of Store.doc.records) {
    const open = r.id === S.selected;
    if (S.only && r.status !== "needs_review" && !open) continue;
    box.append(card(r, open));
  }
}
function card(r, open) {
  const c = el("div", { class: `rec ${r.status}${open ? " sel" : ""}` });
  c.append(el("header", { onclick: () => { S.selected = r.id; renderAll(); } },
    el("span", { class: "title" }, `Khasra ${r.khasra || "?"} · ${r.owner || "—"}`), el("span", { class: "badge " + r.status }, label(r.status))));
  if (!open) return c;
  const b = el("div", { class: "body" }), inputs = {};
  b.append(el("div", { class: "bars" }, bar("visual c_v", r.c_v), bar("semantic c_s", r.c_s), bar("joint C", r.c_joint)));
  const mk = (key, name, fk) => {
    const i = el("input", { value: r[key] || "", class: (r.field_conf[fk] ?? 1) < 0.85 ? "low" : "", title: `OCR confidence ${pct(r.field_conf[fk])}` });
    inputs[key] = i; return el("div", {}, el("label", {}, `${name} (${pct(r.field_conf[fk])})`), i);
  };
  b.append(el("div", { class: "fields" }, mk("khewat", "Khewat", "khewat"), mk("khasra", "Khasra", "khasra"), mk("owner", "Owner", "owner"), mk("area_raw", "Area (K-M-S)", "area")));
  b.append(el("p", { class: "area-note" }, r.area_m2 ? `= ${r.area_m2.toLocaleString(undefined, { maximumFractionDigits: 1 })} m² (${(r.area_m2 / 4046.856).toFixed(3)} acre)` : "Area not understood"));
  b.append(el("ul", { class: "rules" }, r.rules.map((x) => {
    const k = x.score >= 1 ? "pass" : x.score > 0 ? "half" : "fail";
    return el("li", {}, el("span", { class: "m " + k }, x.score >= 1 ? "✓" : x.score > 0 ? "~" : "✗"), el("span", {}, x.name, " ", el("em", {}, "· " + x.detail)));
  })));
  const note = el("input", { placeholder: "optional note for audit log" });
  const act = (fn, msg) => () => { fn(); toast(msg); renderAll(); };
  b.append(el("div", { class: "fields", style: "margin:8px 0" }, note));
  b.append(el("div", { class: "btns" },
    el("button", { class: "btn sm", onclick: act(() => Store.edit(r.id, Object.fromEntries(Object.entries(inputs).map(([k, i]) => [k, i.value]))), "Saved and re-validated") }, "Save + re-validate"),
    el("button", { class: "btn sm primary", onclick: act(() => Store.setStatus(r.id, "verified", note.value), "Marked verified") }, "Verify"),
    el("button", { class: "btn sm danger", onclick: act(() => Store.setStatus(r.id, "rejected", note.value), "Marked rejected") }, "Reject")));
  const h = Store.audit[r.id] || [];
  if (h.length) b.append(el("div", { class: "hist" }, "History: " + h.map((a) => a.action + (a.detail ? ` (${a.detail})` : "")).join(" → ")));
  c.append(b); return c;
}
function drawMap() {
  const svg = $("#map"); svg.replaceChildren();
  const feats = Store.parcels.features, pts = feats.flatMap((f) => f.geometry.coordinates[0]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), minX = Math.min(...xs), minY = Math.min(...ys);
  const pad = 14, k = Math.min((400 - 2 * pad) / (Math.max(...xs) - minX), (260 - 2 * pad) / (Math.max(...ys) - minY));
  const X = (x) => pad + (x - minX) * k, Y = (y) => 260 - pad - (y - minY) * k, NS = "http://www.w3.org/2000/svg";
  const sel = Store.rec(S.selected)?.khasra;
  for (const f of feats) {
    const ring = f.geometry.coordinates[0], poly = document.createElementNS(NS, "polygon");
    poly.setAttribute("points", ring.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" "));
    if (f.properties.khasra_no === sel) poly.setAttribute("class", "sel");
    const t = document.createElementNS(NS, "title"); t.textContent = `Khasra ${f.properties.khasra_no} · ${f.properties.area_m2.toFixed(0)} m²`; poly.append(t); svg.append(poly);
    const cx = ring.reduce((a, p) => a + p[0], 0) / ring.length, cy = ring.reduce((a, p) => a + p[1], 0) / ring.length;
    const tx = document.createElementNS(NS, "text"); tx.setAttribute("x", X(cx)); tx.setAttribute("y", Y(cy) + 3); tx.textContent = f.properties.khasra_no; svg.append(tx);
  }
}
boot("review", async () => {
  const rid = +new URLSearchParams(location.search).get("rid");
  S.selected = Store.rec(rid) ? rid : Store.doc.records[0]?.id;
  renderMetrics(); await loadImg(); renderAll();
  $("#onlyReview").onchange = (e) => { S.only = e.target.checked; renderRecords(); };
  for (const [id, src] of [["#vP", "data/processed.png"], ["#vO", "data/original.jpg"]])
    $(id).onclick = async () => { S.view = src; $("#vP").classList.toggle("active", id === "#vP"); $("#vO").classList.toggle("active", id === "#vO"); await loadImg(); drawScan(); };
  $("#scan").addEventListener("click", (e) => {
    const c = e.target, rc = c.getBoundingClientRect(), x = (e.clientX - rc.left) * (c.width / rc.width), y = (e.clientY - rc.top) * (c.height / rc.height);
    const hit = Store.doc.records.find((r) => x >= r.box[0] && x <= r.box[0] + r.box[2] && y >= r.box[1] - 4 && y <= r.box[1] + r.box[3] + 4);
    if (hit) { S.selected = hit.id; renderAll(); }
  });
});
