/* Auto Video Producer — studio frontend */
"use strict";

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = s => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

let STATE = {
  settings: null, ttsStatus: null, presets: [], scripts: [], projects: [],
  currentProject: null, currentSeg: null, uploadTTS: null, uploadAudio: null,
  pollTimer: null, libFilter: { q: "", kind: "", tag: "" },
};

async function api(path, opts = {}) {
  if (opts.json) {
    opts.body = JSON.stringify(opts.json);
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  }
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.status + " " + r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return r.json();
}

function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  $("#toast-zone").appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .4s"; setTimeout(() => t.remove(), 450); }, 4200);
}

/* ------------------------------------------------------------------ tabs */
$("#tabs").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  $$("#tabs button").forEach(x => x.classList.toggle("active", x === b));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === "view-" + b.dataset.view));
  if (b.dataset.view === "projects") loadProjects();
  if (b.dataset.view === "library") loadLibrary();
  if (b.dataset.view === "templates") loadTemplates();
  if (b.dataset.view === "presets") loadPresetsUI();
  if (b.dataset.view === "settings") buildSettingsUI();
  if (b.dataset.view === "timeline") loadTimelineProjects();
});
function goto(view) { $$("#tabs button").find(b => b.dataset.view === view).click(); }

/* ------------------------------------------------------------------ produce */
const WF = ["LOAD SCRIPT", "NARRATION", "ANALYZE AUDIO", "SEGMENT", "SELECT ASSETS",
  "BUILD TIMELINE", "SUBTITLES", "MOTION GRAPHICS", "TRANSITIONS", "GLOBAL FX",
  "MUSIC", "RENDER", "EXPORT MP4"];
function renderWF(activeIdx = -1, doneUpTo = -1) {
  $("#wf-steps").innerHTML = WF.map((w, i) => {
    const cls = i <= doneUpTo ? "done" : (i === activeIdx ? "hot" : "");
    return `<span class="wf-step ${cls}">${i + 1}. ${w}</span>` + (i < WF.length - 1 ? '<span class="wf-arrow">▸</span>' : "");
  }).join("");
}
renderWF();

async function loadScripts() {
  const d = await api("/api/scripts");
  STATE.scripts = d.scripts;
  $("#script-select").innerHTML = '<option value="">— choose —</option>' +
    d.scripts.map(s => `<option value="${esc(s.name)}">${esc(s.name)} (${s.words}w)</option>`).join("");
}
$("#script-select").addEventListener("change", async e => {
  if (!e.target.value) return;
  const d = await api("/api/scripts/" + encodeURIComponent(e.target.value));
  $("#script-text").value = d.text;
  scriptStats();
});
$("#script-file").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  $("#script-text").value = await f.text();
  if (!$("#proj-title").value) $("#proj-title").value = f.name.replace(/\.[^.]+$/, "");
  scriptStats();
});
function scriptStats() {
  const t = $("#script-text").value;
  const w = t.trim() ? t.trim().split(/\s+/).length : 0;
  $("#script-stats").textContent = w ? `${w} words · ~${fmt(w / 2.55)} est. narration · target 550–700 words for 4–5 min` : "—";
}
$("#script-text").addEventListener("input", scriptStats);
$("#btn-save-script").addEventListener("click", async () => {
  const t = $("#script-text").value.trim(); if (!t) return toast("Script is empty", "err");
  const name = $("#proj-title").value || "script_" + Date.now();
  const fd = new FormData();
  fd.append("name", name); fd.append("text", t);
  await api("/api/scripts", { method: "POST", body: fd });
  toast(`Saved script "${name}"`); loadScripts();
});

/* segmentation preview */
$("#btn-seg-preview").addEventListener("click", async () => {
  const t = $("#script-text").value.trim();
  if (!t) return toast("Load a script first", "err");
  const el = $("#seg-preview");
  el.innerHTML = '<span class="spin"></span> analyzing…';
  try {
    const d = await api("/api/segmentation/preview", { method: "POST", json: { text: t } });
    el.innerHTML = `<div class="small dim" style="margin-bottom:6px">${d.segments.length} semantic segments · estimated timings</div>` +
      d.segments.slice(0, 40).map(s =>
        `<div style="display:flex; gap:10px; font-size:11.5px; padding:3px 0; border-bottom:1px solid var(--line)">
          <span class="tag-role r-${s.role}" style="width:130px; flex:none">${s.role.replace(/_/g, " ")}</span>
          <span class="dim" style="flex:1">${esc(s.text.slice(0, 90))}${s.text.length > 90 ? "…" : ""}</span>
          <span class="faint mono" style="flex:none">${(s.mg || []).join(",")}</span>
        </div>`).join("");
  } catch (e) { el.innerHTML = `<div class="small" style="color:var(--red)">${esc(e.message)}</div>`; }
});

