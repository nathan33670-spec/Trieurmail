"use strict";

/* =====================================================================
   Trieurmail — interface (vanilla JS, aucune dépendance, aucun build)
   ===================================================================== */

const ICONS = {
  mail: '<path d="M4 6h16v12H4z"/><path d="m4 7 8 6 8-6"/>',
  home: '<path d="M4 11 12 4l8 7"/><path d="M6 10v10h12V10"/>',
  flame: '<path d="M12 3s5 4.5 5 9.5a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5 0 2 1 3 2 3 0-3 1-6 1-8z"/>',
  inbox: '<path d="M4 13h4l2 3h4l2-3h4"/><path d="M5 5h14l1 8v6H4v-6z"/>',
  folders: '<path d="M3 7h6l2 2h10v10H3z"/><path d="M3 7V5h6l2 2"/>',
  folder: '<path d="M3 6h6l2 2h10v11H3z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  reply: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 6 6v4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.8-4M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.8 4M20 20v-4h-4"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  calendar: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  send: '<path d="M21 3 10 14"/><path d="m21 3-7 18-4-7-7-4z"/>',
  save: '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5h10"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeoff: '<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3 3.8M6.6 6.6A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 4.4-1"/>',
  image: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 8"/>',
  paperclip: '<path d="m20 12-8 8a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"/>',
  arrowLeft: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  palette: '<path d="M12 3a9 9 0 1 0 0 18c1 0 1.5-.8 1.5-1.5 0-1.2-1-1.3-1-2.5 0-.8.7-1.5 1.5-1.5H17a4 4 0 0 0 4-4c0-4.7-4-8.5-9-8.5z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="15" cy="7" r="1"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>',
  doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
  wand: '<path d="m15 4 5 5L9 20l-5-5z"/><path d="M13 6l5 5M4 4l1.5 1.5M8 2v2M2 8h2"/>',
  filter: '<path d="M3 5h18l-7 8v6l-4 2v-8z"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".5"/>',
};
const icon = (name, cls = "") => `<svg class="icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const fmtNum = (n) => new Intl.NumberFormat("fr-FR").format(n || 0);
const plural = (n, word) => `${fmtNum(n)} ${word}${n > 1 ? "s" : ""}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }

const S = {
  state: null,
  folders: [],
  timeline: null,
  route: "home",
  inbox: { items: [], total: 0, q: "", unread: false, selected: null, offset: 0, syncing: false },
  priority: null,
  plan: null,
  digest: null,
  showLowPrio: false,
};

/* ---------- API ---------- */
async function api(path, { method = "GET", body, signal } = {}) {
  const opts = { method, headers: {}, signal };
  if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch { /* vide */ }
  if (!res.ok) {
    let detail = data && data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join(", ");
    throw new Error(detail || `Erreur ${res.status}`);
  }
  return data;
}

/* ---------- Dates ---------- */
const DF = {
  time: new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }),
  wd: new Intl.DateTimeFormat("fr-FR", { weekday: "short" }),
  dm: new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" }),
  dmy: new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" }),
  long: new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }),
  my: new Intl.DateTimeFormat("fr-FR", { month: "short", year: "numeric" }),
  dmyl: new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" }),
};
function shortDate(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return DF.time.format(d);
  const diff = (now - d) / 86400000;
  if (diff < 6) return DF.wd.format(d);
  if (d.getFullYear() === now.getFullYear()) return DF.dm.format(d);
  return DF.dmy.format(d);
}
function ago(ts) {
  if (!ts) return "jamais";
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.round(s / 3600)} h`;
  return `il y a ${Math.round(s / 86400)} j`;
}
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseDay = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

/* ---------- Avatars ---------- */
function avatar(name, addr, cls = "") {
  const label = (name || addr || "?").replace(/[^\p{L}\p{N} ]/gu, "").trim();
  const parts = label.split(/\s+/).filter(Boolean);
  const initials = ((parts[0] || "?")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  let h = 0;
  for (const c of addr || name || "") h = (h * 31 + c.charCodeAt(0)) % 360;
  return `<div class="avatar ${cls}" style="background:hsl(${h} 55% 52%)">${esc(initials)}</div>`;
}

/* ---------- Notifications ---------- */
function toast(message, type = "info", ms = 3800) {
  const t = el(`<div class="toast ${type}">${type === "error" ? icon("alert") : type === "success" ? icon("check") : icon("bolt")}<div>${esc(message)}</div></div>`);
  $("#dock").appendChild(t);
  setTimeout(() => { t.style.transition = "opacity .3s"; t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, ms);
}
const fail = (e) => toast(e.message || String(e), "error", 6000);

const JOB_TITLES = { sync: "Synchronisation", priority: "Analyse des priorités", digest: "Synthèse globale", briefs: "Résumés express", sort: "Tri de la boîte mail" };

async function runJob(startPromise, { title, quiet = false } = {}) {
  let job = await startPromise;
  let card = null;
  if (!quiet) {
    card = el(`<div class="job"><div class="row"><span class="title">${esc(title || JOB_TITLES[job.kind] || "Tâche")}</span>
      <button class="btn ghost sm icon-only" title="Annuler">${icon("x")}</button></div>
      <div class="msg"></div><div class="progress"><div style="width:0%"></div></div></div>`);
    $("button", card).onclick = () => api(`/api/jobs/${job.id}/cancel`, { method: "POST" }).catch(() => {});
    $("#dock").appendChild(card);
  }
  try {
    while (job.status === "running") {
      if (card) {
        $(".msg", card).textContent = job.message;
        $(".progress div", card).style.width = `${Math.max(3, job.progress * 100)}%`;
        $(".progress", card).classList.toggle("indeterminate", job.progress === 0);
      }
      await sleep(600);
      job = await api(`/api/jobs/${job.id}`);
    }
  } finally {
    if (card) card.remove();
    refreshState();
  }
  if (job.status === "error") throw new Error(job.error);
  if (job.status === "cancelled") throw new Error("Tâche annulée");
  return job.result;
}

function modal({ title, body = "", confirm = "Confirmer", cancel = "Annuler", danger = false }) {
  return new Promise((resolve) => {
    const bd = el(`<div class="backdrop"><div class="modal" role="dialog">
      <div class="modal-body"><h3>${esc(title)}</h3><div class="muted">${body}</div></div>
      <div class="modal-foot"><button class="btn" data-a="0">${esc(cancel)}</button>
      <button class="btn ${danger ? "danger solid" : "primary"}" data-a="1">${esc(confirm)}</button></div></div></div>`);
    const close = (v) => { bd.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
    const onKey = (e) => { if (e.key === "Escape") close(false); if (e.key === "Enter") close(true); };
    bd.addEventListener("click", (e) => { if (e.target === bd) close(false); const a = e.target.closest("[data-a]"); if (a) close(a.dataset.a === "1"); });
    document.addEventListener("keydown", onKey);
    document.body.appendChild(bd);
    $("[data-a='1']", bd).focus();
  });
}

function setBusy(btn, busy, label) {
  if (!btn) return;
  if (busy) { btn.dataset.html = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>${label ? esc(label) : ""}`; }
  else if (btn.dataset.html) { btn.innerHTML = btn.dataset.html; btn.disabled = false; }
}

