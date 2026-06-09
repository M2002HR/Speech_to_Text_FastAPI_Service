const statusPill = document.getElementById('statusPill');
const runtimeStatus = document.getElementById('runtimeStatus');
const events = document.getElementById('events');
const form = document.getElementById('controlForm');
const sourceMode = document.getElementById('sourceMode');
const mediaFile = document.getElementById('mediaFile');
const uploadBtn = document.getElementById('uploadBtn');
const uploadHint = document.getElementById('uploadHint');
const language = document.getElementById('language');
const topic = document.getElementById('topic');
const keyterms = document.getElementById('keyterms');
const diarize = document.getElementById('diarize');
const autoScroll = document.getElementById('autoScroll');
const showJsonLog = document.getElementById('showJsonLog');
const maxLogItems = document.getElementById('maxLogItems');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const partial = document.getElementById('partial');
const finalText = document.getElementById('finalText');
const hints = document.getElementById('hints');

const state = { ws: null, upload: null, finalParts: [], hintCount: 0, logEntries: [] };

function setStatus(text, cls = '') {
  statusPill.textContent = text;
  statusPill.className = `status-pill ${cls}`.trim();
}

function shouldAutoScroll() { return !autoScroll || autoScroll.checked; }
function maxLogCount() {
  const value = Number(maxLogItems?.value || 120);
  return Number.isFinite(value) ? Math.max(20, Math.min(400, Math.round(value))) : 120;
}