/* narration uploads */
function wireDrop(boxId, inputId, nameId, onFile) {
  const box = $(boxId);
  box.addEventListener("click", () => $(inputId).click());
  box.addEventListener("dragover", e => { e.preventDefault(); box.classList.add("drag"); });
  box.addEventListener("dragleave", () => box.classList.remove("drag"));
  box.addEventListener("drop", e => {
    e.preventDefault(); box.classList.remove("drag");
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
  const inp = document.createElement("input");
  inp.type = "file"; inp.id = inputId.slice(1); inp.style.display = "none";
  box.appendChild(inp);
  inp.addEventListener("change", e => { if (e.target.files[0]) onFile(e.target.files[0]); });
}
wireDrop("#box-tts-txt", "#in-tts-txt", "#tts-txt-name", f => {
  STATE.uploadTTS = f;
  $("#tts-txt-name").textContent = f.name + " (" + Math.round(f.size / 1024) + " KB)";
  $("#box-tts-txt").classList.add("loaded");
  $('[name=narrsrc][value=uploaded]').checked = true;
  narrStatus();
});
wireDrop("#box-tts-audio", "#in-tts-audio", "#tts-audio-name", f => {
  STATE.uploadAudio = f;
  $("#tts-audio-name").textContent = f.name + " (" + Math.round(f.size / 1024) + " KB)";
  $("#box-tts-audio").classList.add("loaded");
  $('[name=narrsrc][value=uploaded]').checked = true;
  narrStatus();
});
function narrStatus() {
  const src = $('[name=narrsrc]:checked').value;
  const el = $("#narr-status");
  const ttsProvider = STATE.settings?.tts?.provider || "espeak_offline";
  const provLabel = { espeak_offline: "offline espeak", timed_placeholder: "TIMING PLACEHOLDER", openai: "OpenAI API", elevenlabs: "ElevenLabs API", generic_http: "custom HTTP", piper_local: "Piper local" }[ttsProvider] || ttsProvider;
  if (src === "uploaded") {
    const a = STATE.uploadAudio, t = STATE.uploadTTS;
    el.textContent = "✓ Uploaded / Pre-generated selected — " +
      (a ? `audio master: ${a.name}` : t ? `TTS package: ${t.name}` : "no file loaded yet");
    el.className = "note blue small";
  } else if (src === "project_existing") {
    el.textContent = "✓ Existing project narration — will never call TTS if narration exists";
    el.className = "note blue small";
  } else {
    el.textContent = `Narration: TTS API (${provLabel})${STATE.ttsStatus && !STATE.ttsStatus.key_present && ["openai", "elevenlabs"].includes(ttsProvider) ? " — MISSING API KEY (set " + STATE.ttsStatus.key_var + ")" : ""}`;
    el.className = "note small";
  }
  const pill = $("#pill-narration");
  pill.textContent = "TTS: " + provLabel;
  pill.className = "pill " + (STATE.ttsStatus && ["openai", "elevenlabs"].includes(ttsProvider) && !STATE.ttsStatus.key_present ? "warn" : "ok");
}
$$("#narr-radios input").forEach(r => r.addEventListener("change", narrStatus));

/* generate */
$("#btn-generate").addEventListener("click", async () => {
  const script = $("#script-text").value.trim();
  if (!script) return toast("Load a script first", "err");
  const src = $('[name=narrsrc]:checked').value;
  try {
    let pid;
    if (STATE.currentProject && $("#proj-title").value === STATE.currentProject.title) {
      pid = STATE.currentProject.project_id;
      await api(`/api/projects/${pid}/script`, { method: "POST", json: { script } });
    } else {
      const d = await api("/api/projects", { method: "POST", json: {
        title: $("#proj-title").value || "untitled_" + Date.now().toString(36),
        script, narration_source: src, preset: $("#preset-select").value || null, save_script: true } });
      pid = d.project.project_id;
    }
    if (src === "uploaded") {
      if (STATE.uploadAudio) {
        const fd = new FormData(); fd.append("file", STATE.uploadAudio); fd.append("kind", "audio");
        await api(`/api/projects/${pid}/narration_upload`, { method: "POST", body: fd });
      }
      if (STATE.uploadTTS) {
        const fd = new FormData(); fd.append("file", STATE.uploadTTS); fd.append("kind", "text");
        await api(`/api/projects/${pid}/narration_upload`, { method: "POST", body: fd });
      }
      if (!STATE.uploadAudio && !STATE.uploadTTS) toast("No narration file loaded — falling back to TTS generation", "warn");
    }
    await api(`/api/projects/${pid}/generate`, { method: "POST", json: { narration_source: src } });
    STATE.currentProject = await api("/api/projects/" + pid);
    $("#current-project-note").textContent = `Project: ${STATE.currentProject.title} (${pid})`;
    watchProgress(pid, true);
    toast("Generation started");
  } catch (e) { toast(e.message, "err"); }
});

$("#btn-render-only").addEventListener("click", async () => {
  const p = STATE.currentProject;
  if (!p) return toast("No project selected — generate once first", "err");
  try {
    await api(`/api/projects/${p.project_id}/render`, { method: "POST", json: {} });
    watchProgress(p.project_id, false);
  } catch (e) { toast(e.message, "err"); }
});

function watchProgress(pid, fullPipeline) {
  if (STATE.pollTimer) clearInterval(STATE.pollTimer);
  renderWF(0, -1);
  STATE.pollTimer = setInterval(async () => {
    let p;
    try { p = await api(`/api/projects/${pid}/progress`); } catch (e) { return; }
    const log = $("#log");
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
    log.innerHTML = p.lines.map(l => {
      const cls = l.includes("ERROR") ? "err" : l.includes("WARNING") ? "warn" :
        /done:|render complete|assembled|narration:|segmentation:|timeline:/.test(l) ? "ok" : "";
      return `<div class="${cls}">${esc(l)}</div>`;
    }).join("");
    if (atBottom) log.scrollTop = log.scrollHeight;
    $("#progress-stage").textContent = p.stage || "";
    renderWF(-1, pipelineStageIndex(p.lines));
    if (!p.running && p.done) {
      clearInterval(STATE.pollTimer); STATE.pollTimer = null;
      $("#btn-generate").disabled = false;
      if (p.ok) {
        renderWF(-1, WF.length - 1);
        toast("Video ready", "");
        const proj = await api("/api/projects/" + pid);
        STATE.currentProject = proj;
        showResult(proj);
      } else { toast("Generation failed: " + (p.error || "?"), "err"); renderWF(-1, -1); }
    }
  }, 1200);
}
function pipelineStageIndex(lines) {
  const stages = ["narration:", "audio:", "segmentation:", "timeline:", "assembled", "final pass", "render complete"];
  let last = -1;
  for (const l of lines || []) for (let i = 0; i < stages.length; i++)
    if (l.includes(stages[i])) last = Math.max(last, i);
  return last;
}

function showResult(proj) {
  const panel = $("#result-panel");
  panel.style.display = "block";
  const v = $("#result-video");
  v.src = proj.final_url + "?t=" + Date.now();
  const rr = proj.render_result || {};
  $("#result-meta").innerHTML =
    `<span>DURATION <b class="mono">${fmt(rr.duration || proj.duration)}</b></span>
     <span>RES <b class="mono">${rr.width}×${rr.height}</b></span>
     <span>SIZE <b class="mono">${rr.size_mb || "—"} MB</b></span>
     <span>SEGMENTS <b class="mono">${proj.segments}</b></span>
     <span>REVIEW FLAGS <b class="mono" style="color:${proj.review_flags ? "var(--amber)" : "var(--blue)"}">${proj.review_flags}</b></span>
     <span>NARRATION <b class="mono">${esc(proj.narration_provider || "—")}</b></span>`;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
$("#btn-open-timeline").addEventListener("click", () => goto("timeline"));
$("#btn-copy-review").addEventListener("click", async () => {
  const p = STATE.currentProject; if (!p) return;
  const flags = (p.timeline?.segments || []).filter(s => s.human_review_reason)
    .map(s => `${s.segment_id} [${s.role}] ${s.human_review_reason}`).join("\n");
  await navigator.clipboard.writeText(flags || "no flags");
  toast("Review flags copied");
});

/* ------------------------------------------------------------------ projects */
async function loadProjects() {
  const d = await api("/api/projects");
  STATE.projects = d.projects;
  $("#proj-grid").innerHTML = d.projects.length ? d.projects.map(p => `
    <div class="proj-card" data-pid="${esc(p.project_id)}">
      <div class="thumb" style="${p.has_final ? "" : "display:flex;align-items:center;justify-content:center;color:var(--bone-faint);font-size:11px;letter-spacing:.2em"}${p.has_final ? `background-image:url('${p.poster_url}')` : ""}">${p.has_final ? "" : "NO RENDER YET"}
        <span class="badge chip ${p.narration_source === "uploaded" ? "blue" : "amber"}">${esc((p.narration_provider || p.narration_source || "?").replace("_", " "))}</span>
      </div>
      <div class="body">
        <div class="title">${esc(p.title)}</div>
        <div class="meta">
          <span>${fmt(p.duration)}</span><span>${p.segments} seg</span>
          <span style="color:${p.review_flags ? "var(--amber)" : "var(--blue)"}">${p.review_flags} flags</span>
          ${p.preset ? `<span>${esc(p.preset)}</span>` : ""}
        </div>
      </div>
    </div>`).join("") : '<div class="ghost-note">No projects yet — produce your first video.</div>';
  $$("#proj-grid .proj-card").forEach(c => c.addEventListener("click", () => openProject(c.dataset.pid)));
}
async function openProject(pid) {
  STATE.currentProject = await api("/api/projects/" + pid);
  $("#proj-title").value = STATE.currentProject.title;
  $("#script-text").value = STATE.currentProject.script || "";
  scriptStats();
  $("#current-project-note").textContent = `Project: ${STATE.currentProject.title} (${pid})`;
  if (STATE.currentProject.has_final) showResult(STATE.currentProject);
  goto("timeline");
}

/* ------------------------------------------------------------------ timeline */
async function loadTimelineProjects() {
  const d = await api("/api/projects");
  $("#tl-project").innerHTML = '<option value="">— choose project —</option>' +
    d.projects.map(p => `<option value="${esc(p.project_id)}" ${STATE.currentProject?.project_id === p.project_id ? "selected" : ""}>${esc(p.title)}</option>`).join("");
  if (STATE.currentProject) renderTimeline(STATE.currentProject);
}
$("#tl-project").addEventListener("change", async e => {
  if (!e.target.value) return;
  STATE.currentProject = await api("/api/projects/" + e.target.value);
  renderTimeline(STATE.currentProject);
});
async function renderTimeline(proj) {
  if (!proj.timeline) { $("#tl-title").textContent = proj.title + " — no timeline yet (generate first)"; $("#tl-strip").innerHTML = ""; return; }
  $("#tl-title").textContent = proj.title;
  const segs = proj.timeline.segments;
  $("#tl-stats").textContent = `${segs.length} segments · ${fmt(segs[segs.length - 1].end)} · ${proj.timeline.review_flags} review flags · narration: ${proj.narration_provider}`;
  $("#tl-strip").innerHTML = segs.map((s, i) => `
    <div class="tl-cell ${s.asset_id ? "" : "no-asset"}" data-sid="${esc(s.segment_id)}" title="${esc(s.voiceover_summary)}">
      ${s.human_review_reason ? '<span class="flag" title="needs review"></span>' : ""}
      ${s.preview_url ? `<img src="${s.preview_url}" loading="lazy" onerror="this.style.display='none'">` : ""}
      <span class="lbl"><span>${fmt(s.start)}</span><span>${s.role.split("_")[0]}</span></span>
    </div>`).join("");
  $$("#tl-strip .tl-cell").forEach(c => c.addEventListener("click", () => selectSegment(c.dataset.sid)));
  const v = $("#tl-video");
  if (proj.has_final && !v.src.includes(proj.project_id)) v.src = proj.final_url;
  selectSegment(segs[0]?.segment_id);
}
async function selectSegment(sid) {
  const proj = STATE.currentProject;
  const s = proj.timeline.segments.find(x => x.segment_id === sid);
  if (!s) return;
  STATE.currentSeg = s;
  $$("#tl-strip .tl-cell").forEach(c => c.classList.toggle("sel", c.dataset.sid === sid));
  const v = $("#tl-video"); if (v.src) { v.currentTime = Math.max(0, s.start + 0.2); }
  const assets = await api("/api/assets?limit=400");
  $("#seg-info").innerHTML = `
    <h2>${esc(s.segment_id)} · <span class="tag-role r-${s.role}">${s.role.replace(/_/g, " ")}</span></h2>
    <div class="seg-text">"${esc(s.text)}"</div>
    <dl class="kv">
      <dt>time</dt><dd class="mono">${s.start.toFixed(2)} → ${s.end.toFixed(2)}  (${s.duration.toFixed(2)}s)</dd>
      <dt>emotion</dt><dd>${esc(s.emotion)}</dd>
      <dt>concepts</dt><dd>${(s.concepts || []).map(c => `<span class="chip">${esc(c)}</span>`).join("") || "—"}</dd>
      <dt>visual intent</dt><dd>${esc(s.visual_intent?.motif || "—")} · tint ${esc(s.visual_intent?.tint)}</dd>
      <dt>asset</dt><dd>${s.asset_name ? esc(s.asset_name) : `<span style="color:var(--amber)">${esc(s.fallback || "none")}</span>`}</dd>
      <dt>motion</dt><dd class="mono">${esc(s.motion?.type || "static")} ${(s.motion?.amount || 0) ? (s.motion.amount * 100).toFixed(1) + "%" : ""}</dd>
      <dt>transition</dt><dd class="mono">${esc(s.transition?.type)} ${s.transition?.duration ? s.transition.duration + "s" : ""}</dd>
      <dt>evidence</dt><dd>${s.evidence_status?.has_source ? "source present" + (s.evidence_status?.meta ? ` — ${esc(s.evidence_status.meta.author || "")} ${esc(s.evidence_status.meta.year || "")}` : "") : "—"}</dd>
      <dt>music</dt><dd>${esc(s.music?.mood)}</dd>
      <dt>sfx</dt><dd>${s.sfx ? esc(s.sfx.asset_id) : "—"}</dd>
      <dt>confidence</dt><dd class="mono">${s.confidence}</dd>
      <dt>review</dt><dd style="color:${s.human_review_reason ? "var(--amber)" : "var(--blue)"}">${esc(s.human_review_reason || "clean")}</dd>
      ${s.timing_mode === "estimated" ? '<dt>timing</dt><dd style="color:var(--amber)">estimated (no word timestamps)</dd>' : ""}
    </dl>`;
  const candidates = assets.assets.filter(a => a.type === "image" || a.type === "video").slice(0, 200);
  $("#seg-edit").innerHTML = `
    <h2>Advanced edit</h2>
    <label class="f"><span>Replace visual asset</span>
      <select id="seg-asset-sel">
        <option value="">— keep current (${esc(s.asset_name || s.fallback || "none")}) —</option>
        ${candidates.map(a => `<option value="${esc(a.asset_id)}">${esc(a.filename)} · ${a.type} · ${esc((a.semantic_tags || []).slice(0, 3).join("/"))}</option>`).join("")}
      </select></label>
    <div class="grid2">
      <label class="f"><span>Motion</span>
        <select id="seg-motion-sel">
          ${["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "kenburns", "static"].map(m => `<option ${s.motion?.type === m ? "selected" : ""}>${m}</option>`).join("")}
        </select></label>
      <label class="f"><span>Transition in</span>
        <select id="seg-tr-sel">
          ${["hold", "hard_cut", "fade", "dissolve", "zoom", "slide", "blur", "flash", "light_leak", "glitch", "evidence_pivot", "fade_from_black"].map(m => `<option ${s.transition?.type === m ? "selected" : ""}>${m}</option>`).join("")}
        </select></label>
    </div>
    <label class="f" style="display:flex; gap:8px; align-items:center">
      <input type="checkbox" id="seg-locked" ${s.locked ? "checked" : ""}> <span>Locked (never auto-regenerated)</span></label>
    <div style="display:flex; gap:8px; flex-wrap:wrap">
      <button class="btn small" id="btn-seg-save">Apply</button>
      <button class="btn small amber" id="btn-seg-regen">⟳ Regenerate scene</button>
      <button class="btn small" id="btn-seg-clear-asset">Use typography card</button>
    </div>
    <div class="note small">Changes apply to the stored timeline. Use “Render video” to rebuild the MP4 (no TTS, no re-planning).</div>`;
  $("#btn-seg-save").addEventListener("click", async () => {
    const patch = {};
    const assetSel = $("#seg-asset-sel").value;
    if (assetSel) patch.asset_id = assetSel;
    patch.motion = { ...(s.motion || {}), type: $("#seg-motion-sel").value };
    patch.transition = { ...(s.transition || {}), type: $("#seg-tr-sel").value };
    patch.locked = $("#seg-locked").checked;
    await api(`/api/projects/${proj.project_id}/segments/${sid}`, { method: "PATCH", json: patch });
    toast("Segment updated");
    STATE.currentProject = await api("/api/projects/" + proj.project_id);
    renderTimeline(STATE.currentProject);
  });
  $("#btn-seg-regen").addEventListener("click", async () => {
    await api(`/api/projects/${proj.project_id}/regenerate_scene/${sid}`, { method: "POST", json: {} });
    toast("Scene regenerated");
    STATE.currentProject = await api("/api/projects/" + proj.project_id);
    renderTimeline(STATE.currentProject);
  });
  $("#btn-seg-clear-asset").addEventListener("click", async () => {
    await api(`/api/projects/${proj.project_id}/segments/${sid}`, { method: "PATCH", json: { asset_id: null, fallback: "__typography__" } });
    toast("Segment set to typography card");
    STATE.currentProject = await api("/api/projects/" + proj.project_id);
    renderTimeline(STATE.currentProject);
  });
}
$("#btn-rebuild-tl").addEventListener("click", async () => {
  const p = STATE.currentProject; if (!p) return;
  await api(`/api/projects/${p.project_id}/rebuild_timeline`, { method: "POST", json: {} });
  STATE.currentProject = await api("/api/projects/" + p.project_id);
  renderTimeline(STATE.currentProject);
  toast("Timeline rebuilt (kept narration)");
});
$("#btn-render-tl").addEventListener("click", async () => {
  const p = STATE.currentProject; if (!p) return;
  await api(`/api/projects/${p.project_id}/render`, { method: "POST", json: {} });
  goto("produce"); watchProgress(p.project_id, false);
});

/* ------------------------------------------------------------------ library */
async function loadLibrary() {
  const { q, kind, tag } = STATE.libFilter;
  const d = await api(`/api/assets?q=${encodeURIComponent(q)}&kind=${kind}&tag=${encodeURIComponent(tag)}&limit=500`);
  $("#lib-tag").innerHTML = '<option value="">all tags</option>' +
    d.all_tags.map(t => `<option ${t === tag ? "selected" : ""}>${esc(t)}</option>`).join("");
  $("#asset-grid").innerHTML = d.assets.map(a => `
    <div class="asset-card ${a.enabled ? "" : "disabled"}" data-id="${esc(a.asset_id)}">
      <div class="im ${a.type === "music" || a.type === "sfx" ? "audio" : ""}" style="${["image", "video"].includes(a.type) ? `background-image:url('/api/assets/${esc(a.asset_id)}/thumb')` : ""}">${a.type === "music" ? "♪ MUSIC" : a.type === "sfx" ? "SFX" : ""}</div>
      <div class="body">
        <div class="name" title="${esc(a.filename)}">${esc(a.filename)}</div>
        <div class="meta">${a.type}${a.duration ? " · " + a.duration.toFixed(1) + "s" : ""}${a.width ? " · " + a.width + "×" + a.height : ""} · used ${a.usage_count}×</div>
        <div>${(a.semantic_tags || []).slice(0, 4).map(t => `<span class="chip blue">${esc(t)}</span>`).join("")}${(a.tags || []).filter(t => !(a.semantic_tags || []).includes(t)).slice(0, 3).map(t => `<span class="chip">${esc(t)}</span>`).join("")}</div>
        <div style="margin-top:6px; display:flex; gap:6px">
          <button class="btn small" data-act="tag">+ tag</button>
          <button class="btn small" data-act="toggle">${a.enabled ? "disable" : "enable"}</button>
        </div>
      </div>
    </div>`).join("");
  $("#lib-count").textContent = `${d.total} assets shown · semantic matching uses semantic_tags (blue) + tags`;
  $$("#asset-grid .asset-card").forEach(card => {
    const id = card.dataset.id;
    $(".im", card)?.addEventListener("click", () => window.open(`/api/assets/${id}`, "_blank"));
    $('[data-act=tag]', card)?.addEventListener("click", async () => {
      const t = prompt("Add tag (also added to semantic_tags):");
      if (!t) return;
      const a = await api("/api/assets/" + id);
      await api("/api/assets/" + id, { method: "PATCH", json: {
        tags: [...new Set([...(a.tags || []), t.trim()])],
        semantic_tags: [...new Set([...(a.semantic_tags || []), t.trim().toLowerCase()])] } });
      loadLibrary(); toast("Tagged " + t);
    });
    $('[data-act=toggle]', card)?.addEventListener("click", async () => {
      await api("/api/assets/" + id, { method: "PATCH", json: { enabled: card.className.includes("disabled") } });
      loadLibrary();
    });
  });
}
$("#lib-q").addEventListener("change", e => { STATE.libFilter.q = e.target.value; loadLibrary(); });
$("#lib-kind").addEventListener("change", e => { STATE.libFilter.kind = e.target.value; loadLibrary(); });
$("#lib-tag").addEventListener("change", e => { STATE.libFilter.tag = e.target.value; loadLibrary(); });
$("#btn-lib-scan").addEventListener("click", async () => {
  toast("Scanning library…");
  const d = await api("/api/library/scan", { method: "POST" });
  toast(`Scanned ${d.total} assets in ${d.seconds}s`); updateLibraryPill(d.total); loadLibrary();
});
$("#lib-upload").addEventListener("change", async e => {
  const files = Array.from(e.target.files); if (!files.length) return;
  const fd = new FormData();
  files.forEach(f => fd.append("files", f));
  fd.append("category", $("#lib-upload-cat").value);
  const d = await api("/api/library/upload", { method: "POST", body: fd });
  toast(`Uploaded ${d.saved.length} files`); loadLibrary();
});
async function updateLibraryPill(n) {
  if (!n) { try { n = (await api("/api/assets?limit=1")).total; } catch (e) {} }
  $("#pill-library").textContent = "Library: " + (n || "—") + " assets";
}

/* ------------------------------------------------------------------ templates */
async function loadTemplates() {
  const d = await api("/api/motion_graphics/templates");
  $("#tpl-grid").innerHTML = d.templates.map(t => `
    <div class="tpl-card">
      <img loading="lazy" src="/api/motion_graphics/preview/${t}?title=Sample headline for this card&kicker=${encodeURIComponent(t.replace(/_/g, " "))}" alt="${t}">
      <div class="name">${t}</div>
    </div>`).join("");
}

/* ------------------------------------------------------------------ presets */
async function loadPresets() {
  const d = await api("/api/presets");
  STATE.presets = d.presets;
  $("#preset-select").innerHTML = '<option value="">(default settings)</option>' +
    d.presets.map(p => `<option value="${esc(p.name)}">${esc(p.name)}</option>`).join("");
}
async function loadPresetsUI() {
  await loadPresets();
  $("#preset-list").innerHTML = STATE.presets.map(p => `
    <div class="row" style="align-items:center; padding:10px 0; border-bottom:1px solid var(--line)">
      <div style="flex:2">
        <div style="font-weight:700">${esc(p.name)}</div>
        <div class="dim small">${esc(p.description)}</div>
      </div>
      <button class="btn small" data-apply="${esc(p.name)}">Apply</button>
    </div>`).join("");
  $$("#preset-list [data-apply]").forEach(b => b.addEventListener("click", async () => {
    await api(`/api/presets/${encodeURIComponent(b.dataset.apply)}/apply`, { method: "POST" });
    await loadSettings();
    toast(`Preset "${b.dataset.apply}" applied`);
  }));
}
$("#btn-preset-save").addEventListener("click", async () => {
  const name = $("#preset-name").value.trim();
  if (!name) return toast("Name your preset", "err");
  await api("/api/presets", { method: "POST", json: {
    name, description: $("#preset-desc").value || "Custom preset",
    render: STATE.settings.render, subtitles: STATE.settings.subtitles,
    music: STATE.settings.music, transitions: STATE.settings.transitions,
    effects: STATE.settings.effects, motion_graphics: STATE.settings.motion_graphics,
    asset_rules: { repetition: STATE.settings.repetition, scoring: STATE.settings.scoring },
    tts: STATE.settings.tts } });
  toast(`Preset "${name}" saved`); loadPresets();
});

/* ------------------------------------------------------------------ settings */
async function loadSettings() {
  const d = await api("/api/settings");
  STATE.settings = d.settings; STATE.ttsStatus = d.tts_status;
  narrStatus();
  return d;
}
const SET_SCHEMA = [
  { title: "TTS engine", path: "tts", fields: [
    { k: "provider", t: "select", opts: ["espeak_offline", "openai", "elevenlabs", "generic_http", "piper_local", "timed_placeholder"] },
    { k: "endpoint", t: "text", ph: "https://… (for openai/generic_http)" },
    { k: "model", t: "text" }, { k: "voice", t: "text" },
    { k: "speed", t: "num", step: 0.05 }, { k: "pitch", t: "num", step: 0.5 },
    { k: "espeak_voice", t: "text" }, { k: "espeak_rate", t: "num" },
    { k: "piper_model", t: "text" },
    { k: "env_key_var", t: "text", note: "API key is read from this ENV VAR — never stored here." },
  ]},
  { title: "Render", path: "render", fields: [
    { k: "resolution", t: "select", opts: ["1920x1080", "1280x720", "1080x1920", "720x1280", "1080x1080"] },
    { k: "fps", t: "select", opts: [24, 30, 60] },
    { k: "crf", t: "range", min: 14, max: 30 }, { k: "preset", t: "select", opts: ["ultrafast", "veryfast", "medium", "slow"] },
    { k: "transition_mode", t: "select", opts: ["filter", "xfade"] },
  ]},
  { title: "Subtitles", path: "subtitles", fields: [
    { k: "mode", t: "select", opts: ["selective", "full", "off"] },
    { k: "animation", t: "select", opts: ["fade", "pop", "typewriter", "slide", "word_highlight"] },
    { k: "position", t: "select", opts: ["bottom", "top", "center", "custom"] },
    { k: "font", t: "text" }, { k: "size", t: "num" }, { k: "max_chars", t: "num" }, { k: "max_lines", t: "num" },
    { k: "bold", t: "bool" }, { k: "accent_colors", t: "bool" },
    { k: "background", t: "bool" }, { k: "background_opacity", t: "range", min: 0, max: 1, step: 0.05 },
  ]},
  { title: "Music & ducking", path: "music", fields: [
    { k: "mode", t: "select", opts: ["auto", "fixed", "random", "off"] },
    { k: "fixed_track", t: "text" }, { k: "base_volume", t: "range", min: 0.05, max: 0.8, step: 0.01 },
    { k: "fade_in", t: "num" }, { k: "fade_out", t: "num" },
    { k: "ducking.enabled", t: "bool" }, { k: "ducking.threshold", t: "num", step: 0.005 }, { k: "ducking.ratio", t: "num" },
  ]},
  { title: "Global effects", path: "effects", fields: [
    { k: "grain.enabled", t: "bool" }, { k: "grain.opacity", t: "range", min: 0, max: 0.4, step: 0.01 },
    { k: "vignette.enabled", t: "bool" }, { k: "vignette.opacity", t: "range", min: 0, max: 1, step: 0.05 },
    { k: "dust.enabled", t: "bool" }, { k: "letterbox.enabled", t: "bool" }, { k: "letterbox.ratio", t: "num", step: 0.01 },
    { k: "scanlines.enabled", t: "bool" },
  ]},
  { title: "Transitions (weighted pool)", path: "transitions", fields: [
    ...["hard_cut", "fade", "dissolve", "zoom", "slide", "blur", "flash", "glitch", "light_leak", "evidence_pivot"].map(w => ({ k: "weights." + w, t: "num" })),
    { k: "max_duration", t: "num", step: 0.1 },
  ]},
  { title: "Asset scoring weights", path: "scoring", fields: [
    { k: "semantic_match", t: "num", step: 0.05 }, { k: "scene_match", t: "num", step: 0.05 },
    { k: "format_match", t: "num", step: 0.05 }, { k: "duration_match", t: "num", step: 0.05 },
    { k: "diversity", t: "num", step: 0.05 }, { k: "quality", t: "num", step: 0.01 },
    { k: "recent_use_penalty", t: "num", step: 0.05 }, { k: "reuse_penalty", t: "num", step: 0.05 },
  ]},
  { title: "Repetition control", path: "repetition", fields: [
    { k: "min_gap_segments", t: "num" }, { k: "max_reuse", t: "num" }, { k: "same_category_limit", t: "num" },
  ]},
  { title: "Motion graphics", path: "motion_graphics", fields: [
    { k: "enabled", t: "bool" }, { k: "min_gap_seconds", t: "num" }, { k: "max_per_video", t: "num" },
  ]},
  { title: "Sound effects", path: "sfx", fields: [
    { k: "enabled", t: "bool" }, { k: "volume", t: "range", min: 0, max: 1, step: 0.05 }, { k: "min_gap_seconds", t: "num" },
  ]},
];
function getp(obj, path) { return path.split(".").reduce((o, k) => o?.[k], obj); }
function setp(obj, path, v) {
  const ks = path.split("."); let o = obj;
  for (let i = 0; i < ks.length - 1; i++) { o[ks[i]] = o[ks[i]] ?? {}; o = o[ks[i]]; }
  o[ks[ks.length - 1]] = v;
}
function buildSettingsUI() {
  if (!STATE.settings) return;
  $("#settings-grid").innerHTML = SET_SCHEMA.map(group => `
    <div class="panel"><h2>${group.title}</h2>
      ${group.fields.map(f => {
        const v = getp(STATE.settings, group.path + "." + f.k);
        const id = `set-${group.path}-${f.k.replace(/\./g, "-")}`;
        let inp;
        if (f.t === "select") inp = `<select id="${id}">${f.opts.map(o => `<option ${String(o) === String(v) ? "selected" : ""}>${o}</option>`).join("")}</select>`;
        else if (f.t === "range") inp = `<input type="range" id="${id}" min="${f.min}" max="${f.max}" step="${f.step || 0.01}" value="${v}">`;
        else if (f.t === "bool") return `<label class="f" style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="${id}" ${v ? "checked" : ""}><span>${f.k}</span></label>`;
        else if (f.t === "num") inp = `<input type="number" id="${id}" step="${f.step || 1}" value="${v}">`;
        else inp = `<input type="text" id="${id}" value="${esc(v ?? "")}" placeholder="${f.ph || ""}">`;
        return `<label class="f"><span>${f.k}</span>${inp}</label>`;
      }).join("")}
    </div>`).join("") +
    `<div class="panel"><h2>Editing rhythm (seconds per role)</h2>` +
    Object.entries(STATE.settings.rhythm).map(([role, rng]) => `
      <div class="rhythm-row"><span class="dim">${role}</span>
        <input type="number" step="0.1" id="rhythm-${role}-min" value="${rng[0]}">
        <input type="number" step="0.1" id="rhythm-${role}-max" value="${rng[1]}">
      </div>`).join("") + `</div>`;
}
$("#btn-settings-save").addEventListener("click", async () => {
  const patch = {};
  for (const group of SET_SCHEMA) {
    for (const f of group.fields) {
      const id = `set-${group.path}-${f.k.replace(/\./g, "-")}`;
      const el = $("#" + id); if (!el) continue;
      let v;
      if (f.t === "bool") v = el.checked;
      else if (f.t === "num") v = parseFloat(el.value);
      else if (f.t === "select" && ["fps"].includes(f.k.split(".").pop())) v = parseInt(el.value);
      else v = el.value;
      setp(patch, group.path + "." + f.k, v);
    }
  }
  patch.rhythm = {};
  Object.keys(STATE.settings.rhythm).forEach(role => {
    patch.rhythm[role] = [parseFloat($(`#rhythm-${role}-min`).value), parseFloat($(`#rhythm-${role}-max`).value)];
  });
  await api("/api/settings", { method: "POST", json: patch });
  await loadSettings();
  toast("Settings saved — every future video uses them");
});
$("#btn-tts-test").addEventListener("click", async () => {
  $("#tts-test-result").textContent = "synthesizing…";
  try {
    const d = await api("/api/tts/test", { method: "POST", json: {} });
    $("#tts-test-result").innerHTML = d.placeholder
      ? `<span style="color:var(--amber)">placeholder ${d.duration.toFixed(1)}s — configure a real provider</span>`
      : `<a href="${d.url}" target="_blank" style="color:var(--blue)">▶ play test (${d.duration.toFixed(1)}s, ${d.provider})</a>`;
  } catch (e) { $("#tts-test-result").textContent = "failed: " + e.message; }
});

/* ------------------------------------------------------------------ boot */
(async function boot() {
  try {
    await loadSettings();
    await loadPresets();
    await loadScripts();
    updateLibraryPill();
    renderWF();
    const projList = await api("/api/projects");
    if (projList.projects.length) {
      STATE.currentProject = await api("/api/projects/" + projList.projects[0].project_id);
      $("#current-project-note").textContent = `Project: ${STATE.currentProject.title} (${STATE.currentProject.project_id})`;
      if (projList.projects[0].has_final) showResult(STATE.currentProject);
    }
  } catch (e) {
    toast("Boot warning: " + e.message, "err");
  }
})();