/* ---------- Markdown minimal (échappé) ---------- */
function md(src) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|\W)\*(?!\s)(.+?)\*(?=\W|$)/g, "$1<em>$2</em>").replace(/`(.+?)`/g, "<code>$1</code>");
  const out = [];
  let list = false;
  for (const raw of String(src || "").split("\n")) {
    const line = raw.trimEnd();
    const li = line.match(/^\s*[-*•]\s+(.*)/);
    if (li) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(li[1])}</li>`); continue; }
    if (list) { out.push("</ul>"); list = false; }
    const hd = line.match(/^(#{1,4})\s+(.*)/);
    if (hd) {
      const t = hd[2];
      const ic = /priorit|traiter/i.test(t) ? "flame" : /savoir/i.test(t) ? "eye" : /attendre/i.test(t) ? "clock" : "list";
      out.push(`<h${hd[1].length < 3 ? 2 : 3}>${icon(ic)}${inline(t)}</h${hd[1].length < 3 ? 2 : 3}>`);
    } else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (list) out.push("</ul>");
  return out.join("");
}

/* =====================================================================
   État global, barre latérale
   ===================================================================== */
const NAV = [
  ["home", "home", "Accueil"],
  ["priority", "flame", "Prioritaires"],
  ["inbox", "inbox", "Boîte mail"],
  ["sort", "folders", "Trier l'historique"],
  ["settings", "settings", "Réglages"],
];

async function refreshState() {
  try { S.state = await api("/api/state"); } catch (e) { return; }
  applyTheme(S.state.settings.theme);
  renderSidebar();
}

function applyTheme(theme) {
  if (theme === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = theme;
}

function renderSidebar() {
  const urgent = S.priority ? S.priority.items.filter((i) => i.tier === "urgent" || i.tier === "important").length : 0;
  $("#nav").innerHTML = NAV.map(([id, ic, label]) => `<a class="nav-item ${S.route === id ? "active" : ""}" href="#/${id}">${icon(ic)}<span>${label}</span>${id === "priority" && urgent ? `<span class="badge red">${urgent}</span>` : ""}</a>`).join("");
  const st = S.state;
  if (!st) return;
  const llm = st.settings.llm;
  $("#llm-status").innerHTML = `<div class="row"><span class="row"><span class="dot ${st.configured.llm ? (st.usage.last_error && st.usage.errors ? "ko" : "ok") : "ko"}"></span><b>IA locale</b></span>
    <a href="#/settings" class="small">Régler</a></div>
    <div class="faint small ellipsis" style="margin-top:4px" title="${esc(llm.base_url)}">${esc(llm.model || "aucun modèle")}</div>`;
  const u = st.usage;
  $("#usage-status").innerHTML = `<div class="row"><b>Consommation IA</b></div>
    <div class="small muted" style="margin-top:4px">${fmtNum(u.calls)} appels · ${fmtNum(u.cache_hits)} évités (cache)</div>
    <div class="small faint">${fmtNum(u.prompt_tokens + u.completion_tokens)} tokens · ${u.seconds.toFixed(0)} s de calcul</div>`;
}

/* =====================================================================
   Périmètre : dossiers + timeline
   ===================================================================== */
const scope = () => S.state.settings.scope;

function renderScopebar() {
  const sc = scope();
  const folders = sc.folders || ["INBOX"];
  const folderLabel = folders.length === 1 ? folderName(folders[0]) : `${folderName(folders[0])} +${folders.length - 1}`;
  const presets = [["7", "7 j"], ["30", "30 j"], ["90", "3 mois"], ["182", "6 mois"], ["365", "1 an"], ["all", "Tout"]];
  const active = activePreset();
  $("#scopebar").innerHTML = `
    <div class="scopebar-top">
      <span class="scope-label row">${icon("target")}Périmètre</span>
      <button class="chip" id="folders-btn">${icon("folder")}${esc(folderLabel)}${icon("chevronDown")}</button>
      <div class="row wrap">${presets.map(([v, l]) => `<button class="chip ${active === v ? "active" : ""}" data-preset="${v}">${l}</button>`).join("")}</div>
      <span class="row small"><input type="date" class="input" id="since" style="height:28px;width:140px" value="${sc.since || ""}" title="Début">
      <span class="faint">→</span><input type="date" class="input" id="until" style="height:28px;width:140px" value="${sc.until || ""}" title="Fin"></span>
      <span class="spacer"></span>
      <span class="scope-summary small" id="scope-summary"></span>
    </div>
    <div class="timeline" id="timeline"><div class="timeline-empty"><span class="spinner"></span></div></div>`;
  $("#folders-btn").onclick = (e) => openFolderPicker(e.currentTarget);
  $$("[data-preset]").forEach((b) => (b.onclick = () => applyPreset(b.dataset.preset)));
  $("#since").onchange = (e) => setScope({ since: e.target.value || null });
  $("#until").onchange = (e) => setScope({ until: e.target.value || null });
  drawTimeline();
}

function folderName(name) {
  if (name === "INBOX") return "Boîte de réception";
  return name;
}

function activePreset() {
  const sc = scope();
  if (!sc.since && !sc.until) return "all";
  if (sc.until) return null;
  const days = Math.round((Date.now() - parseDay(sc.since)) / 86400000);
  for (const d of [7, 30, 90, 182, 365]) if (Math.abs(days - d) <= 1) return String(d);
  return null;
}

function applyPreset(p) {
  if (p === "all") return setScope({ since: null, until: null });
  const d = new Date(); d.setDate(d.getDate() - Number(p));
  setScope({ since: isoDay(d), until: null });
}

async function setScope(patch) {
  const sc = { ...scope(), ...patch };
  try {
    S.state.settings.scope = await api("/api/scope", { method: "PUT", body: sc });
  } catch (e) { return fail(e); }
  const foldersChanged = patch.folders !== undefined;
  renderScopebar();
  if (foldersChanged) loadTimeline();
  S.priority = null;
  onScopeChange();
}

async function loadTimeline(rebuild = false) {
  try {
    const qs = scope().folders.map((f) => `folders=${enc(f)}`).join("&");
    S.timeline = await api(`/api/timeline?${qs}${rebuild ? "&rebuild=true" : ""}`);
  } catch (e) {
    S.timeline = { buckets: [], error: e.message };
  }
  drawTimeline();
}

function selectionIndices() {
  const b = S.timeline.buckets, sc = scope();
  let i0 = 0, i1 = b.length - 1;
  if (sc.since) { i0 = b.findIndex((x) => x.end >= sc.since); if (i0 < 0) i0 = b.length - 1; }
  if (sc.until) { for (let i = b.length - 1; i >= 0; i--) if (b[i].start <= sc.until) { i1 = i; break; } }
  return [Math.min(i0, i1), Math.max(i0, i1)];
}

function drawTimeline(dragSel) {
  const box = $("#timeline");
  if (!box) return;
  const tl = S.timeline;
  if (!tl) return;
  if (!tl.buckets.length) {
    box.innerHTML = `<div class="timeline-empty">${tl.error ? esc(tl.error) : "Aucun email dans ces dossiers"}</div>`;
    $("#scope-summary").textContent = "";
    return;
  }
  const b = tl.buckets, n = b.length, W = n * 10, H = 46;
  const max = Math.max(...b.map((x) => x.count), 1);
  const [i0, i1] = dragSel || selectionIndices();
  const bars = b.map((x, i) => {
    const h = x.count ? Math.max(2, Math.sqrt(x.count / max) * (H - 4)) : 0;
    return `<rect class="bar ${i >= i0 && i <= i1 ? "in" : ""}" x="${i * 10 + 1}" y="${H - h}" width="8" height="${h}" rx="1.5"/>`;
  }).join("");
  const axisFmt = (s) => (tl.granularity === "month" ? DF.my : DF.dmyl).format(parseDay(s));
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <rect class="sel" x="${i0 * 10}" y="0" width="${(i1 - i0 + 1) * 10}" height="${H}"/>${bars}
      <rect class="handle" x="${i0 * 10}" y="0" width="${Math.max(1, W / 400)}" height="${H}"/>
      <rect class="handle" x="${(i1 + 1) * 10 - Math.max(1, W / 400)}" y="0" width="${Math.max(1, W / 400)}" height="${H}"/></svg>
    <div class="timeline-axis"><span>${axisFmt(b[0].start)}</span><span>${axisFmt(b[Math.floor(n / 2)].start)}</span><span>${axisFmt(b[n - 1].start)}</span></div>`;
  const count = b.slice(i0, i1 + 1).reduce((a, x) => a + x.count, 0);
  const sc = scope();
  const from = sc.since ? DF.dmyl.format(parseDay(sc.since)) : "le début";
  const to = sc.until ? DF.dmyl.format(parseDay(sc.until)) : "aujourd'hui";
  $("#scope-summary").innerHTML = `De <b>${from}</b> à <b>${to}</b> · ≈ ${fmtNum(count)} emails`;
  bindTimeline(box, b);
}

function bindTimeline(box, b) {
  const svg = $("svg", box);
  const idxAt = (x) => { const r = svg.getBoundingClientRect(); return Math.max(0, Math.min(b.length - 1, Math.floor(((x - r.left) / r.width) * b.length))); };
  let tip = null, start = null, cur = null;
  const showTip = (e) => {
    const i = idxAt(e.clientX), x = b[i];
    const label = S.timeline.granularity === "month" ? DF.my.format(parseDay(x.start)) : `${DF.dm.format(parseDay(x.start))}${x.start !== x.end ? " – " + DF.dm.format(parseDay(x.end)) : ""}`;
    if (!tip) { tip = el('<div class="tooltip"></div>'); document.body.appendChild(tip); }
    tip.textContent = `${label} · ${fmtNum(x.count)} emails`;
    tip.style.left = `${e.clientX}px`; tip.style.top = `${svg.getBoundingClientRect().top}px`;
  };
  svg.onpointermove = (e) => {
    showTip(e);
    if (start === null) return;
    cur = idxAt(e.clientX);
    drawSel(Math.min(start, cur), Math.max(start, cur));
  };
  svg.onpointerleave = () => { if (tip) { tip.remove(); tip = null; } };
  svg.onpointerdown = (e) => { svg.setPointerCapture(e.pointerId); start = cur = idxAt(e.clientX); drawSel(start, start); };
  svg.onpointerup = () => {
    if (start === null) return;
    const a = Math.min(start, cur), z = Math.max(start, cur);
    start = null;
    if (tip) { tip.remove(); tip = null; }
    const since = a === 0 ? null : b[a].start;
    const until = z === b.length - 1 ? null : b[z].end;
    setScope({ since, until });
  };
  const drawSel = (a, z) => {
    $$(".bar", svg).forEach((r, i) => r.classList.toggle("in", i >= a && i <= z));
    const sel = $(".sel", svg); sel.setAttribute("x", a * 10); sel.setAttribute("width", (z - a + 1) * 10);
    const hs = $$(".handle", svg), w = Number(hs[0].getAttribute("width"));
    hs[0].setAttribute("x", a * 10); hs[1].setAttribute("x", (z + 1) * 10 - w);
  };
}

async function openFolderPicker(anchor) {
  if ($(".popover")) { $(".popover").remove(); return; }
  if (!S.folders.length) { try { S.folders = await api("/api/folders"); } catch (e) { return fail(e); } }
  const sel = new Set(scope().folders);
  const r = anchor.getBoundingClientRect();
  const specialLabel = { sent: "envoyés", drafts: "brouillons", trash: "corbeille", junk: "spam", archive: "archives", all: "tous" };
  const pop = el(`<div class="popover" style="left:${r.left}px;top:${r.bottom + 6}px">
    <div class="small faint" style="padding:4px 9px 6px">Dossiers analysés</div>
    ${S.folders.filter((f) => f.selectable).map((f) => `<label class="opt"><input type="checkbox" value="${esc(f.name)}" ${sel.has(f.name) ? "checked" : ""}>
      ${icon("folder")}<span class="grow ellipsis">${esc(folderName(f.name))}</span>${f.special ? `<span class="badge">${specialLabel[f.special] || f.special}</span>` : ""}</label>`).join("")}
    <div class="row" style="padding:8px 4px 2px"><span class="spacer"></span><button class="btn sm primary">Appliquer</button></div></div>`);
  document.body.appendChild(pop);
  const close = (e) => { if (!pop.contains(e.target) && e.target !== anchor) { pop.remove(); document.removeEventListener("mousedown", close); } };
  setTimeout(() => document.addEventListener("mousedown", close));
  $("button", pop).onclick = () => {
    const folders = $$("input:checked", pop).map((i) => i.value);
    if (!folders.length) return toast("Sélectionnez au moins un dossier", "error");
    pop.remove(); document.removeEventListener("mousedown", close);
    setScope({ folders });
  };
}

function onScopeChange() {
  const r = S.route;
  if (r === "inbox") { S.inbox.offset = 0; loadInbox(true); }
  else if (r === "home") renderHome();
  else if (r === "priority") renderPriority();
  else if (r === "sort") renderSort();
}

/* =====================================================================
   Routeur
   ===================================================================== */
const ROUTES = { home: renderHome, priority: renderPriority, inbox: renderInbox, sort: renderSort, settings: renderSettings };

