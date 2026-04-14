'use strict';

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(seconds) {
  if (!seconds) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function words(text) {
  return text ? text.trim().split(/\s+/).filter(Boolean).length : 0;
}

function showToast(msg = 'Copiado!') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  requestAnimationFrame(() => {
    requestAnimationFrame(() => t.classList.add('show'));
  });
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.classList.add('hidden'), 300);
  }, 2000);
}

// ── API ────────────────────────────────────────────────────────────────────

async function submitYoutube(url) {
  const res = await fetch('/transcriptions/video/url', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function submitAudio(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/transcriptions/audio', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function submitVideo(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/transcriptions/video', { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

async function getStatus(jobId) {
  const res = await fetch(`/transcriptions/${jobId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function getResult(jobId) {
  const res = await fetch(`/transcriptions/${jobId}/result`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Polling ────────────────────────────────────────────────────────────────

const STATUS_LABELS = {
  pending:    'Na fila…',
  processing: 'Transcrevendo…',
  done:       'Concluído!',
  failed:     'Falha',
};

function poll(jobId, onStatus, onDone, onError) {
  const tick = async () => {
    try {
      const job = await getStatus(jobId);
      onStatus(job.status);
      if (job.status === 'done') {
        const result = await getResult(jobId);
        onDone(result);
      } else if (job.status === 'failed') {
        onError(job.error || 'Falha no processamento.');
      } else {
        setTimeout(tick, 3000);
      }
    } catch (e) {
      onError(e.message);
    }
  };
  tick();
}

// ── Card controller ────────────────────────────────────────────────────────

function createCard({ btnId, feedbackId, msgId, resultId, metaId, textId, errorId, errorMsgId }) {
  const btn      = document.getElementById(btnId);
  const feedback = document.getElementById(feedbackId);
  const msg      = document.getElementById(msgId);
  const result   = document.getElementById(resultId);
  const meta     = document.getElementById(metaId);
  const textEl   = document.getElementById(textId);
  const error    = document.getElementById(errorId);
  const errorMsg = document.getElementById(errorMsgId);

  function setLoading(on) {
    btn.disabled = on;
    btn.querySelector('.btn-icon').classList.toggle('hidden', on);
    btn.querySelector('.btn-spinner').classList.toggle('hidden', !on);
  }

  function setStatus(status) {
    feedback.classList.remove('hidden');
    msg.textContent = STATUS_LABELS[status] || status;
  }

  function setResult(data) {
    feedback.classList.add('hidden');
    result.classList.remove('hidden');

    const tags = [`<span class="badge success">✓ Concluído</span>`];
    if (data.language) tags.push(`<span class="meta-tag">🌐 ${data.language}</span>`);
    if (data.duration_seconds) tags.push(`<span class="meta-tag">⏱ ${fmt(data.duration_seconds)}</span>`);
    const w = words(data.text);
    if (w) tags.push(`<span class="meta-tag">${w} palavras</span>`);
    meta.innerHTML = tags.join('');

    textEl.textContent = data.text || '(sem texto)';
    setLoading(false);
  }

  function setError(message) {
    feedback.classList.add('hidden');
    error.classList.remove('hidden');
    errorMsg.textContent = message;
    setLoading(false);
  }

  function reset() {
    feedback.classList.add('hidden');
    result.classList.add('hidden');
    error.classList.add('hidden');
    meta.innerHTML = '';
    textEl.textContent = '';
    errorMsg.textContent = '';
  }

  return { setLoading, setStatus, setResult, setError, reset };
}

// ── YouTube section ────────────────────────────────────────────────────────

(function setupYoutube() {
  const card = createCard({
    btnId: 'btn-yt', feedbackId: 'fb-yt', msgId: 'msg-yt',
    resultId: 'res-yt', metaId: 'meta-yt', textId: 'text-yt',
    errorId: 'err-yt', errorMsgId: 'err-yt-msg',
  });

  document.getElementById('btn-yt').addEventListener('click', async () => {
    const url = document.getElementById('yt-url').value.trim();
    if (!url) { document.getElementById('yt-url').focus(); return; }

    card.reset();
    card.setLoading(true);

    try {
      const { job_id } = await submitYoutube(url);
      card.setStatus('pending');
      poll(job_id, card.setStatus, card.setResult, card.setError);
    } catch (e) {
      card.setError(e.message);
      card.setLoading(false);
    }
  });
})();

// ── Audio section ──────────────────────────────────────────────────────────

(function setupAudio() {
  const card = createCard({
    btnId: 'btn-audio', feedbackId: 'fb-audio', msgId: 'msg-audio',
    resultId: 'res-audio', metaId: 'meta-audio', textId: 'text-audio',
    errorId: 'err-audio', errorMsgId: 'err-audio-msg',
  });

  setupDropzone('file-audio', 'drop-audio', 'drop-idle-audio', 'drop-sel-audio', 'fname-audio');

  document.getElementById('btn-audio').addEventListener('click', async () => {
    const file = document.getElementById('file-audio').files[0];
    if (!file) { document.getElementById('drop-audio').focus(); return; }

    card.reset();
    card.setLoading(true);

    try {
      const { job_id } = await submitAudio(file);
      card.setStatus('pending');
      poll(job_id, card.setStatus, card.setResult, card.setError);
    } catch (e) {
      card.setError(e.message);
      card.setLoading(false);
    }
  });
})();

// ── Video section ──────────────────────────────────────────────────────────

(function setupVideo() {
  const card = createCard({
    btnId: 'btn-video', feedbackId: 'fb-video', msgId: 'msg-video',
    resultId: 'res-video', metaId: 'meta-video', textId: 'text-video',
    errorId: 'err-video', errorMsgId: 'err-video-msg',
  });

  setupDropzone('file-video', 'drop-video', 'drop-idle-video', 'drop-sel-video', 'fname-video');

  document.getElementById('btn-video').addEventListener('click', async () => {
    const file = document.getElementById('file-video').files[0];
    if (!file) { document.getElementById('drop-video').focus(); return; }

    card.reset();
    card.setLoading(true);

    try {
      const { job_id } = await submitVideo(file);
      card.setStatus('pending');
      poll(job_id, card.setStatus, card.setResult, card.setError);
    } catch (e) {
      card.setError(e.message);
      card.setLoading(false);
    }
  });
})();

// ── Dropzone helper ────────────────────────────────────────────────────────

function setupDropzone(inputId, dropId, idleId, selId, fnameId) {
  const input  = document.getElementById(inputId);
  const zone   = document.getElementById(dropId);
  const idle   = document.getElementById(idleId);
  const sel    = document.getElementById(selId);
  const fname  = document.getElementById(fnameId);

  function showFile(file) {
    fname.textContent = file.name;
    idle.classList.add('hidden');
    sel.classList.remove('hidden');
  }
  function clearFile() {
    input.value = '';
    idle.classList.remove('hidden');
    sel.classList.add('hidden');
    fname.textContent = '';
  }

  input.addEventListener('change', () => {
    if (input.files[0]) showFile(input.files[0]);
  });

  zone.addEventListener('dragenter', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragover',  e => { e.preventDefault(); });
  zone.addEventListener('dragleave', e => { if (!zone.contains(e.relatedTarget)) zone.classList.remove('drag-over'); });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    showFile(file);
  });

  // clear button (inside label, stop propagation to avoid re-opening dialog)
  zone.querySelector('.clear-file')?.addEventListener('click', e => {
    e.preventDefault(); e.stopPropagation();
    clearFile();
  });
}

// ── Paste buttons ──────────────────────────────────────────────────────────

document.querySelectorAll('.paste-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      const input = document.getElementById(btn.dataset.target);
      if (input) { input.value = text; input.focus(); }
    } catch {
      /* permission denied — ignore */
    }
  });
});

// ── Copy buttons ───────────────────────────────────────────────────────────

document.querySelectorAll('.copy-btn').forEach(btn => {
  btn.addEventListener('click', async () => {
    const el = document.getElementById(btn.dataset.src);
    if (!el) return;
    try {
      await navigator.clipboard.writeText(el.textContent);
      showToast('Copiado!');
    } catch {
      /* fallback */
      const range = document.createRange();
      range.selectNodeContents(el);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
      document.execCommand('copy');
      window.getSelection().removeAllRanges();
      showToast('Copiado!');
    }
  });
});

// ── Download buttons ───────────────────────────────────────────────────────

document.querySelectorAll('.download-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const el = document.getElementById(btn.dataset.src);
    if (!el) return;
    const text = el.textContent;
    const name = `transcricao-${btn.dataset.name || 'resultado'}-${Date.now()}.txt`;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  });
});
