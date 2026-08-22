/* =========================================================================
   BhashaSetu - bundled UI logic (vanilla JS, no dependencies)
   Talks to the same FastAPI backend as the React frontend.
   ========================================================================= */
(() => {
  'use strict';

  const API = '/api';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // -- HTTP helpers -----------------------------------------------------------
  async function http(path, opts = {}) {
    const res = await fetch(API + path, {
      headers: opts.body && !(opts.body instanceof FormData)
        ? { 'Content-Type': 'application/json' } : undefined,
      ...opts,
    });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try { const d = await res.json(); detail = d.detail || detail; } catch {}
      throw new Error(detail);
    }
    return res.status === 204 ? null : res.json();
  }
  const fileUrl = (id, kind, dl = false) => `${API}/jobs/${encodeURIComponent(id)}/file/${kind}${dl ? '?download=true' : ''}`;

  // -- App state --------------------------------------------------------------
  const state = {
    view: 'translate',
    mode: 'text',
    languages: [],
    file: null,
    opts: { generate_tts: true, generate_subtitles: true, burn_subtitles: false },
    poller: null,
    glossary: [],
    currentJob: null,
  };

  const LANG_NATIVE = { auto: 'स्वयं', en: 'English', hi: 'हिन्दी', mr: 'मराठी' };

  const STAGE_LABELS = {
    pending: 'Queued', starting: 'Starting up', 'extracting-audio': 'Extracting audio',
    transcribing: 'Transcribing speech', translating: 'Translating', translated: 'Translating',
    'synthesizing-voice': 'Generating voice', 'building-subtitles': 'Building subtitles',
    'burning-captions': 'Burning captions into video', done: 'Completed', error: 'Failed',
  };
  const PHASES_MEDIA = [
    { label: 'Extract', at: 10 }, { label: 'Transcribe', at: 25 }, { label: 'Translate', at: 55 },
    { label: 'Voice', at: 78 }, { label: 'Subtitles', at: 88 }, { label: 'Done', at: 100 },
  ];
  const PHASES_TEXT = [{ label: 'Translate', at: 40 }, { label: 'Voice', at: 78 }, { label: 'Done', at: 100 }];

  // -- Toasts -----------------------------------------------------------------
  function toast(msg, kind = 'ok') {
    const el = document.createElement('div');
    el.className = `toast` + (kind === 'err' ? ' err' : '');
    el.textContent = msg;
    $('#toasts').appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(20px)'; el.style.transition = 'all .3s'; setTimeout(() => el.remove(), 320); }, 3000);
  }

  // -- Theme ------------------------------------------------------------------
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('bs-theme', t);
    $('#themeIcon').innerHTML = t === 'dark'
      ? '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'
      : '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M5.5 5.5l1.5 1.5M17.5 17.5l1.5 1.5M2 12h2M20 12h2M5.5 18.5l1.5-1.5M17.5 5.5l1.5 1.5"/>';
  }
  function toggleTheme() {
    applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  }

  // -- Routing ----------------------------------------------------------------
  function go(view) {
    state.view = view;
    $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
    $$('.shell > .view').forEach((s) => s.classList.add('hidden'));
    const sec = $(`#view-${view}`);
    sec.classList.remove('hidden');
    sec.classList.remove('view'); void sec.offsetWidth; sec.classList.add('view'); // replay animation
    if (view === 'library') loadLibrary();
    if (view === 'glossary') loadGlossary();
    if (view === 'system') loadSystem();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // -- Languages --------------------------------------------------------------
  async function loadLanguages() {
    try {
      state.languages = await http('/languages');
    } catch {
      state.languages = [{ code: 'en', name: 'English', native: 'English' },
        { code: 'hi', name: 'Hindi', native: 'हिन्दी' }, { code: 'mr', name: 'Marathi', native: 'मराठी' }];
    }
    const opt = (l) => `<option value="${l.code}">${esc(l.name)} · ${esc(l.native)}</option>`;
    $('#srcLang').innerHTML = `<option value="auto">Auto-detect · स्वयं</option>` + state.languages.map(opt).join('');
    $('#tgtLang').innerHTML = state.languages.map(opt).join('');
    $('#srcLang').value = 'auto';
    $('#tgtLang').value = (state.languages.find((l) => l.code === 'hi') ? 'hi' : state.languages[0].code);
  }

  function swap() {
    const s = $('#srcLang'), t = $('#tgtLang');
    if (s.value === 'auto') { toast('Pick a source language to swap', 'err'); return; }
    const a = s.value; s.value = t.value; t.value = a;
  }

  // -- Mode + options ---------------------------------------------------------
  function setMode(mode) {
    state.mode = mode;
    $$('#modeSeg button').forEach((b) => b.classList.toggle('active', b.dataset.mode === mode));
    $('#textMode').classList.toggle('hidden', mode !== 'text');
    $('#mediaMode').classList.toggle('hidden', mode !== 'media');
    $$('.media-only').forEach((el) => el.classList.toggle('hidden', mode !== 'media'));
  }

  function bindOptions() {
    $$('#opts .chip').forEach((chip) => {
      chip.addEventListener('click', (e) => {
        e.preventDefault();
        const key = chip.dataset.opt;
        state.opts[key] = !state.opts[key];
        chip.classList.toggle('on', state.opts[key]);
        $('input', chip).checked = state.opts[key];
      });
    });
  }

  // -- Dropzone ---------------------------------------------------------------
  function bindDropzone() {
    const dz = $('#dropzone'), input = $('#fileInput');
    dz.addEventListener('click', (e) => { if (e.target.closest('.file-pill')) return; input.click(); });
    input.addEventListener('change', () => { if (input.files[0]) setFile(input.files[0]); });
    ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('drag'); }));
    ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('drag'); }));
    dz.addEventListener('drop', (e) => e.dataTransfer.files[0] && setFile(e.dataTransfer.files[0]));
  }

  function setFile(f) {
    state.file = f;
    const kb = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + ' MB' : (f.size / 1024).toFixed(0) + ' KB';
    $('#filePillWrap').innerHTML =
      `<div class="file-pill">🗎 ${esc(f.name)} · ${kb}
        <button onclick="event.stopPropagation();App.clearFile()" title="Remove">
          <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button></div>`;
  }
  function clearFile() { state.file = null; $('#filePillWrap').innerHTML = ''; $('#fileInput').value = ''; }

  // -- Translate --------------------------------------------------------------
  async function translate() {
    const src = $('#srcLang').value, tgt = $('#tgtLang').value;
    const btn = $('#goBtn');
    if (state.mode === 'text') {
      const text = $('#srcText').value.trim();
      if (!text) { toast('Enter some text first', 'err'); return; }
      setBusy(btn, true);
      try {
        const job = await http('/translate/text', {
          method: 'POST',
          body: JSON.stringify({ text, source_lang: src, target_lang: tgt, generate_tts: state.opts.generate_tts }),
        });
        showResult(job);
        $('#progressCard').classList.add('hidden');
        toast(job.reused ? 'Reused an identical translation ⚡' : 'Translated');
      } catch (e) { toast(e.message, 'err'); }
      finally { setBusy(btn, false); }
    } else {
      if (!state.file) { toast('Choose an audio or video file', 'err'); return; }
      setBusy(btn, true);
      const fd = new FormData();
      fd.append('file', state.file);
      fd.append('target_lang', tgt);
      fd.append('source_lang', src);
      const title = $('#mediaTitle').value.trim(); if (title) fd.append('title', title);
      fd.append('generate_tts', state.opts.generate_tts);
      fd.append('generate_subtitles', state.opts.generate_subtitles);
      fd.append('burn_subtitles', state.opts.burn_subtitles);
      try {
        const job = await http('/jobs', { method: 'POST', body: fd });
        setBusy(btn, false);
        if (job.status === 'completed') { showResult(job); toast('Reused an identical result ⚡'); return; }
        $('#resultCard').classList.add('hidden');
        startPolling(job);
      } catch (e) { toast(e.message, 'err'); setBusy(btn, false); }
    }
  }

  function setBusy(btn, busy) {
    btn.disabled = busy;
    btn.querySelector('span').textContent = busy ? 'Working…' : 'Translate';
    btn.querySelector('svg').style.display = busy ? 'none' : '';
    if (busy && !btn.querySelector('.spinner')) { const s = document.createElement('span'); s.className = 'spinner'; btn.prepend(s); }
    if (!busy) { const s = btn.querySelector('.spinner'); if (s) s.remove(); }
  }

  // -- Progress polling -------------------------------------------------------
  function startPolling(job) {
    renderProgress(job);
    $('#progressCard').classList.remove('hidden');
    if (state.poller) clearInterval(state.poller);
    state.poller = setInterval(async () => {
      try {
        const j = await http('/jobs/' + job.id);
        renderProgress(j);
        if (j.status === 'completed' || j.status === 'failed') {
          clearInterval(state.poller); state.poller = null;
          if (j.status === 'completed') { showResult(j); toast('Done — ' + (j.title || 'translation ready')); }
          else { toast('Failed: ' + (j.error || 'unknown error'), 'err'); }
        }
      } catch (e) { clearInterval(state.poller); toast(e.message, 'err'); }
    }, 850);
  }

  function renderProgress(job) {
    const stage = job.stage || job.status || 'pending';
    $('#stageLabel').textContent = STAGE_LABELS[stage] || stage;
    $('#pctLabel').textContent = (job.progress || 0) + '%';
    $('#barFill').style.width = (job.progress || 0) + '%';
    const phases = job.input_type === 'text' ? PHASES_TEXT : PHASES_MEDIA;
    const p = job.progress || 0;
    $('#stageSteps').innerHTML = phases.map((ph, i) => {
      const next = phases[i + 1]?.at ?? 101;
      let cls = 'step';
      if (p >= next || (ph.at === 100 && p >= 100)) cls += ' done';
      else if (p >= ph.at) cls += ' active';
      return `<span class="${cls}">${ph.label}</span>`;
    }).join('');
  }

  // -- Result rendering -------------------------------------------------------
  function showResult(job) {
    state.currentJob = job;
    const tabs = [];
    if (job.translated_text != null) tabs.push('translation');
    if (job.source_text) tabs.push('transcript');
    if (job.segments && job.segments.some((s) => s.end > s.start)) tabs.push('segments');
    if (job.has_srt || job.has_vtt) tabs.push('subtitles');
    if (job.has_audio) tabs.push('voice');
    if (job.has_video) tabs.push('video');

    const badges = [];
    const dir = `${(job.detected_lang || job.source_lang || '').toUpperCase()} → ${job.target_lang.toUpperCase()}`;
    badges.push(`<span class="badge green dot">${esc(dir)}</span>`);
    if (job.reused) badges.push(`<span class="badge amber">⚡ reused</span>`);
    if (job.mock) badges.push(`<span class="badge">demo output</span>`);
    if (job.duration_sec) badges.push(`<span class="badge">${(job.duration_sec).toFixed(1)}s media</span>`);
    badges.push(`<span class="badge">${esc(job.input_type)}</span>`);

    const label = { translation: 'Translation', transcript: 'Transcript', segments: 'Segments', subtitles: 'Subtitles', voice: 'Voice', video: 'Video' };
    const card = $('#resultCard');
    card.classList.remove('hidden');
    card.innerHTML = `
      <div class="spread" style="margin-bottom:6px">
        <div class="card-title" style="margin:0"><span class="dot"></span> ${esc(job.title || 'Result')}</div>
        <button class="btn btn-ghost btn-sm" onclick="App.go('library')">View in library ↗</button>
      </div>
      <div class="meta-row">${badges.join('')}</div>
      <div class="result-tabs" style="margin-top:16px">
        ${tabs.map((t, i) => `<button data-tab="${t}" class="${i === 0 ? 'active' : ''}">${label[t]}</button>`).join('')}
      </div>
      <div id="resBody"></div>`;
    $$('#resTabs button').forEach((b) => b.addEventListener('click', () => {
      $$('#resTabs button').forEach((x) => x.classList.remove('active'));
      b.classList.add('active'); renderTab(job, b.dataset.tab);
    }));
    if (tabs.length) renderTab(job, tabs[0]); else $('#resBody').innerHTML = '<p class="muted">No output produced.</p>';
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function renderTab(job, tab) {
    const body = $('#resBody');
    if (tab === 'translation') {
      body.innerHTML = `<div class="text-out" id="trOut">${esc(job.translated_text)}</div>
        <div class="btn-row">
          <button class="btn btn-ghost btn-sm" onclick="App.copy(this, $(q(job.translated_text)))">Copy</button>
          <a class="btn btn-ghost btn-sm" href="${fileUrl(job.id, 'text', true)}">Download .txt</a>
        </div>`;
    } else if (tab === 'transcript') {
      body.innerHTML = `<div class="text-out">${esc(job.source_text)}</div>
        <div class="btn-row"><button class="btn btn-ghost btn-sm" onclick="App.copy(this, $(q(job.source_text)))">Copy</button>
        <a class="btn btn-ghost btn-sm" href="${fileUrl(job.id, 'transcript', true)}">Download .txt</a></div>`;
    } else if (tab === 'segments') {
      body.innerHTML = `<div class="seg-list">${job.segments.map((s) =>
        `<div class="seg-item"><div class="time">${fmt(s.start)} → ${fmt(s.end)}</div>
         <div class="src">${esc(s.source)}</div><div class="tr">${esc(s.translated || '')}</div></div>`).join('')}</div>`;
    } else if (tab === 'subtitles') {
      body.innerHTML = `<p class="muted" style="margin-top:0">Translated, time-aligned captions ready for any player.</p>
        <div class="btn-row">
          ${job.has_srt ? `<a class="btn btn-primary btn-sm" href="${fileUrl(job.id, 'srt', true)}">Download .srt</a>` : ''}
          ${job.has_vtt ? `<a class="btn btn-ghost btn-sm" href="${fileUrl(job.id, 'vtt', true)}">Download .vtt</a>` : ''}
        </div>`;
    } else if (tab === 'voice') {
      body.innerHTML = `<audio controls src="${fileUrl(job.id, 'audio')}"></audio>
        <div class="btn-row"><a class="btn btn-ghost btn-sm" href="${fileUrl(job.id, 'audio', true)}">Download voice .wav</a></div>`;
    } else if (tab === 'video') {
      body.innerHTML = `<video controls src="${fileUrl(job.id, 'video')}"></video>
        <div class="btn-row"><a class="btn btn-ghost btn-sm" href="${fileUrl(job.id, 'video', true)}">Download captioned .mp4</a></div>`;
    }
  }
  const q = (s) => JSON.stringify(String(s ?? '')).replace(/"/g, '&quot;').replace(/"/g, '&#39;');
  function copy(btn, text) {
    navigator.clipboard.writeText(text).then(() => { const o = btn.textContent; btn.textContent = 'Copied ✓'; setTimeout(() => btn.textContent = o, 1400); });
  }
  function fmt(t) { const m = Math.floor(t / 60), s = (t % 60).toFixed(1).padStart(4, '0'); return `${m}:${s}`; }

  // -- Library ----------------------------------------------------------------
  async function loadLibrary() {
    const grid = $('#libGrid');
    grid.innerHTML = `<div class="empty" style="grid-column:1/-1"><div class="spinner dark" style="margin:0 auto"></div></div>`;
    try {
      const data = await http('/jobs?limit=60');
      $('#libCount').textContent = `${data.total} translation${data.total === 1 ? '' : 's'} stored`;
      if (!data.items.length) { grid.innerHTML = emptyState('No translations yet', 'Your processed text, audio and video will appear here.'); return; }
      grid.innerHTML = data.items.map(jobCard).join('');
    } catch (e) { grid.innerHTML = emptyState('Could not load library', e.message); }
  }

  function jobCard(j) {
    const dir = `${(j.detected_lang || j.source_lang || '').toUpperCase()}→${j.target_lang.toUpperCase()}`;
    const snippet = esc((j.translated_text || j.source_text || '').slice(0, 90));
    const st = j.status === 'completed' ? 'green' : (j.status === 'failed' ? 'amber' : '');
    return `<div class="card job-card" data-job-id="${esc(j.id)}" onclick="App.openJob(this.dataset.jobId)">}')">
      <div class="spread"><h4 title="${esc(j.title || (j.input_type + ' translation'))}">${esc(j.title || (j.input_type + ' translation'))}</h4></div>
      <div class="snippet">${snippet} ${'<span class="muted">…</span>'}</div>
      <div class="foot">
        <span class="badge ${st} dot">${esc(dir)}</span>
        <span class="row">
          ${j.has_audio ? icon('voice') : ''} ${j.has_srt ? icon('cc') : ''} ${j.has_video ? icon('video') : ''}
          ${j.reused ? `<span class="badge amber" style="padding:2px 7px">⚡</span>` : ''}
        </span>
      </div></div>`;
  }

  function icon(kind) {
    const map = { voice: 'M11 5 6 9H2v6h4l5 4zM15.5 8.5a5 5 0 0 1 0 7M19 5a9 9 0 0 1 0 14', cc: 'M3 5h18v14H3zM7 10h3M7 14h3M14 10h3M14 14h3', video: 'm23 7-7 5 7 5V7zM1 5h15v14H1z' };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="var(--leaf)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px"><path d="${map[kind]}"/></svg>`;
  }

  async function openJob(id) {
    try { const job = await http('/jobs/' + encodeURIComponent(id)); go('translate'); $('#progressCard').classList.add('hidden'); showResult(job); }
    catch (e) { toast(e.message, 'err'); }
  }

  // -- Glossary ---------------------------------------------------------------
  async function loadGlossary() {
    try { state.glossary = await http('/glossary'); renderGlossary(); }
    catch (e) { $('#gBody').innerHTML = `<tr><td colspan="5" class="muted">${esc(e.message)}</td></tr>`; }
  }

  function renderGlossary() {
    const term = ($('#gSearch').value || '').toLowerCase();
    const gf = (e, code) => (e.forms && e.forms[code]) || '';
    const rows = state.glossary.filter((e) =>
      !term || [gf(e, 'en'), gf(e, 'hi'), gf(e, 'mr'), e.category].some((v) => (v || '').toLowerCase().includes(term)));
    $('#gCount').textContent = `(${rows.length})`;
    $('#gBody').innerHTML = rows.length ? rows.map((e) =>
      `<tr><td><span class="cat-tag">${esc(e.category)}</span></td><td>${esc(gf(e, 'en'))}</td><td>${esc(gf(e, 'hi'))}</td><td>${esc(gf(e, 'mr'))}</td>
        <td style="text-align:right"><button class="del-btn" title="Delete" data-entry-id="${esc(e.id)}" onclick="App.delGlossary(this.dataset.entryId)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg></button></td></tr>`
    ).join('') : `<tr><td colspan="5" class="muted" style="text-align:center;padding:24px">No matching terms</td></tr>`;
  }

  async function addGlossary() {
    const forms = { en: $('#gEn').value.trim(), hi: $('#gHi').value.trim(), mr: $('#gMr').value.trim() };
    const entry = { category: $('#gCat').value.trim() || 'general', forms };
    if (!forms.en || !forms.hi || !forms.mr) { toast('Fill English, Hindi and Marathi', 'err'); return; }
    try {
      const created = await http('/glossary', { method: 'POST', body: JSON.stringify(entry) });
      state.glossary.unshift(created); renderGlossary();
      $('#gEn').value = ''; $('#gHi').value = ''; $('#gMr').value = '';
      toast('Term added to glossary');
    } catch (e) { toast(e.message, 'err'); }
  }

  async function delGlossary(id) {
    try { await http('/glossary/' + encodeURIComponent(id), { method: 'DELETE' }); state.glossary = state.glossary.filter(e => e.id !== id); renderGlossary(); }
    catch (e) { toast(e.message, 'err'); }
  }

  // -- System / health --------------------------------------------------------
  async function loadSystem() {
    try {
      const h = await http('/health');
      $('#sysGrid').innerHTML = [
        ['Version', 'v' + h.version], ['Mode', h.models_enabled ? 'Live models' : 'Demo (mock)'],
        ['Offline', h.offline ? 'Yes' : 'No'], ['Device', h.device.toUpperCase()],
        ['Whisper', h.whisper_model], ['Translator', h.mt_backend], ['Voice', h.tts_backend],
      ].map(([k, v]) => `<div class="sys-item"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`).join('');
      $('#readyGrid').innerHTML = Object.entries(h.ready).map(([k, v]) =>
        `<div class="sys-item"><div class="k">${esc(k)}</div><div class="v"><span class="ready-dot ${v ? 'on' : 'off'}"></span>${v ? 'Ready' : 'Idle'}</div></div>`).join('');
      $('#modeNote').innerHTML = h.models_enabled
        ? `<div class="card-title" style="margin:0"><span class="dot"></span> Live models are enabled — real transcription, translation and voice.</div>`
        : `<div class="card-title" style="margin:0"><span class="dot"></span> Demo mode</div><p class="muted" style="margin:8px 0 0">Heavy ML models are disabled, so the full pipeline runs instantly
          with realistic mock output — perfect for trying the workflow offline. Set <code>BHASHASETU_ENABLE_MODELS=true</code> after downloading models for production output.</p>`;
    } catch (e) { $('#sysGrid').innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
  }

  async function pingHealth() {
    const pill = $('#healthPill');
    try {
      const h = await http('/health');
      pill.className = 'status-pill ok';
      pill.innerHTML = `<span class="d"></span> ${h.models_enabled ? 'Live models' : 'Demo mode'} · ${h.offline ? 'offline' : 'online'}`;
    } catch {
      pill.className = 'status-pill err';
      pill.innerHTML = `<span class="d"></span> API offline`;
    }
  }

  function clearForm() {
    $('#srcText').value = ''; $('#mediaTitle').value = ''; clearFile();
    $('#resultCard').classList.add('hidden'); $('#progressCard').classList.add('hidden');
  }

  // -- Boot -------------------------------------------------------------------
  function init() {
    applyTheme(localStorage.getItem('bs-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
    $$('#nav button').forEach((b) => b.addEventListener('click', () => go(b.dataset.view)));
    $$('#modeSeg button').forEach((b) => b.addEventListener('click', () => setMode(b.dataset.mode)));
    bindOptions(); bindDropzone();
    loadLanguages(); pingHealth();
    setInterval(pingHealth, 15000);
  }

  // expose for inline handlers
  window.App = { go, toggleTheme, swap, translate, clearForm, clearFile, copy, openJob, addGlossary, delGlossary, renderGlossary, loadLibrary, loadGlossary };
  document.addEventListener('DOMContentLoaded', init);
})();