function route() {
  const name = (location.hash.replace(/^#\/?/, "").split("?")[0]) || "home";
  S.route = ROUTES[name] ? name : "home";
  closeDrawer();
  const view = $("#view");
  view.className = "view";
  view.scrollTop = 0;
  $("#scopebar").classList.toggle("hidden", S.route === "settings");
  renderSidebar();
  ROUTES[S.route]();
}

/* =====================================================================
   Accueil
   ===================================================================== */
async function renderHome() {
  const st = S.state;
  const view = $("#view");
  const needsSetup = !st.configured.llm || !st.configured.mail;
  view.innerHTML = `
    <div class="page-head"><div><h1>Bonjour${st.settings.profile.full_name ? " " + esc(st.settings.profile.full_name.split(" ")[0]) : ""} 👋</h1>
      <p>Votre assistant mail, propulsé par votre IA locale.${st.settings.mail.provider === "demo" ? ' <span class="badge orange">Mode démo</span>' : ""}</p></div></div>
    ${needsSetup ? onboardingHtml() : ""}
    <div class="kpis">
      ${kpi("inbox", "Non lus (période)", '<span class="skeleton" style="width:60px;height:26px;display:block"></span>', "", "k-unread")}
      ${kpi("flame", "Prioritaires", S.priority ? fmtNum(S.priority.items.filter((i) => i.tier === "urgent" || i.tier === "important").length) : "—", S.priority ? `analysés ${ago(S.priority.computed_at)}` : "lancer une analyse", "k-prio")}
      ${kpi("mail", "Emails (période)", '<span class="skeleton" style="width:60px;height:26px;display:block"></span>', "", "k-total")}
      ${kpi("bolt", "Appels IA évités", fmtNum(st.usage.cache_hits), `${fmtNum(st.cache.insights)} analyses en cache`, "k-cache")}
    </div>
    <div class="actions-grid">
      ${actionCard("go-prio", "flame", "red", "Mes priorités", "Les non lus qui méritent votre attention, classés par l'IA.")}
      ${actionCard("go-digest", "sparkles", "violet", "Synthèse des non lus", "Un résumé global de ce qui vous attend.")}
      ${actionCard("go-sort", "folders", "green", "Trier l'historique", "L'IA propose une arborescence, vous validez.")}
      ${actionCard("go-inbox", "reply", "blue", "Lire & répondre", "Résumés, ouverture et brouillons de réponse.")}
    </div>
    <div id="digest-zone">${S.digest ? digestCard(S.digest) : ""}</div>`;
  if (needsSetup) bindOnboarding();
  $("#go-prio").onclick = () => { location.hash = "#/priority"; setTimeout(runPriority, 50); };
  $("#go-sort").onclick = () => (location.hash = "#/sort");
  $("#go-inbox").onclick = () => (location.hash = "#/inbox");
  $("#go-digest").onclick = () => runDigest({ unread_only: true }, "Synthèse des non lus");
  bindDigest();
  try {
    const [u, t] = await Promise.all([api("/api/messages?unread=true&limit=1"), api("/api/messages?limit=1")]);
    if ($("#k-unread")) {
      $("#k-unread .value").textContent = fmtNum(u.total);
      $("#k-total .value").textContent = fmtNum(t.total);
      $("#k-unread .sub").textContent = t.total ? "depuis le cache local" : "synchronisez la boîte";
    }
  } catch { /* ignore */ }
  if (!S.priority) {
    S.priority = await api("/api/priority").catch(() => null);
    if (S.priority && !S.priority.computed_at) S.priority = null;
    if (S.priority && $("#k-prio")) {
      $("#k-prio .value").textContent = fmtNum(S.priority.items.filter((i) => i.tier === "urgent" || i.tier === "important").length);
      $("#k-prio .sub").textContent = `analysés ${ago(S.priority.computed_at)}`;
      renderSidebar();
    }
  }
}

const kpi = (ic, label, value, sub, id) => `<div class="card kpi" id="${id}"><div class="label">${icon(ic)}${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
const actionCard = (id, ic, color, title, text) => `<button class="card action-card" id="${id}"><div class="ic ${color}">${icon(ic)}</div><h3>${title}</h3><p>${text}</p></button>`;

function onboardingHtml() {
  const c = S.state.configured;
  return `<div class="card onboarding"><h2>Bienvenue ! Trois étapes pour démarrer</h2>
    <div class="muted">Tout reste sur votre machine : vos emails ne sont envoyés qu'à l'IA que vous configurez.</div>
    <div class="steps-list">
      <div class="step-item ${c.llm ? "done" : ""}"><div class="step-num">${c.llm ? "✓" : 1}</div><div><b>Connecter l'IA locale</b><div class="small muted">Ollama, LM Studio, vLLM… (API compatible OpenAI)</div><a href="#/settings" class="small">Configurer →</a></div></div>
      <div class="step-item ${c.mail ? "done" : ""}"><div class="step-num">${c.mail ? "✓" : 2}</div><div><b>Connecter la boîte mail</b><div class="small muted">IMAP / SMTP, ou mode démo pour essayer</div><a href="#/settings" class="small">Configurer →</a></div></div>
      <div class="step-item"><div class="step-num">3</div><div><b>Choisir la période</b><div class="small muted">Glissez sur la timeline ci-dessus pour limiter le périmètre traité.</div></div></div>
    </div></div>`;
}
function bindOnboarding() {}

function digestCard(d) {
  return `<div class="card"><div class="card-head">${icon("sparkles")}<b>${esc(d.title)}</b><span class="badge accent">${plural(d.count, "email")}</span>
    <span class="spacer"></span><span class="small faint">${ago(d.at)}</span>
    <button class="btn ghost sm" id="digest-copy">${icon("copy")}Copier</button><button class="btn ghost sm icon-only" id="digest-close" title="Fermer">${icon("x")}</button></div>
    <div class="card-pad md">${md(d.markdown)}</div></div>`;
}
function bindDigest() {
  const c = $("#digest-copy"), x = $("#digest-close");
  if (c) c.onclick = () => navigator.clipboard.writeText(S.digest.markdown).then(() => toast("Synthèse copiée", "success"));
  if (x) x.onclick = () => { S.digest = null; $("#digest-zone").innerHTML = ""; };
}

async function runDigest(body, title) {
  try {
    const res = await runJob(api("/api/digest", { method: "POST", body }), { title });
    S.digest = { ...res, title, at: Date.now() / 1000 };
    const zone = $("#digest-zone");
    if (zone) { zone.innerHTML = digestCard(S.digest); bindDigest(); zone.scrollIntoView({ behavior: "smooth", block: "start" }); }
    else showDigestModal();
  } catch (e) { fail(e); }
}
function showDigestModal() {
  const d = S.digest;
  const bd = el(`<div class="backdrop"><div class="modal" style="width:min(760px,94vw)"><div class="modal-body"><h3 class="row">${icon("sparkles")}${esc(d.title)}</h3><div class="md">${md(d.markdown)}</div></div>
    <div class="modal-foot"><button class="btn" data-copy>${icon("copy")}Copier</button><button class="btn primary" data-close>Fermer</button></div></div></div>`);
  bd.onclick = (e) => { if (e.target === bd || e.target.closest("[data-close]")) bd.remove(); if (e.target.closest("[data-copy]")) navigator.clipboard.writeText(d.markdown).then(() => toast("Synthèse copiée", "success")); };
  document.body.appendChild(bd);
}

/* =====================================================================
   Prioritaires
   ===================================================================== */
const TIERS = [
  ["urgent", "À traiter aujourd'hui", "red"],
  ["important", "Important", "orange"],
  ["normal", "Normal", "blue"],
  ["faible", "Peu prioritaire", ""],
];
const TIER_COLOR = { urgent: "var(--red)", important: "var(--orange)", normal: "var(--blue)", faible: "var(--text-3)" };
const ACTION_BADGE = { "répondre": "accent", traiter: "orange", planifier: "blue", lire: "", ignorer: "" };

async function renderPriority() {
  const view = $("#view");
  if (!S.priority) {
    view.innerHTML = `<div class="page-head"><div><h1>Prioritaires</h1><p>Chargement…</p></div></div>`;
    S.priority = await api("/api/priority").catch(() => null);
    if (S.priority && !S.priority.computed_at) S.priority = null;
  }
  if (S.route !== "priority") return;
  const p = S.priority;
  view.innerHTML = `
    <div class="page-head"><div><h1>Prioritaires</h1>
      <p>${p ? `${fmtNum(p.unread)} non lus dans la période · ${fmtNum(p.analysed)} analysés par l'IA (${fmtNum(p.from_cache)} depuis le cache) · ${ago(p.computed_at)}` : "Les emails non lus de la période, évalués par l'IA."}</p></div>
      <span class="spacer"></span>
      ${p && p.items.length ? `<button class="btn" id="prio-digest">${icon("sparkles")}Synthèse des prioritaires</button>` : ""}
      <button class="btn primary" id="prio-run">${icon("refresh")}${p ? "Actualiser" : "Analyser mes non lus"}</button>
    </div>
    <div id="prio-body"></div>`;
  $("#prio-run").onclick = runPriority;
  if ($("#prio-digest")) $("#prio-digest").onclick = () => {
    const keys = p.items.filter((i) => i.tier === "urgent" || i.tier === "important").map((i) => i.key);
    runDigest({ keys: keys.length ? keys : p.items.slice(0, 20).map((i) => i.key) }, "Synthèse des prioritaires");
  };
  const body = $("#prio-body");
  if (!p) {
    body.innerHTML = emptyState("flame", "red", "Aucune analyse pour l'instant", "L'IA va lire les non lus de la période sélectionnée et les classer par urgence. Les newsletters sont filtrées localement, sans appel IA.", '<button class="btn primary" id="prio-run2">Lancer l\'analyse</button>');
    $("#prio-run2").onclick = runPriority;
    return;
  }
  if (!p.items.length) { body.innerHTML = emptyState("check", "green", "Rien en attente", "Aucun email non lu dans la période. Bravo !"); return; }
  body.innerHTML = TIERS.map(([tier, label, color]) => {
    const items = p.items.filter((i) => i.tier === tier);
    if (!items.length) return "";
    const collapsed = tier === "faible" && !S.showLowPrio;
    return `<div class="prio-group"><div class="prio-group-head"><span class="dot" style="background:${TIER_COLOR[tier]}"></span>${label}<span class="badge ${color}">${items.length}</span>
      ${tier === "faible" ? `<button class="btn ghost sm" id="toggle-low">${collapsed ? "Afficher" : "Masquer"}</button>` : ""}</div>
      ${collapsed ? "" : `<div class="prio-list">${items.map(prioCard).join("")}</div>`}</div>`;
  }).join("");
  $$(".prio-card", body).forEach((c) => (c.onclick = () => openDrawer(c.dataset.key)));
  if ($("#toggle-low")) $("#toggle-low").onclick = () => { S.showLowPrio = !S.showLowPrio; renderPriority(); };
}

function scoreRing(score, tier) {
  const r = 20, c = 2 * Math.PI * r;
  return `<div class="score-ring"><svg viewBox="0 0 46 46"><circle class="track" cx="23" cy="23" r="${r}"/>
    <circle cx="23" cy="23" r="${r}" stroke="${TIER_COLOR[tier]}" stroke-linecap="round" stroke-dasharray="${(c * score) / 100} ${c}"/></svg>${score}</div>`;
}

function prioCard(i) {
  return `<div class="card prio-card" data-key="${esc(i.key)}">${scoreRing(i.score, i.tier)}
    <div style="min-width:0"><div class="row"><span class="who ellipsis">${esc(i.from_name || i.from_addr)}</span><span class="faint small nowrap">${shortDate(i.date)}</span></div>
      <div class="subj">${esc(i.subject)}</div>
      <div class="reason">${i.ai ? icon("sparkles") : icon("filter")}<span class="ellipsis">${esc(i.reason)}</span></div></div>
    <div class="side"><span class="badge ${ACTION_BADGE[i.action] || ""}">${esc(i.action)}</span>${i.deadline ? `<span class="badge red">${icon("clock")} ${esc(i.deadline)}</span>` : ""}</div></div>`;
}

async function runPriority() {
  const btn = $("#prio-run");
  setBusy(btn, true, "Analyse…");
  try {
    S.priority = await runJob(api("/api/priority", { method: "POST" }), { title: "Analyse des priorités" });
    renderSidebar();
    if (S.route === "priority") renderPriority();
    const n = S.priority.items.filter((i) => i.tier === "urgent").length;
    toast(n ? `${plural(n, "email")} à traiter aujourd'hui` : "Analyse terminée", "success");
  } catch (e) { fail(e); setBusy(btn, false); }
}