function log(type, data = {}) {
  const detailed = !showJsonLog || showJsonLog.checked;
  const clean = typeof data === 'string' ? data : JSON.stringify(data);
  const payload = detailed ? clean.slice(0, 1400) : clean.replace(/\s+/g, ' ').slice(0, 520);
  state.logEntries.unshift(`${new Date().toLocaleTimeString()} ${type} ${payload}`);
  state.logEntries = state.logEntries.slice(0, maxLogCount());
  events.textContent = state.logEntries.join('\n');
  if (shouldAutoScroll()) events.scrollTop = 0;
}

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws/realtime`;
}

function resetOutput() {
  state.finalParts = [];
  state.hintCount = 0;
  state.logEntries = [];
  partial.textContent = '...';
  finalText.textContent = '';
  events.textContent = '';
  hints.innerHTML = '<p class="muted">هنوز بازخوردی تولید نشده است.</p>';
}

function statusLabel(status) {
  if (status === 'resolved') return 'حل شد';
  if (status === 'probably_addressed') return 'احتمالاً رفع شد';
  return 'باز';
}

function statusClass(status) {
  if (status === 'resolved') return 'issue-resolved';
  if (status === 'probably_addressed') return 'issue-probably';
  return 'issue-open';
}

function renderIssueStatus(issue) {
  if (!issue) return '';
  const status = issue.status || 'open';
  const evidence = issue.resolution_evidence || issue.resolution_message || '';
  return `<div class="issue-status ${statusClass(status)}"><b>وضعیت:</b> ${statusLabel(status)}${evidence ? `<br><span>${escapeHtml(evidence)}</span>` : ''}</div>`;
}

function addHint(result) {
  if (!result) return;
  if (state.hintCount === 0) hints.innerHTML = '';
  state.hintCount += 1;
  const node = document.createElement('div');
  node.className = `hint-card hint-${result.severity_label || result.alert_level || 'none'}`;
  if (result.issue_id) node.dataset.issueId = result.issue_id;
  const confidence = Number(result.confidence || 0).toFixed(2);
  const tags = Array.isArray(result.tags) ? result.tags : [];
  const badges = [result.alert_category, result.severity_label, result.issue_type, ...tags]
    .filter(Boolean)
    .map((tag) => `<span class="hint-badge">${escapeHtml(tag)}</span>`)
    .join('');
  node.innerHTML = `
    <strong>${state.hintCount}. ${escapeHtml(result.short_feedback || 'بدون هشدار مهم.')}</strong>
    <div class="hint-badges">${badges}<span class="hint-badge">confidence ${confidence}</span></div>
    ${result.issue_id ? `<div class="issue-status issue-open"><b>وضعیت:</b> باز</div>` : ''}
    ${result.resolution_criteria ? `<p class="muted"><b>معیار حل‌شدن:</b> ${escapeHtml(result.resolution_criteria)}</p>` : ''}
    ${result.suggested_teacher_action ? `<p><b>اقدام:</b> ${escapeHtml(result.suggested_teacher_action)}</p>` : ''}
    ${result.suggested_example ? `<p><b>مثال:</b> ${escapeHtml(result.suggested_example)}</p>` : ''}
    ${result.evidence ? `<p class="muted"><b>شاهد:</b> ${escapeHtml(result.evidence)}</p>` : ''}
  `;
  hints.prepend(node);
  if (shouldAutoScroll()) hints.scrollTop = 0;
}

function applyIssueUpdate(issue, eventType) {
  if (!issue || !issue.issue_id) return;
  const card = hints.querySelector(`[data-issue-id="${CSS.escape(issue.issue_id)}"]`);
  if (!card) {
    const node = document.createElement('div');
    node.className = `hint-card ${statusClass(issue.status)}`;
    node.dataset.issueId = issue.issue_id;
    node.innerHTML = `<strong>${eventType === 'teacher.issue.resolved' ? '✅ حل شد' : 'به‌روزرسانی هشدار'}</strong>${renderIssueStatus(issue)}<p>${escapeHtml(issue.short_feedback || '')}</p>`;
    hints.prepend(node);
    if (shouldAutoScroll()) hints.scrollTop = 0;
    return;
  }
  card.classList.remove('issue-open', 'issue-probably', 'issue-resolved');
  card.classList.add(statusClass(issue.status));
  const existing = card.querySelector('.issue-status');
  if (existing) existing.outerHTML = renderIssueStatus(issue);
  else card.insertAdjacentHTML('afterbegin', renderIssueStatus(issue));
}

async function loadStatus() {
  try {
    const res = await fetch('/realtime/status');
    const data = await res.json();
    runtimeStatus.textContent = JSON.stringify(data.realtime, null, 2);
    const sttReady = data.realtime && data.realtime.deepgram && data.realtime.deepgram.configured;
    const llmReady = data.realtime && data.realtime.llm && data.realtime.llm.configured;
    setStatus(sttReady ? `STT ready · LLM ${llmReady ? 'ready' : 'not configured'}` : 'STT key missing', sttReady ? 'status-ok' : 'status-bad');
  } catch (err) {
    setStatus(`status error: ${err.message}`, 'status-bad');
  }
}

async function uploadFile() {
  const file = mediaFile.files && mediaFile.files[0];
  if (!file) {
    setStatus('اول یک فایل انتخاب کن', 'status-warn');
    return;
  }
  const body = new FormData();
  body.append('file', file);
  uploadBtn.disabled = true;
  uploadHint.textContent = 'در حال آپلود و استخراج صدا...';
  setStatus('در حال آماده‌سازی فایل...', 'status-warn');
  try {
    const res = await fetch('/realtime/uploads', { method: 'POST', body });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    state.upload = data;
    const seconds = data.duration_seconds ? `${Number(data.duration_seconds).toFixed(1)}s` : 'duration unknown';
    uploadHint.textContent = `آماده: ${data.source_filename} · ${seconds}`;
    sourceMode.value = 'upload';
    setStatus('فایل آماده پخش شبه‌زنده است', 'status-ok');
    log('upload.ready', data);
  } catch (err) {
    state.upload = null;
    uploadHint.textContent = 'آپلود ناموفق بود.';
    setStatus(`upload error: ${err.message}`, 'status-bad');
  } finally {
    uploadBtn.disabled = false;
  }
}

function handleMessage(event) {
  let data;
  try { data = JSON.parse(event.data); } catch { log('raw', event.data); return; }
  log(data.type, data);
  if (data.type === 'transcript.partial') {
    partial.textContent = data.text || '';
    if (shouldAutoScroll()) partial.scrollTop = partial.scrollHeight;
  }
  if (data.type === 'transcript.final' && data.text) {
    partial.textContent = '';
    state.finalParts.push(data.text);
    finalText.textContent = state.finalParts.join('\n');
    if (shouldAutoScroll()) finalText.scrollTop = finalText.scrollHeight;
  }
  if (data.type === 'teacher.hint') addHint(data.result);
  if (data.type === 'teacher.issue.updated' || data.type === 'teacher.issue.resolved') applyIssueUpdate(data.issue, data.type);
  if (data.type === 'file.playback.progress') setStatus(`در حال پخش فایل: ${data.audio_seconds}s`, 'status-ok');
  if (data.type === 'stt.open') setStatus('STT stream باز شد', 'status-ok');
  if (data.type === 'session.closed') setStatus('جلسه بسته شد', 'status-warn');
  if (data.type === 'error' || data.type === 'stt.error' || data.type === 'analysis.error' || data.type === 'file.playback.error') setStatus(data.error || data.message || 'خطا', 'status-bad');
}

async function startUploadedFile() {
  if (!state.upload || !state.upload.upload_id) throw new Error('اول فایل را آپلود کن.');
  const ws = new WebSocket(wsUrl());
  state.ws = ws;
  ws.onmessage = handleMessage;
  ws.onerror = () => setStatus('WebSocket error', 'status-bad');
  ws.onclose = () => stopSession(true);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  ws.send(JSON.stringify({
    type: 'start',
    source: 'upload',
    upload_id: state.upload.upload_id,
    language: language.value || undefined,
    topic: topic.value || undefined,
    keyterms: keyterms.value || undefined,
    diarize: diarize.checked,
  }));
  setStatus('پخش شبه‌زنده فایل شروع شد', 'status-ok');
}

async function startSession(event) {
  event.preventDefault();
  if (state.ws) return;
  resetOutput();
  startBtn.disabled = true;
  stopBtn.disabled = false;
  try {
    if (sourceMode.value !== 'upload') throw new Error('در این نسخه از همین صفحه، منبع فایل را انتخاب کن. مسیر میکروفون زنده در /live موجود است.');
    await startUploadedFile();
  } catch (err) {
    setStatus(`شروع ناموفق: ${err.message}`, 'status-bad');
    stopSession(true);
  }
}

function stopSession(silent = false) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    try { state.ws.send(JSON.stringify({ type: 'stop' })); } catch {}
    try { state.ws.close(); } catch {}
  }
  state.ws = null;
  startBtn.disabled = false;
  stopBtn.disabled = true;
  if (!silent) setStatus('متوقف شد', 'status-warn');
}

uploadBtn.addEventListener('click', uploadFile);
form.addEventListener('submit', startSession);
stopBtn.addEventListener('click', () => stopSession(false));
sourceMode.addEventListener('change', () => setStatus(sourceMode.value === 'upload' ? 'حالت فایل: اول فایل را آپلود کن' : 'برای میکروفون زنده فعلاً از /live استفاده کن', 'status-warn'));
showJsonLog?.addEventListener('change', () => log('dashboard.log_mode', { detailed: showJsonLog.checked }));
maxLogItems?.addEventListener('change', () => {
  state.logEntries = state.logEntries.slice(0, maxLogCount());
  events.textContent = state.logEntries.join('\n');
});
loadStatus();
