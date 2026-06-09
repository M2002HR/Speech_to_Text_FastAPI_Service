const statusPill = document.getElementById('statusPill');
const runtimeStatus = document.getElementById('runtimeStatus');
const events = document.getElementById('events');
const form = document.getElementById('controlForm');

function setStatus(text, cls = '') {
  statusPill.textContent = text;
  statusPill.className = `status-pill ${cls}`.trim();
}

function log(text) {
  events.textContent = `${new Date().toLocaleTimeString()} ${text}\n` + events.textContent;
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

form.addEventListener('submit', (event) => {
  event.preventDefault();
  log('The backend websocket is ready at /ws/realtime. Use a browser recorder client or WebRTC frontend to send audio/webm Opus chunks.');
  setStatus('Backend ready; recorder client is not bundled in this safety-limited commit', 'status-warn');
});

loadStatus();