function emptyState(ic, color, title, text, extra = "") {
  return `<div class="card empty"><div class="ic ${color}">${icon(ic)}</div><h3>${title}</h3><p style="max-width:460px;margin:0 auto 16px">${text}</p>${extra}</div>`;
}

/* =====================================================================
   Boîte mail
   ===================================================================== */
function renderInbox() {
  const view = $("#view");
  view.className = "view flush";
  const ib = S.inbox;
  view.innerHTML = `<div class="mail-layout" id="mail-layout">
    <div class="mail-list-pane">
      <div class="list-toolbar">
        <div class="search">${icon("search")}<input class="input" id="q" placeholder="Rechercher (expéditeur, objet…)  /" value="${esc(ib.q)}"></div>
        <div class="row">
          <div class="segmented"><button data-f="all" class="${ib.unread ? "" : "active"}">Tous</button><button data-f="unread" class="${ib.unread ? "active" : ""}">Non lus</button></div>
          <span class="spacer"></span>
          <button class="btn sm" id="brief-btn" title="Résumer en une phrase les emails affichés">${icon("sparkles")}Résumer la liste</button>
          <button class="btn sm icon-only" id="sync-btn" title="Synchroniser">${icon("refresh")}</button>
        </div>
      </div>
      <div class="mail-list" id="mail-list"></div>
      <div class="list-footer" id="list-footer"></div>
    </div>
    <div class="reader" id="reader">${readerEmpty()}</div></div>`;
  let t;
  $("#q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { ib.q = e.target.value; ib.offset = 0; loadInbox(false); }, 250); };
  $$("[data-f]").forEach((b) => (b.onclick = () => { ib.unread = b.dataset.f === "unread"; ib.offset = 0; $$("[data-f]").forEach((x) => x.classList.toggle("active", x === b)); loadInbox(false); }));
  $("#sync-btn").onclick = () => loadInbox(true, false);
  $("#brief-btn").onclick = briefList;
  loadInbox(true);
  if (ib.selected) openInReader(ib.selected);
}

const readerEmpty = () => `<div class="reader-empty"><div>${icon("mail")}<div><b>Sélectionnez un email</b></div><div class="small" style="margin-top:6px">
  <kbd>j</kbd>/<kbd>k</kbd> naviguer · <kbd>s</kbd> résumer · <kbd>r</kbd> répondre · <kbd>u</kbd> lu/non lu</div></div></div>`;

async function loadInbox(sync, quiet = true) {
  const ib = S.inbox;
  const list = $("#mail-list");
  if (!list) return;
  if (!ib.items.length || ib.offset === 0) list.innerHTML = Array.from({ length: 8 }, () => `<div class="mail-item"><div class="avatar" style="background:var(--surface-3)"></div><div class="stack" style="gap:7px"><div class="skeleton" style="width:50%"></div><div class="skeleton" style="width:85%"></div><div class="skeleton" style="width:70%"></div></div></div>`).join("");
  await fetchList();
  if (sync && !ib.syncing) {
    ib.syncing = true;
    updateFooter();
    try {
      const stats = await runJob(api("/api/sync", { method: "POST" }), { quiet, title: "Synchronisation" });
      if (stats.new || stats.removed || !quiet) { ib.offset = 0; await fetchList(); }
      if (!quiet) toast(`Synchronisé : ${stats.new} nouveaux emails`, "success");
    } catch (e) { fail(e); }
    ib.syncing = false;
    updateFooter();
  }
}

async function fetchList(append = false) {
  const ib = S.inbox;
  try {
    const res = await api(`/api/messages?unread=${ib.unread}&q=${enc(ib.q)}&offset=${ib.offset}&limit=60`);
    ib.items = append ? ib.items.concat(res.items) : res.items;
    ib.total = res.total;
  } catch (e) { fail(e); }
  renderList();
}

function renderList() {
  const ib = S.inbox, list = $("#mail-list");
  if (!list) return;
  if (!ib.items.length) {
    list.innerHTML = `<div class="empty"><div class="ic violet">${icon("inbox")}</div><h3>${ib.syncing ? "Synchronisation…" : "Aucun email"}</h3><p class="small">${ib.q ? "Aucun résultat pour cette recherche." : "Élargissez la période sur la timeline ou synchronisez."}</p></div>`;
  } else {
    list.innerHTML = ib.items.map(mailItem).join("");
    $$(".mail-item", list).forEach((it) => (it.onclick = () => selectMessage(it.dataset.key)));
  }
  updateFooter();
}

function updateFooter() {
  const ib = S.inbox, f = $("#list-footer");
  if (!f) return;
  f.innerHTML = `${ib.syncing ? '<span class="spinner" style="width:13px;height:13px"></span> Synchronisation…' : `${fmtNum(ib.items.length)} sur ${fmtNum(ib.total)}`}<span class="spacer"></span>
    ${ib.items.length < ib.total ? '<button class="btn sm" id="more">Charger plus</button>' : ""}`;
  if ($("#more")) $("#more").onclick = () => { ib.offset = ib.items.length; fetchList(true); };
}

function mailItem(m) {
  const sel = S.inbox.selected === m.key;
  return `<div class="mail-item ${m.seen ? "" : "unread"} ${sel ? "selected" : ""}" data-key="${esc(m.key)}">
    ${avatar(m.from_name, m.from_addr)}
    <div style="min-width:0;display:flex;flex-direction:column;gap:2px">
      <div class="line1"><span class="from">${esc(m.from_name || m.from_addr)}</span>${m.flagged ? '<span class="badge orange">suivi</span>' : ""}${m.has_attachments ? icon("paperclip") : ""}<span class="date">${shortDate(m.date)}</span></div>
      <div class="subject">${esc(m.subject)}</div>
      ${m.brief ? `<div class="brief">${icon("sparkles")}<span>${esc(m.brief)}</span></div>` : `<div class="snippet">${esc(m.snippet)}</div>`}
    </div></div>`;
}

function selectMessage(key) {
  S.inbox.selected = key;
  $$(".mail-item").forEach((x) => x.classList.toggle("selected", x.dataset.key === key));
  $("#mail-layout").classList.add("reading");
  openInReader(key);
}

function openInReader(key) {
  const reader = $("#reader");
  if (reader) renderReader(reader, key, { back: () => $("#mail-layout").classList.remove("reading") });
}

async function briefList() {
  const keys = S.inbox.items.slice(0, 60).map((m) => m.key);
  if (!keys.length) return;
  const btn = $("#brief-btn");
  setBusy(btn, true, "Résumés…");
  try {
    const briefs = await runJob(api("/api/briefs", { method: "POST", body: { keys } }), { title: "Résumés express" });
    S.inbox.items.forEach((m) => { if (briefs[m.message_id || m.key]) m.brief = briefs[m.message_id || m.key]; });
    renderList();
  } catch (e) { fail(e); }
  setBusy(btn, false);
}

/* ---------- Lecteur ---------- */
async function renderReader(container, key, opts = {}) {
  container.innerHTML = `<div class="reader-inner"><div class="skeleton" style="width:60%;height:22px"></div><div class="skeleton" style="width:35%"></div><div class="card" style="height:260px"></div></div>`;
  let m;
  try { m = await api(`/api/message?key=${enc(key)}&images=${opts.images ? "true" : "false"}`); }
  catch (e) { container.innerHTML = `<div class="reader-empty"><div>${icon("alert")}<div>${esc(e.message)}</div></div></div>`; return; }
  if (container.dataset.key && container.dataset.key !== key && !container.isConnected) return;
  container.dataset.key = key;
  const to = m.headers.To || m.to_addrs;
  container.innerHTML = `<div class="reader-inner">
    ${opts.back ? `<div class="row mobile-back"><button class="btn ghost sm" data-back>${icon("arrowLeft")}Retour</button></div>` : ""}
    <h2 class="reader-subject">${esc(m.subject)}</h2>
    <div class="reader-meta">${avatar(m.from_name, m.from_addr, "lg")}
      <div class="grow"><div><b>${esc(m.from_name || m.from_addr)}</b> <span class="faint small">&lt;${esc(m.from_addr)}&gt;</span></div>
      <div class="small muted ellipsis">À ${esc(to)} · ${DF.long.format(new Date(m.date * 1000))}</div></div>
      <span class="badge">${esc(folderName(m.folder))}</span></div>
    <div class="reader-actions">
      <button class="btn primary" data-act="reply">${icon("reply")}Répondre avec l'IA</button>
      <button class="btn" data-act="summary">${icon("sparkles")}${m.summary ? "Regénérer le résumé" : "Résumer"}</button>
      <button class="btn" data-act="seen">${icon(m.seen ? "eyeoff" : "eye")}${m.seen ? "Marquer non lu" : "Marquer lu"}</button>
      <span class="spacer"></span>
      <div class="segmented" data-mode><button class="active" data-mode="html" ${m.html_doc ? "" : "disabled"}>HTML</button><button data-mode="text">Texte</button></div>
    </div>
    <div id="summary-slot">${m.summary ? summaryCard(m.summary) : ""}</div>
    <div id="composer-slot"></div>
    ${m.has_remote_images && !opts.images ? `<div class="notice">${icon("image")}Images distantes bloquées pour protéger votre vie privée.<span class="spacer"></span><button class="btn sm" data-act="images">Afficher</button></div>` : ""}
    ${m.attachments.length ? `<div class="attachments">${m.attachments.map((a) => `<span class="attachment">${icon("paperclip")}${esc(a.filename)} <span class="faint">${(a.size / 1024).toFixed(0)} Ko</span></span>`).join("")}</div>` : ""}
    <div class="card body-card" id="body-slot"></div></div>`;
  const bodySlot = $("#body-slot", container);
  const showBody = (mode) => {
    if (mode === "html" && m.html_doc) {
      bodySlot.innerHTML = `<iframe class="body-frame" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer"></iframe>`;
      const f = $("iframe", bodySlot);
      f.onload = () => { try { f.style.height = `${f.contentDocument.documentElement.scrollHeight + 24}px`; } catch { f.style.height = "600px"; } };
      f.srcdoc = m.html_doc;
    } else bodySlot.innerHTML = `<div class="body-text">${esc(m.text || "(message vide)")}</div>`;
    $$("[data-mode] button", container).forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  };
  showBody(m.html_doc ? "html" : "text");
  $$("[data-mode] button", container).forEach((b) => (b.onclick = () => showBody(b.dataset.mode)));
  if (opts.back) $("[data-back]", container).onclick = opts.back;

  const actions = {
    reply: () => openComposer(container, m),
    summary: (btn) => summarize(container, m, btn),
    seen: async () => {
      try { await api("/api/message/seen", { method: "POST", body: { keys: [m.key], seen: !m.seen } }); m.seen = !m.seen; updateSeen(m.key, m.seen); renderReader(container, key, opts); }
      catch (e) { fail(e); }
    },
    images: () => renderReader(container, key, { ...opts, images: true }),
  };
  $$("[data-act]", container).forEach((b) => (b.onclick = () => actions[b.dataset.act](b)));
  container._actions = actions;
  container._msg = m;
  bindSuggestions(container, m);
  if (!m.seen) {
    api("/api/message/seen", { method: "POST", body: { keys: [m.key], seen: true } }).then(() => { m.seen = true; updateSeen(m.key, true); }).catch(() => {});
  }
}

function updateSeen(key, seen) {
  const it = S.inbox.items.find((x) => x.key === key);
  if (it) it.seen = seen;
  const node = $$(".mail-item").find((x) => x.dataset.key === key);
  if (node) node.classList.toggle("unread", !seen);
  if (S.priority && seen) {
    const p = S.priority.items.find((x) => x.key === key);
    if (p) p.seen = true;
  }
}

function summaryCard(s) {
  const list = (arr) => `<ul>${arr.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  return `<div class="card summary-card"><div class="title">${icon("sparkles")}Résumé IA ${s.deadline ? `<span class="badge red">${icon("clock")} ${esc(s.deadline)}</span>` : ""}</div>
    <div>${esc(s.summary)}</div>
    ${s.key_points.length || s.actions.length ? `<div class="cols">${s.key_points.length ? `<div><h4>Points clés</h4>${list(s.key_points)}</div>` : ""}${s.actions.length ? `<div><h4>Actions attendues</h4>${list(s.actions)}</div>` : ""}</div>` : ""}
    ${s.reply_suggestions.length ? `<div class="row wrap" style="margin-top:12px"><span class="small faint">Répondre :</span>${s.reply_suggestions.map((r) => `<button class="chip" data-suggest="${esc(r)}">${icon("reply")}${esc(r)}</button>`).join("")}</div>` : ""}</div>`;
}

function bindSuggestions(container, m) {
  $$("[data-suggest]", container).forEach((c) => (c.onclick = () => openComposer(container, m, c.dataset.suggest, true)));
}

async function summarize(container, m, btn) {
  setBusy(btn, true, "Résumé…");
  const slot = $("#summary-slot", container);
  slot.innerHTML = `<div class="card summary-card"><div class="title">${icon("sparkles")}Résumé IA</div><div class="stack" style="gap:8px"><div class="skeleton" style="width:90%"></div><div class="skeleton" style="width:75%"></div></div></div>`;
  try {
    m.summary = await api("/api/summary", { method: "POST", body: { key: m.key, force: Boolean(m.summary) } });
    slot.innerHTML = summaryCard(m.summary);
    bindSuggestions(container, m);
  } catch (e) { slot.innerHTML = ""; fail(e); }
  setBusy(btn, false);
}

/* ---------- Rédaction ---------- */
async function openComposer(container, m, instruction = "", autostart = false) {
  const slot = $("#composer-slot", container);
  if ($(".composer", slot)) {
    if (instruction) { $("#c-instr", slot).value = instruction; if (autostart) $("#c-gen", slot).click(); }
    slot.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  slot.innerHTML = `<div class="card composer">
    <div class="composer-head">${icon("wand")}Réponse assistée<span class="spacer"></span><button class="btn ghost sm icon-only" id="c-close" title="Fermer">${icon("x")}</button></div>
    <div class="composer-body">
      <div class="row wrap"><span class="small faint">Ton</span><div class="segmented" id="c-tone">
        <button data-tone="pro" class="active">Professionnel</button><button data-tone="formel">Formel</button><button data-tone="amical">Amical</button><button data-tone="bref">Bref</button></div></div>
      <div class="row"><input class="input grow" id="c-instr" placeholder="Consigne (facultatif) : ex. accepter mais proposer jeudi 14h" value="${esc(instruction)}">
        <button class="btn primary" id="c-gen">${icon("sparkles")}Générer</button></div>
      <div class="addr"><span>À</span><input class="input" id="c-to"></div>
      <div class="addr"><span>Cc</span><div class="row"><input class="input grow" id="c-cc"><button class="btn sm ghost" id="c-ccall" title="Ajouter les autres destinataires">Répondre à tous</button></div></div>
      <div class="addr"><span>Objet</span><input class="input" id="c-subject"></div>
      <textarea class="input draft" id="c-body" placeholder="Le brouillon généré apparaîtra ici. Vous pouvez aussi écrire directement."></textarea>
    </div>
    <div class="composer-foot">
      <button class="btn" id="c-save">${icon("save")}Enregistrer en brouillon</button>
      <button class="btn primary" id="c-send">${icon("send")}Envoyer…</button>
      <button class="btn ghost" id="c-copy">${icon("copy")}Copier</button>
      <span class="spacer"></span><span class="small faint" id="c-status"></span>
    </div></div>`;
  slot.scrollIntoView({ behavior: "smooth", block: "start" });
  let tone = "pro", ctrl = null, ccAll = "";
  $$("#c-tone button", slot).forEach((b) => (b.onclick = () => { tone = b.dataset.tone; $$("#c-tone button", slot).forEach((x) => x.classList.toggle("active", x === b)); }));
  $("#c-close", slot).onclick = () => { if (ctrl) ctrl.abort(); slot.innerHTML = ""; };
  api(`/api/reply-context?key=${enc(m.key)}`).then((rc) => {
    $("#c-to", slot).value = rc.to; $("#c-subject", slot).value = rc.subject; ccAll = rc.cc_all;
    if (!ccAll) $("#c-ccall", slot).classList.add("hidden");
  }).catch(fail);
  $("#c-ccall", slot).onclick = () => { $("#c-cc", slot).value = ccAll; };
  const body = $("#c-body", slot), status = $("#c-status", slot), gen = $("#c-gen", slot);

  gen.onclick = async () => {
    if (ctrl) { ctrl.abort(); return; }
    ctrl = new AbortController();
    body.value = ""; body.readOnly = true; body.classList.add("typing");
    gen.innerHTML = `${icon("stop")}Arrêter`;
    status.innerHTML = '<span class="spinner" style="width:12px;height:12px"></span> Rédaction en cours…';
    const t0 = performance.now();
    try {
      const res = await fetch("/api/draft", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: m.key, instructions: $("#c-instr", slot).value, tone }), signal: ctrl.signal });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Erreur ${res.status}`);
      const reader = res.body.getReader(), dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
          if (!chunk.startsWith("data:")) continue;
          const data = JSON.parse(chunk.slice(5));
          if (data.error) throw new Error(data.error);
          if (data.delta) { body.value += data.delta; body.scrollTop = body.scrollHeight; }
        }
      }
      body.value = body.value.trim();
      status.textContent = `Brouillon prêt en ${((performance.now() - t0) / 1000).toFixed(1)} s — relisez avant d'envoyer.`;
    } catch (e) {
      if (e.name === "AbortError") status.textContent = "Génération interrompue.";
      else { status.textContent = ""; fail(e); }
    } finally {
      ctrl = null; body.readOnly = false; body.classList.remove("typing");
      gen.innerHTML = `${icon("sparkles")}Régénérer`;
    }
  };
  const payload = (send) => ({ key: m.key, to: $("#c-to", slot).value, cc: $("#c-cc", slot).value, subject: $("#c-subject", slot).value, body: body.value, send });
  $("#c-save", slot).onclick = async (e) => {
    setBusy(e.currentTarget, true, "Enregistrement…");
    try { const r = await api("/api/draft/save", { method: "POST", body: payload(false) }); toast(`Brouillon enregistré dans « ${r.folder} »`, "success"); status.textContent = "Enregistré dans les brouillons."; }
    catch (err) { fail(err); }
    setBusy(e.currentTarget, false);
  };
  $("#c-send", slot).onclick = async (e) => {
    if (!body.value.trim()) return toast("Le message est vide", "error");
    const ok = await modal({ title: "Envoyer cette réponse ?", body: `À <b>${esc($("#c-to", slot).value)}</b>${$("#c-cc", slot).value ? `, Cc ${esc($("#c-cc", slot).value)}` : ""}<br>Objet : ${esc($("#c-subject", slot).value)}`, confirm: "Envoyer" });
    if (!ok) return;
    const btn = e.currentTarget;
    setBusy(btn, true, "Envoi…");
    try { await api("/api/draft/save", { method: "POST", body: payload(true) }); toast("Réponse envoyée", "success"); slot.innerHTML = ""; }
    catch (err) { fail(err); setBusy(btn, false); }
  };
  $("#c-copy", slot).onclick = () => navigator.clipboard.writeText(body.value).then(() => toast("Copié", "success"));
  if (autostart) gen.click(); else $("#c-instr", slot).focus();
}

/* ---------- Tiroir (lecture depuis les priorités) ---------- */
function openDrawer(key) {
  closeDrawer();
  const bd = el('<div class="drawer-backdrop"></div>');
  const dr = el(`<div class="drawer"><div class="drawer-head"><button class="btn ghost sm" data-close>${icon("x")}Fermer</button><span class="spacer"></span>
    <a class="btn ghost sm" href="#/inbox" data-inbox>${icon("inbox")}Voir dans la boîte</a></div><div class="reader" style="flex:1"></div></div>`);
  bd.onclick = closeDrawer;
  $("[data-close]", dr).onclick = closeDrawer;
  $("[data-inbox]", dr).onclick = () => { S.inbox.selected = key; };
  document.body.append(bd, dr);
  renderReader($(".reader", dr), key);
}
function closeDrawer() {
  $$(".drawer, .drawer-backdrop").forEach((x) => x.remove());
  if (S.route === "priority" && S.priority && $("#prio-body")) {
    // retire visuellement les emails lus entre-temps
  }
}

/* =====================================================================
   Tri de l'historique
   ===================================================================== */
const SORT_STEPS = ["Analyse", "Arborescence", "Classement", "Application"];

async function renderSort() {
  const view = $("#view");
  if (S.plan === null) {
    view.innerHTML = `<div class="page-head"><div><h1>Trier l'historique</h1><p>Chargement…</p></div></div>`;
    const p = await api("/api/sort/plan").catch(() => ({}));
    S.plan = p && p.id ? p : false;
  }
  if (S.route !== "sort") return;
  const plan = S.plan;
  const step = !plan || plan.restart ? 0 : plan.status === "proposed" ? 1 : plan.status === "assigned" ? 2 : 3;
  view.innerHTML = `<div class="page-head"><div><h1>Trier l'historique</h1>
      <p>L'IA propose une nouvelle organisation en dossiers ; rien n'est déplacé sans votre confirmation.</p></div></div>
    <div class="stepper">${SORT_STEPS.map((s, i) => `<div class="st ${i === step ? "active" : i < step ? "done" : ""}"><span class="step-num">${i < step ? "✓" : i + 1}</span>${s}</div>`).join("")}</div>
    <div id="sort-body"></div>`;
  [sortStep1, sortStep2, sortStep3, sortStep4][step]($("#sort-body"), plan);
}

function scopeDescription() {
  const sc = scope();
  const from = sc.since ? DF.dmyl.format(parseDay(sc.since)) : "le début";
  const to = sc.until ? DF.dmyl.format(parseDay(sc.until)) : "aujourd'hui";
  return `<b>${sc.folders.map((f) => esc(folderName(f))).join(", ")}</b>, de ${from} à ${to}`;
}

async function sortStep1(body) {
  const rules = await api("/api/sort/rules").catch(() => ({}));
  const nRules = Object.keys(rules).length;
  body.innerHTML = `<div class="grid-2" style="align-items:start">
    <div class="card card-pad stack">
      <div class="section-title"><div class="ic violet">${icon("wand")}</div><div><h2>Proposer une arborescence</h2><div class="small muted">Périmètre : ${scopeDescription()}</div></div></div>
      <div class="muted small">L'IA reçoit uniquement un résumé compact des expéditeurs (volume et quelques objets), pas le contenu des emails : un seul appel suffit, même pour des milliers de messages.</div>
      <label class="field">Vos préférences (facultatif)<textarea class="input" id="hint" rows="3" placeholder="Ex. : un dossier par client, regrouper toutes les factures, pas plus de 6 dossiers…"></textarea></label>
      <div class="row"><button class="btn primary" id="propose">${icon("sparkles")}Analyser et proposer</button></div>
    </div>
    <div class="card card-pad stack">
      <div class="section-title"><div class="ic green">${icon("bolt")}</div><div><h2>Règles apprises</h2><div class="small muted">${nRules ? `${nRules} expéditeurs associés à un dossier` : "Aucune règle pour l'instant"}</div></div></div>
      <div class="muted small">Après un tri, chaque expéditeur est associé à son dossier. Les nouveaux emails peuvent ensuite être rangés instantanément, sans aucun appel à l'IA.</div>
      <div class="row"><button class="btn" id="apply-rules" ${nRules ? "" : "disabled"}>${icon("folders")}Ranger avec les règles</button>
      ${nRules ? `<button class="btn ghost danger" id="del-rules">${icon("trash")}Oublier les règles</button>` : ""}</div>
    </div></div>`;
  $("#propose").onclick = async (e) => {
    setBusy(e.currentTarget, true, "Analyse…");
    try { S.plan = await runJob(api("/api/sort/propose", { method: "POST", body: { hint: $("#hint").value } }), { title: "Conception de l'arborescence" }); renderSort(); }
    catch (err) { fail(err); setBusy(e.currentTarget, false); }
  };
  if (nRules) {
    $("#apply-rules").onclick = applyRules;
    $("#del-rules").onclick = async () => { if (await modal({ title: "Oublier les règles ?", body: "Les associations expéditeur → dossier seront supprimées.", confirm: "Oublier", danger: true })) { await api("/api/sort/rules", { method: "DELETE" }); renderSort(); } };
  }
}

async function applyRules() {
  if (!(await modal({ title: "Ranger avec les règles ?", body: `Les emails de ${scopeDescription()} dont l'expéditeur est connu seront déplacés dans leur dossier.`, confirm: "Ranger" }))) return;
  try { const r = await runJob(api("/api/sort/rules/apply", { method: "POST" }), { title: "Tri par règles" }); toast(`${plural(r.moved, "email")} rangé${r.moved > 1 ? "s" : ""}`, "success"); S.priority = null; loadTimeline(); renderSidebar(); }
  catch (e) { fail(e); }
}

function sortStep2(body, plan) {
  let folders = plan.folders.map((f) => ({ ...f }));
  const root = S.state.settings.mail.sorted_root;
  const draw = () => {
    body.innerHTML = `<div style="display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:start" class="sort-step2">
      <div class="stack">
        ${plan.rationale ? `<div class="card card-pad row" style="align-items:flex-start">${icon("sparkles")}<div><b>Proposition de l'IA</b><div class="muted">${esc(plan.rationale)}</div></div></div>` : ""}
        <div class="card card-pad stack">
          <div class="row"><h2 class="grow">Arborescence proposée</h2><span class="small faint">${folders.length} dossiers · ${fmtNum(plan.total)} emails analysés</span></div>
          <div class="small muted">Renommez, ajoutez ou supprimez des dossiers. Utilisez « / » pour un sous-dossier (ex. <code>Finances/Factures</code>).</div>
          <div class="tree-editor">${folders.map((f, i) => `<div class="tree-row ${f.path.includes("/") ? "child" : ""}" data-i="${i}">
            <span class="folder-ic">${icon("folder")}</span>
            <input class="input" data-k="path" value="${esc(f.path)}" placeholder="Nom du dossier">
            <input class="input desc" data-k="description" value="${esc(f.description)}" placeholder="Description (aide l'IA à classer)">
            <span class="count">${plan.folder_counts[f.path] ? fmtNum(plan.folder_counts[f.path]) + " emails" : ""}</span>
            <button class="btn ghost sm icon-only" data-del title="Supprimer">${icon("trash")}</button></div>`).join("")}</div>
          <div class="row"><button class="btn sm" id="add-folder">${icon("plus")}Ajouter un dossier</button></div>
        </div>
        <div class="row"><button class="btn" id="redo">${icon("refresh")}Nouvelle proposition</button><span class="spacer"></span>
          <button class="btn primary" id="confirm-tree">${icon("check")}Valider et classer les emails</button></div>
      </div>
      <div class="card card-pad stack" style="position:sticky;top:0"><b>Aperçu</b><div class="tree-preview" id="tree-preview"></div>
        <div class="small faint">Les dossiers seront créés ${root ? `sous « ${esc(root)} »` : "à la racine de la boîte"} (modifiable dans Réglages).</div></div>
    </div>`;
    $$(".tree-row input", body).forEach((inp) => (inp.oninput = () => { folders[Number(inp.closest(".tree-row").dataset.i)][inp.dataset.k] = inp.value; preview(); }));
    $$("[data-del]", body).forEach((b) => (b.onclick = () => { folders.splice(Number(b.closest(".tree-row").dataset.i), 1); draw(); }));
    $("#add-folder").onclick = () => { folders.push({ path: "", description: "" }); draw(); $$(".tree-row input[data-k=path]", body).pop().focus(); };
    $("#redo").onclick = () => { S.plan = { ...plan, restart: true }; renderSort(); };
    $("#confirm-tree").onclick = async (e) => {
      const clean = folders.filter((f) => f.path.trim());
      if (!clean.length) return toast("Ajoutez au moins un dossier", "error");
      setBusy(e.currentTarget, true, "Classement…");
      try {
        await api(`/api/sort/plan/${plan.id}/tree`, { method: "PUT", body: { folders: clean } });
        S.plan = await runJob(api(`/api/sort/plan/${plan.id}/assign`, { method: "POST" }), { title: "Classement des expéditeurs" });
        renderSort();
      } catch (err) { fail(err); setBusy(e.currentTarget, false); }
    };
    preview();
  };
  const preview = () => {
    const tree = {};
    for (const f of folders) {
      const parts = f.path.split("/").map((s) => s.trim()).filter(Boolean);
      if (!parts.length) continue;
      tree[parts[0]] = tree[parts[0]] || new Set();
      if (parts[1]) tree[parts[0]].add(parts[1]);
    }
    const lines = [root ? `📁 ${root}` : "📥 Boîte de réception"];
    const tops = Object.keys(tree);
    tops.forEach((t, i) => {
      const last = i === tops.length - 1, subs = [...tree[t]];
      lines.push(`${last ? "└─" : "├─"} 📁 ${t}`);
      subs.forEach((s, j) => lines.push(`${last ? "   " : "│  "}${j === subs.length - 1 ? "└─" : "├─"} ${s}`));
    });
    $("#tree-preview").textContent = lines.join("\n");
  };
  draw();
}

function sortStep3(body, plan) {
  const folders = plan.folders.map((f) => f.path);
  const groupsBy = (path) => plan.groups.filter((g) => (plan.assignments[g.id] || "") === path);
  let filter = "";
  const moved = plan.groups.filter((g) => plan.assignments[g.id]).reduce((a, g) => a + g.count, 0);
  const draw = () => {
    const columns = [...folders, ""];
    body.innerHTML = `<div class="card card-pad row wrap" style="margin-bottom:16px">
        <div class="section-title grow"><div class="ic green">${icon("folders")}</div><div><h2>${fmtNum(moved)} emails seront rangés dans ${folders.length} dossiers</h2>
        <div class="small muted">${fmtNum(plan.total - moved)} restent dans leur dossier actuel · ${plan.groups.length} expéditeurs. Glissez un expéditeur vers un autre dossier ou utilisez le sélecteur.</div></div></div>
        <div class="search" style="width:240px">${icon("search")}<input class="input" id="g-filter" placeholder="Filtrer les expéditeurs" value="${esc(filter)}"></div>
      </div>
      <div class="preview-grid">${columns.map((path) => {
        const gs = groupsBy(path).filter((g) => !filter || (g.sender + " " + g.name).toLowerCase().includes(filter.toLowerCase()));
        const count = groupsBy(path).reduce((a, g) => a + g.count, 0);
        return `<div class="card folder-card" data-path="${esc(path)}"><div class="fc-head">${icon(path ? "folder" : "inbox")}<span class="name" title="${esc(path)}">${esc(path || "Inchangé (reste en place)")}</span><span class="badge ${path ? "accent" : ""}">${fmtNum(count)}</span></div>
          <div class="fc-body">${gs.map((g) => `<div class="group-pill" draggable="true" data-g="${g.id}" title="${esc(g.subjects.join("\n"))}">
            ${avatar(g.name, g.sender, "xs")}
            <span class="ellipsis">${esc(g.name || g.sender)}</span>
            <select data-g="${g.id}">${columns.map((c) => `<option value="${esc(c)}" ${c === path ? "selected" : ""}>${esc(c || "Inchangé")}</option>`).join("")}</select>
            <span class="n">${g.count}</span></div>`).join("") || '<div class="small faint" style="padding:8px">Aucun expéditeur</div>'}</div></div>`;
      }).join("")}</div>
      <div class="row" style="margin-top:18px"><button class="btn" id="back-tree">${icon("arrowLeft")}Modifier l'arborescence</button><span class="spacer"></span>
        <button class="btn primary" id="apply-plan" ${moved ? "" : "disabled"}>${icon("check")}Appliquer le tri (${fmtNum(moved)} emails)</button></div>`;
    $("#g-filter").oninput = (e) => { filter = e.target.value; const pos = e.target.selectionStart; draw(); const f = $("#g-filter"); f.focus(); f.setSelectionRange(pos, pos); };
    $$("select[data-g]", body).forEach((s) => (s.onchange = () => reassign(s.dataset.g, s.value)));
    $$(".group-pill", body).forEach((p) => {
      p.ondragstart = (e) => { e.dataTransfer.setData("text/plain", p.dataset.g); p.classList.add("dragging"); };
      p.ondragend = () => p.classList.remove("dragging");
    });
    $$(".folder-card", body).forEach((c) => {
      c.ondragover = (e) => { e.preventDefault(); c.classList.add("drop-over"); };
      c.ondragleave = () => c.classList.remove("drop-over");
      c.ondrop = (e) => { e.preventDefault(); c.classList.remove("drop-over"); reassign(e.dataTransfer.getData("text/plain"), c.dataset.path); };
    });
    $("#back-tree").onclick = () => { S.plan = { ...plan, status: "proposed" }; renderSort(); };
    $("#apply-plan").onclick = async (e) => {
      const ok = await modal({ title: "Appliquer le tri ?", body: `<b>${fmtNum(moved)} emails</b> vont être déplacés dans ${folders.length} dossiers (créés si nécessaire).<br><br>L'opération modifie votre boîte mail sur le serveur. Les règles apprises permettront de ranger les futurs emails automatiquement.`, confirm: "Déplacer les emails" });
      if (!ok) return;
      setBusy(e.currentTarget, true, "Déplacement…");
      try { S.plan = await runJob(api(`/api/sort/plan/${plan.id}/apply`, { method: "POST" }), { title: "Application du tri" }); S.folders = []; S.priority = null; S.inbox.items = []; S.inbox.selected = null; renderSidebar(); renderSort(); loadTimeline(); toast("Tri appliqué", "success"); }
      catch (err) { fail(err); setBusy(e.currentTarget, false); }
    };
  };
  const reassign = async (gid, path) => {
    if (!gid || (plan.assignments[gid] || "") === path) return;
    plan.assignments[gid] = path;
    draw();
    try { const p = await api(`/api/sort/plan/${plan.id}/assignments`, { method: "PUT", body: { assignments: { [gid]: path } } }); Object.assign(plan, p); S.plan = plan; sortStep3(body, plan); }
    catch (e) { fail(e); }
  };
  draw();
}

function sortStep4(body, plan) {
  const a = plan.applied || {};
  body.innerHTML = emptyState("check", "green", "Votre boîte est rangée", `${fmtNum(a.moved)} emails déplacés dans ${a.folders} dossiers ${a.at ? ago(a.at) : ""}. Les associations expéditeur → dossier ont été mémorisées.`,
    `<div class="row" style="justify-content:center"><button class="btn" id="rules-now">${icon("bolt")}Ranger les nouveaux emails (sans IA)</button><button class="btn primary" id="new-sort">${icon("plus")}Nouveau tri</button></div>`);
  $("#rules-now").onclick = applyRules;
  $("#new-sort").onclick = () => { S.plan = { ...plan, restart: true }; renderSort(); };
}

/* =====================================================================
   Réglages
   ===================================================================== */
const LLM_PRESETS = [
  ["Ollama", "http://localhost:11434/v1"], ["LM Studio", "http://localhost:1234/v1"], ["llama.cpp", "http://localhost:8080/v1"],
  ["vLLM", "http://localhost:8000/v1"], ["Jan", "http://localhost:1337/v1"], ["LocalAI", "http://localhost:8080/v1"],
];
const MAIL_PRESETS = {
  Gmail: ["imap.gmail.com", 993, "smtp.gmail.com", 587, "starttls", "Utilisez un mot de passe d'application (Compte Google → Sécurité)."],
  Outlook: ["outlook.office365.com", 993, "smtp-mail.outlook.com", 587, "starttls", "Certains comptes Microsoft exigent OAuth : préférez un mot de passe d'application si disponible."],
  Yahoo: ["imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 465, "ssl", "Mot de passe d'application requis."],
  iCloud: ["imap.mail.me.com", 993, "smtp.mail.me.com", 587, "starttls", "Mot de passe d'application requis (appleid.apple.com)."],
  Orange: ["imap.orange.fr", 993, "smtp.orange.fr", 465, "ssl", ""],
  Free: ["imap.free.fr", 993, "smtp.free.fr", 465, "ssl", ""],
  OVH: ["ssl0.ovh.net", 993, "ssl0.ovh.net", 465, "ssl", ""],
  Infomaniak: ["mail.infomaniak.com", 993, "mail.infomaniak.com", 465, "ssl", ""],
};

function renderSettings() {
  const s = S.state.settings;
  const v = (x) => esc(x ?? "");
  const view = $("#view");
  view.innerHTML = `<div class="page-head"><div><h1>Réglages</h1><p>Tout est stocké localement dans <code>~/.trieurmail</code>.</p></div></div>
  <div class="settings-layout">
    <nav class="settings-nav">
      <a class="nav-item" href="#s-llm" data-scroll>${icon("cpu")}<span>Intelligence artificielle</span></a>
      <a class="nav-item" href="#s-mail" data-scroll>${icon("mail")}<span>Messagerie</span></a>
      <a class="nav-item" href="#s-profile" data-scroll>${icon("user")}<span>Profil</span></a>
      <a class="nav-item" href="#s-app" data-scroll>${icon("palette")}<span>Apparence & cache</span></a>
    </nav>
    <div>
    <section class="card settings-section" id="s-llm"><div class="card-head"><div class="section-title"><div class="ic violet">${icon("cpu")}</div><div><b>Intelligence artificielle</b><div class="small muted">Tout serveur compatible avec l'API OpenAI (chat/completions).</div></div></div></div>
      <div class="card-pad">
        <div class="provider-presets"><span class="small faint" style="align-self:center">Préréglages :</span>${LLM_PRESETS.map(([n, u]) => `<button class="chip" data-llm-preset="${u}">${n}</button>`).join("")}</div>
        <div class="grid-2">
          <label class="field">URL de base de l'API<input class="input" data-path="llm.base_url" value="${v(s.llm.base_url)}" placeholder="http://localhost:11434/v1"><span class="hint">Le chemin /chat/completions est ajouté automatiquement.</span></label>
          <label class="field">Clé API<input class="input" type="password" data-path="llm.api_key" value="${v(s.llm.api_key)}" placeholder="facultatif en local" autocomplete="off"></label>
          <label class="field">Modèle principal<input class="input" data-path="llm.model" list="models" value="${v(s.llm.model)}" placeholder="ex. qwen2.5:14b-instruct"><span class="hint">Synthèses, réponses, conception de l'arborescence.</span></label>
          <label class="field">Modèle rapide (facultatif)<input class="input" data-path="llm.model_fast" list="models" value="${v(s.llm.model_fast)}" placeholder="ex. llama3.2:3b"><span class="hint">Tâches de masse : priorisation, classement, résumés express.</span></label>
        </div>
        <datalist id="models"></datalist>
        <div class="grid-3">
          <label class="field">Température <span class="hint" id="temp-val">${s.llm.temperature}</span><input type="range" min="0" max="1.5" step="0.05" data-path="llm.temperature" data-type="number" value="${s.llm.temperature}"></label>
          <label class="field">Tokens max par réponse<input class="input" type="number" min="128" max="32000" data-path="llm.max_tokens" data-type="number" value="${s.llm.max_tokens}"></label>
          <label class="field">Délai d'attente (s)<input class="input" type="number" min="10" max="1200" data-path="llm.timeout" data-type="number" value="${s.llm.timeout}"></label>
          <label class="field">Requêtes parallèles<input class="input" type="number" min="1" max="16" data-path="llm.concurrency" data-type="number" value="${s.llm.concurrency}"><span class="hint">1–2 pour un GPU local, plus pour vLLM.</span></label>
          <label class="field">Emails par appel (lots)<input class="input" type="number" min="1" max="60" data-path="llm.batch_size" data-type="number" value="${s.llm.batch_size}"><span class="hint">Plus grand = moins d'appels, contexte plus long.</span></label>
          <label class="field">Caractères max par email<input class="input" type="number" min="200" max="20000" data-path="llm.max_chars_per_email" data-type="number" value="${s.llm.max_chars_per_email}"></label>
          <label class="field">Non lus analysés par l'IA (max)<input class="input" type="number" min="5" max="500" data-path="llm.max_priority_candidates" data-type="number" value="${s.llm.max_priority_candidates}"><span class="hint">Les autres gardent leur pré-score local.</span></label>
        </div>
        <label class="switch"><input type="checkbox" data-path="llm.json_mode" ${s.llm.json_mode ? "checked" : ""}>Mode JSON (<code>response_format</code>) — désactivé automatiquement si non supporté</label>
        <div id="llm-test"></div>
        <div class="row"><button class="btn" id="test-llm">${icon("bolt")}Tester & lister les modèles</button><span class="spacer"></span><button class="btn primary" data-save="llm">${icon("save")}Enregistrer</button></div>
      </div></section>

    <section class="card settings-section" id="s-mail"><div class="card-head"><div class="section-title"><div class="ic blue">${icon("mail")}</div><div><b>Messagerie</b><div class="small muted">IMAP pour lire et ranger, SMTP pour envoyer.</div></div></div></div>
      <div class="card-pad">
        <div class="segmented" id="provider"><button data-p="demo" class="${s.mail.provider === "demo" ? "active" : ""}">Mode démo</button><button data-p="imap" class="${s.mail.provider === "imap" ? "active" : ""}">Compte IMAP</button></div>
        <div id="imap-fields" class="stack ${s.mail.provider === "imap" ? "" : "hidden"}" style="gap:16px">
          <div class="provider-presets"><span class="small faint" style="align-self:center">Fournisseur :</span>${Object.keys(MAIL_PRESETS).map((n) => `<button class="chip" data-mail-preset="${n}">${n}</button>`).join("")}</div>
          <div id="preset-note" class="notice hidden"></div>
          <div class="grid-3">
            <label class="field">Serveur IMAP<input class="input" data-path="mail.imap_host" value="${v(s.mail.imap_host)}" placeholder="imap.exemple.fr"></label>
            <label class="field">Port<input class="input" type="number" data-path="mail.imap_port" data-type="number" value="${s.mail.imap_port}"></label>
            <label class="switch" style="align-self:end;height:36px"><input type="checkbox" data-path="mail.imap_ssl" ${s.mail.imap_ssl ? "checked" : ""}>SSL/TLS</label>
          </div>
          <div class="grid-2">
            <label class="field">Identifiant<input class="input" data-path="mail.username" value="${v(s.mail.username)}" autocomplete="username"></label>
            <label class="field">Mot de passe<input class="input" type="password" data-path="mail.password" value="${v(s.mail.password)}" autocomplete="current-password"><span class="hint">Stocké localement (fichier lisible par vous seul).</span></label>
          </div>
          <div class="grid-3">
            <label class="field">Serveur SMTP<input class="input" data-path="mail.smtp_host" value="${v(s.mail.smtp_host)}" placeholder="smtp.exemple.fr"></label>
            <label class="field">Port SMTP<input class="input" type="number" data-path="mail.smtp_port" data-type="number" value="${s.mail.smtp_port}"></label>
            <label class="field">Sécurité<select class="input" data-path="mail.smtp_security">${["starttls", "ssl", "none"].map((o) => `<option ${s.mail.smtp_security === o ? "selected" : ""}>${o}</option>`).join("")}</select></label>
            <label class="field">Identifiant SMTP<input class="input" data-path="mail.smtp_username" value="${v(s.mail.smtp_username)}" placeholder="identique à l'IMAP"></label>
            <label class="field">Mot de passe SMTP<input class="input" type="password" data-path="mail.smtp_password" value="${v(s.mail.smtp_password)}" placeholder="identique à l'IMAP"></label>
          </div>
        </div>
        <div class="grid-2">
          <label class="field">Nom d'expéditeur<input class="input" data-path="mail.from_name" value="${v(s.mail.from_name)}"></label>
          <label class="field">Adresse d'expédition<input class="input" data-path="mail.from_address" value="${v(s.mail.from_address)}" placeholder="vous@exemple.fr"></label>
          <label class="field">Dossier des brouillons<input class="input" data-path="mail.drafts_folder" value="${v(s.mail.drafts_folder)}" placeholder="détection automatique"></label>
          <label class="field">Dossier parent pour le tri<input class="input" data-path="mail.sorted_root" value="${v(s.mail.sorted_root)}" placeholder="aucun (racine)"><span class="hint">Ex. « Classé » : les dossiers créés seront Classé/…</span></label>
        </div>
        <div id="mail-test"></div>
        <div class="row"><button class="btn" id="test-mail">${icon("bolt")}Tester la connexion</button><span class="spacer"></span><button class="btn primary" data-save="mail">${icon("save")}Enregistrer</button></div>
      </div></section>

    <section class="card settings-section" id="s-profile"><div class="card-head"><div class="section-title"><div class="ic orange">${icon("user")}</div><div><b>Profil</b><div class="small muted">Contexte transmis à l'IA pour mieux prioriser et répondre.</div></div></div></div>
      <div class="card-pad">
        <div class="grid-2">
          <label class="field">Votre nom<input class="input" data-path="profile.full_name" value="${v(s.profile.full_name)}"></label>
          <label class="field">Langue de travail<input class="input" data-path="profile.language" value="${v(s.profile.language)}"></label>
        </div>
        <label class="field">À propos de vous<textarea class="input" rows="3" data-path="profile.about" placeholder="Ex. : Responsable produit chez Acme. Ma manager est Sophie Bernard. Mes clients prioritaires : …">${v(s.profile.about)}</textarea><span class="hint">Aide l'IA à reconnaître ce qui compte pour vous.</span></label>
        <label class="field">Signature<textarea class="input" rows="3" data-path="profile.signature" placeholder="Camille Martin&#10;Responsable produit">${v(s.profile.signature)}</textarea></label>
        <label class="switch"><input type="checkbox" data-path="profile.include_newsletters_in_priority" ${s.profile.include_newsletters_in_priority ? "checked" : ""}>Envoyer aussi les newsletters / notifications à l'IA lors de la priorisation</label>
        <div class="row"><span class="spacer"></span><button class="btn primary" data-save="profile">${icon("save")}Enregistrer</button></div>
      </div></section>

    <section class="card settings-section" id="s-app"><div class="card-head"><div class="section-title"><div class="ic green">${icon("palette")}</div><div><b>Apparence & cache</b></div></div></div>
      <div class="card-pad">
        <div class="row"><span class="grow">Thème</span><div class="segmented" id="theme">${[["auto", "Système"], ["light", "Clair"], ["dark", "Sombre"]].map(([t, l]) => `<button data-t="${t}" class="${s.theme === t ? "active" : ""}">${l}</button>`).join("")}</div></div>
        <div class="row"><div class="grow"><b>Cache local</b><div class="small muted">${fmtNum(S.state.cache.messages)} en-têtes · ${fmtNum(S.state.cache.bodies)} corps · ${fmtNum(S.state.cache.insights)} analyses IA · ${fmtNum(S.state.cache.llm_cache)} réponses IA</div></div>
          <button class="btn danger" id="clear-ai">${icon("trash")}Vider le cache IA</button></div>
      </div></section>
    </div></div>`;

  $$("[data-scroll]").forEach((a) => (a.onclick = (e) => { e.preventDefault(); $(a.getAttribute("href")).scrollIntoView({ behavior: "smooth" }); }));
  $("[data-path='llm.temperature']").oninput = (e) => ($("#temp-val").textContent = e.target.value);
  $$("[data-llm-preset]").forEach((b) => (b.onclick = () => { $("[data-path='llm.base_url']").value = b.dataset.llmPreset; }));
  let provider = s.mail.provider;
  $$("#provider button").forEach((b) => (b.onclick = () => { provider = b.dataset.p; $$("#provider button").forEach((x) => x.classList.toggle("active", x === b)); $("#imap-fields").classList.toggle("hidden", provider !== "imap"); }));
  $$("[data-mail-preset]").forEach((b) => (b.onclick = () => {
    const [ih, ip, sh, sp, sec, note] = MAIL_PRESETS[b.dataset.mailPreset];
    $("[data-path='mail.imap_host']").value = ih; $("[data-path='mail.imap_port']").value = ip; $("[data-path='mail.imap_ssl']").checked = true;
    $("[data-path='mail.smtp_host']").value = sh; $("[data-path='mail.smtp_port']").value = sp; $("[data-path='mail.smtp_security']").value = sec;
    $("#preset-note").classList.toggle("hidden", !note); $("#preset-note").innerHTML = `${icon("alert")}${esc(note)}`;
  }));
  const collect = (section) => {
    const out = {};
    $$(`[data-path^='${section}.']`).forEach((inp) => {
      const key = inp.dataset.path.split(".")[1];
      out[key] = inp.type === "checkbox" ? inp.checked : inp.dataset.type === "number" ? Number(inp.value) : inp.value;
    });
    if (section === "mail") out.provider = provider;
    return out;
  };
  $$("[data-save]").forEach((b) => (b.onclick = async () => {
    const section = b.dataset.save;
    setBusy(b, true, "Enregistrement…");
    try {
      await api("/api/settings", { method: "PUT", body: { [section]: collect(section) } });
      await refreshState();
      if (section === "mail") { S.folders = []; S.inbox = { ...S.inbox, items: [], selected: null }; S.priority = null; S.plan = null; loadTimeline(); renderScopebar(); }
      toast("Réglages enregistrés", "success");
    } catch (e) { fail(e); }
    setBusy(b, false);
  }));
  $("#test-llm").onclick = async (e) => {
    setBusy(e.currentTarget, true, "Test…");
    const out = $("#llm-test");
    try {
      const r = await api("/api/test/llm", { method: "POST", body: collect("llm") });
      $("#models").innerHTML = r.models.map((m) => `<option value="${esc(m)}">`).join("");
      out.innerHTML = `<div class="test-result ok">${icon("check")} Serveur joignable${r.models.length ? ` · ${r.models.length} modèle(s) : ${esc(r.models.slice(0, 8).join(", "))}${r.models.length > 8 ? "…" : ""}` : ""}${r.reply ? ` · réponse du modèle : « ${esc(r.reply.slice(0, 60))} »` : " · choisissez un modèle puis retestez"}</div>`;
    } catch (err) { out.innerHTML = `<div class="test-result ko">${esc(err.message)}</div>`; }
    setBusy(e.currentTarget, false);
  };
  $("#test-mail").onclick = async (e) => {
    setBusy(e.currentTarget, true, "Test…");
    const out = $("#mail-test");
    try {
      await api("/api/settings", { method: "PUT", body: { mail: collect("mail") } });
      const r = await api("/api/test/mail", { method: "POST" });
      out.innerHTML = `<div class="test-result ok">${icon("check")} Connexion réussie · ${r.folders} dossiers trouvés (réglages enregistrés)</div>`;
      await refreshState(); S.folders = []; loadTimeline();
    } catch (err) { out.innerHTML = `<div class="test-result ko">${esc(err.message)}</div>`; }
    setBusy(e.currentTarget, false);
  };
  $$("#theme button").forEach((b) => (b.onclick = async () => {
    $$("#theme button").forEach((x) => x.classList.toggle("active", x === b));
    applyTheme(b.dataset.t);
    await api("/api/settings", { method: "PUT", body: { theme: b.dataset.t } }).catch(fail);
    refreshState();
  }));
  $("#clear-ai").onclick = async () => {
    if (!(await modal({ title: "Vider le cache IA ?", body: "Les résumés, priorités et réponses mémorisés seront recalculés à la demande.", confirm: "Vider", danger: true }))) return;
    await api("/api/cache/clear-ai", { method: "POST" }).catch(fail);
    await refreshState(); renderSettings(); toast("Cache IA vidé", "success");
  };
  if (location.hash.includes("?")) {
    const target = location.hash.split("?")[1];
    if ($(`#s-${target}`)) $(`#s-${target}`).scrollIntoView();
  }
}

/* =====================================================================
   Raccourcis clavier
   ===================================================================== */
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  if (e.key === "Escape") { closeDrawer(); return; }
  if (S.route !== "inbox") return;
  const items = S.inbox.items;
  const idx = items.findIndex((m) => m.key === S.inbox.selected);
  const reader = $("#reader");
  if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); const n = items[Math.min(items.length - 1, idx + 1)]; if (n) { selectMessage(n.key); scrollToItem(n.key); } }
  else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); const n = items[Math.max(0, idx - 1)]; if (n) { selectMessage(n.key); scrollToItem(n.key); } }
  else if (e.key === "/") { e.preventDefault(); $("#q").focus(); }
  else if (reader && reader._actions) {
    if (e.key === "s") reader._actions.summary($("[data-act=summary]", reader));
    else if (e.key === "r") { e.preventDefault(); reader._actions.reply(); }
    else if (e.key === "u") reader._actions.seen();
  }
});
function scrollToItem(key) { const n = $$(".mail-item").find((x) => x.dataset.key === key); if (n) n.scrollIntoView({ block: "nearest" }); }

/* =====================================================================
   Démarrage
   ===================================================================== */
async function init() {
  $$("[data-icon]").forEach((x) => (x.innerHTML = icon(x.dataset.icon)));
  await refreshState();
  if (!S.state) { $("#view").innerHTML = emptyState("alert", "red", "Serveur injoignable", "Relancez Trieurmail puis rechargez la page."); return; }
  renderScopebar();
  window.addEventListener("hashchange", route);
  route();
  loadTimeline();
  setInterval(() => { if (document.visibilityState === "visible") refreshState(); }, 15000);
}
init();
