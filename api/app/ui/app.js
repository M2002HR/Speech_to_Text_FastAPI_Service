const $ = (id) => document.getElementById(id);

const els = {
  healthStatus: $("healthStatus"),
  ffmpegStatus: $("ffmpegStatus"),
  ffprobeStatus: $("ffprobeStatus"),
  defaultProvider: $("defaultProvider"),
  adminToken: $("adminToken"),
  adminHeader: $("adminHeader"),
  btnSaveAdmin: $("btnSaveAdmin"),
  btnReloadAll: $("btnReloadAll"),
  btnRefreshModels: $("btnRefreshModels"),
  btnRefreshJobs: $("btnRefreshJobs"),
  providerInput: $("providerInput"),
  modelInput: $("modelInput"),
  fileInput: $("fileInput"),
  languageInput: $("languageInput"),
  responseFormatInput: $("responseFormatInput"),
  temperatureInput: $("temperatureInput"),
  promptInput: $("promptInput"),
  wordTimestampsInput: $("wordTimestampsInput"),
  segmentTimestampsInput: $("segmentTimestampsInput"),
  vadFilterInput: $("vadFilterInput"),
  transcribeForm: $("transcribeForm"),
  transcribeStatus: $("transcribeStatus"),
  transcribeResult: $("transcribeResult"),
  transcribePercent: $("transcribePercent"),
  transcribeProgressBar: $("transcribeProgressBar"),
  transcribeJobMeta: $("transcribeJobMeta"),
  btnCopyText: $("btnCopyText"),
  providerModels: $("providerModels"),
  presetModels: $("presetModels"),
  localModels: $("localModels"),
  remoteModels: $("remoteModels"),
  remoteSearchInput: $("remoteSearchInput"),
  btnSearchRemote: $("btnSearchRemote"),
  downloadPreset: $("downloadPreset"),
  downloadRepo: $("downloadRepo"),
  downloadRevision: $("downloadRevision"),
  downloadSubdir: $("downloadSubdir"),
  downloadFiles: $("downloadFiles"),
  remoteRepoFiles: $("remoteRepoFiles"),
  btnDownloadModel: $("btnDownloadModel"),
  downloadJobs: $("downloadJobs"),
  jobTemplate: $("jobTemplate"),
};

const state = {
  providers: null,
  presets: [],
  localModels: [],
  remoteModels: [],
  remoteRepoFiles: [],
  recommendedFiles: [],
  jobs: [],
  latestText: "",
  currentTranscribeJobId: null,
  transcribePollHandle: null,
  pollHandle: null,
};

function saveAdmin() {
  localStorage.setItem("stt_admin_token", els.adminToken.value.trim());
  localStorage.setItem("stt_admin_header", els.adminHeader.value.trim() || "x-admin-token");
}

function loadAdmin() {
  els.adminToken.value = localStorage.getItem("stt_admin_token") || "";
  els.adminHeader.value = localStorage.getItem("stt_admin_header") || "x-admin-token";
}

function adminHeaders() {
  const token = els.adminToken.value.trim();
  const header = els.adminHeader.value.trim() || "x-admin-token";
  return token ? { [header]: token } : {};
}

function setStatus(text, cls = "") {
  els.transcribeStatus.className = `hint ${cls}`.trim();
  els.transcribeStatus.textContent = text;
}

function setTranscribeProgress(percent, stage = "-", jobId = "-") {
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  if (els.transcribeProgressBar) {
    els.transcribeProgressBar.style.width = `${p}%`;
  }
  if (els.transcribePercent) {
    els.transcribePercent.textContent = `${p.toFixed(0)}%`;
  }
  if (els.transcribeJobMeta) {
    const shortId = jobId && jobId !== "-" ? jobId.slice(0, 8) : "-";
    els.transcribeJobMeta.textContent = `job: ${shortId} | stage: ${stage || "-"}`;
  }
}

async function apiFetch(path, { method = "GET", body, admin = false, timeoutMs = 15000 } = {}) {
  const headers = {};
  if (admin) {
    Object.assign(headers, adminHeaders());
  }

  let payload = body;
  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetch(path, { method, headers, body: payload, signal: controller.signal });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new Error(`request timeout after ${timeoutMs}ms`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const msg = typeof data === "string" ? data : data.detail || JSON.stringify(data);
    throw new Error(`${response.status}: ${msg}`);
  }
  return data;
}

function createTranscribeJobWithProgress(formData, onUploadProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/transcribe/jobs", true);
    xhr.timeout = 30 * 60 * 1000;

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      const percent = (evt.loaded / evt.total) * 100;
      onUploadProgress && onUploadProgress(percent);
    };

    xhr.onload = () => {
      try {
        const text = xhr.responseText || "";
        const isJson = (xhr.getResponseHeader("content-type") || "").includes("application/json");
        const payload = isJson ? JSON.parse(text) : text;
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(payload);
          return;
        }
        const msg = typeof payload === "string" ? payload : payload.detail || JSON.stringify(payload);
        reject(new Error(`${xhr.status}: ${msg}`));
      } catch (err) {
        reject(err);
      }
    };

    xhr.onerror = () => reject(new Error("network error while creating transcription job"));
    xhr.ontimeout = () => reject(new Error("upload timeout while creating transcription job"));
    xhr.send(formData);
  });
}

function formatBytes(bytes) {
  if (!bytes || bytes < 1) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatParams(million) {
  if (!million) return "-";
  return `${million.toLocaleString()}M`;
}

function fillProviders() {
  if (!state.providers) return;
  const prev = els.providerInput.value;
  els.providerInput.innerHTML = "";

  state.providers.providers.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.name;
    opt.textContent = `${item.name}${item.enabled ? "" : " (disabled)"}`;
    if (!item.enabled) {
      opt.disabled = true;
    }
    els.providerInput.appendChild(opt);
  });

  els.providerInput.value = prev || state.providers.default_provider || "local";
}

function renderProviderModels() {
  if (!state.providers) return;
  els.providerModels.innerHTML = "";

  state.providers.providers.forEach((p) => {
    const box = document.createElement("article");
    box.className = "item";
    box.innerHTML = `
      <div class="item-head">
        <strong>${p.name}</strong>
        <span class="chip ${p.enabled ? "ok" : "bad"}">${p.enabled ? "فعال" : "غیرفعال"}</span>
      </div>
      <div class="item-meta">
        <span>model: ${p.model || "-"}</span>
        <span>base_url: ${p.base_url || "-"}</span>
      </div>
    `;

    const useBtn = document.createElement("button");
    useBtn.className = "btn ghost";
    useBtn.textContent = "استفاده در فرم";
    useBtn.type = "button";
    useBtn.onclick = () => {
      els.providerInput.value = p.name;
      if (p.model) {
        els.modelInput.value = p.model;
      }
    };
    box.appendChild(useBtn);
    els.providerModels.appendChild(box);
  });
}

function renderPresets() {
  els.presetModels.innerHTML = "";
  els.downloadPreset.innerHTML = "<option value=''>انتخاب اختیاری preset</option>";

  state.presets.forEach((p) => {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-head">
        <strong>${p.name}</strong>
        <span class="chip">${p.repo_id}</span>
      </div>
      <p class="hint">${p.notes}</p>
      <div class="item-meta">
        <span>variant: ${p.variant || "-"}</span>
        <span>params: ${formatParams(p.parameters_million)}</span>
        <span>est. model.bin: ${p.estimated_model_bin_mb ? `${p.estimated_model_bin_mb} MB` : "-"}</span>
        <span>est. VRAM: ${p.estimated_vram_gb ? `${p.estimated_vram_gb} GB` : "-"}</span>
      </div>
    `;

    const row = document.createElement("div");
    row.className = "actions";

    const useBtn = document.createElement("button");
    useBtn.className = "btn ghost";
    useBtn.textContent = "قرار دادن در دانلود";
    useBtn.type = "button";
    useBtn.onclick = () => {
      els.downloadPreset.value = p.name;
      els.downloadRepo.value = p.repo_id;
      els.downloadSubdir.value = p.name;
    };

    const transcribeBtn = document.createElement("button");
    transcribeBtn.className = "btn ghost";
    transcribeBtn.textContent = "استفاده در local";
    transcribeBtn.type = "button";
    transcribeBtn.onclick = () => {
      els.providerInput.value = "local";
      els.modelInput.value = p.variant || p.name;
    };

    row.append(useBtn, transcribeBtn);
    item.appendChild(row);
    els.presetModels.appendChild(item);

    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = `${p.name} (${p.repo_id})`;
    els.downloadPreset.appendChild(opt);
  });
}

function renderLocalModels() {
  els.localModels.innerHTML = "";
  if (!state.localModels.length) {
    els.localModels.innerHTML = '<p class="hint">مدل لوکالی پیدا نشد. یک دانلود جدید شروع کن.</p>';
    return;
  }

  state.localModels.forEach((m) => {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-head">
        <strong>${m.display_name}</strong>
        <span class="chip">${formatBytes(m.total_size_bytes)}</span>
      </div>
      <p class="mono">${m.path}</p>
      <div class="item-meta">
        <span>files: ${m.file_count}</span>
        <span>model.bin: ${m.model_bin_size_bytes ? formatBytes(m.model_bin_size_bytes) : "-"}</span>
        <span>variant: ${m.variant || "-"}</span>
        <span>params: ${formatParams(m.parameters_million)}</span>
        <span>est. VRAM: ${m.estimated_vram_gb ? `${m.estimated_vram_gb} GB` : "-"}</span>
        <span>updated: ${new Date(m.updated_at).toLocaleString()}</span>
      </div>
    `;
    const btn = document.createElement("button");
    btn.className = "btn";
    btn.type = "button";
    btn.textContent = "استفاده در فرم";
    btn.onclick = () => {
      els.providerInput.value = "local";
      els.modelInput.value = m.model_id;
    };
    item.appendChild(btn);
    els.localModels.appendChild(item);
  });
}

function renderRemoteRepoFiles() {
  els.remoteRepoFiles.innerHTML = "";
  if (!state.remoteRepoFiles.length) {
    els.remoteRepoFiles.innerHTML = '<p class="hint">ابتدا یک repo انتخاب کن تا فایل‌ها از اینترنت خوانده شود.</p>';
    return;
  }

  const rec = state.recommendedFiles.length ? state.recommendedFiles.join(", ") : "-";
  const recBox = document.createElement("article");
  recBox.className = "item";
  recBox.innerHTML = `
    <div class="item-head"><strong>فایل‌های پیشنهادی دانلود</strong><span class="chip">${state.recommendedFiles.length}</span></div>
    <p class="mono">${rec}</p>
  `;
  els.remoteRepoFiles.appendChild(recBox);

  state.remoteRepoFiles.forEach((f) => {
    const box = document.createElement("article");
    box.className = "item";
    box.innerHTML = `
      <div class="item-head">
        <strong class="mono">${f.path}</strong>
        <span class="chip">${formatBytes(f.size_bytes || f.lfs_size_bytes || 0)}</span>
      </div>
    `;
    els.remoteRepoFiles.appendChild(box);
  });
}

function renderRemoteModels() {
  els.remoteModels.innerHTML = "";
  if (!state.remoteModels.length) {
    els.remoteModels.innerHTML = '<p class="hint">مدل آنلاینی پیدا نشد.</p>';
    return;
  }

  state.remoteModels.forEach((m) => {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-head">
        <strong>${m.repo_id}</strong>
        <span class="chip">⬇ ${m.downloads ?? "-"}</span>
      </div>
      <div class="item-meta">
        <span>likes: ${m.likes ?? "-"}</span>
        <span>updated: ${m.last_modified ? new Date(m.last_modified).toLocaleDateString() : "-"}</span>
      </div>
    `;

    const row = document.createElement("div");
    row.className = "actions";

    const selectBtn = document.createElement("button");
    selectBtn.className = "btn ghost";
    selectBtn.type = "button";
    selectBtn.textContent = "انتخاب و خواندن فایل‌ها";
    selectBtn.onclick = async () => {
      els.downloadRepo.value = m.repo_id;
      if (!els.downloadSubdir.value.trim()) {
        els.downloadSubdir.value = m.repo_id.replace("/", "--");
      }
      await loadRemoteRepoFiles(m.repo_id, els.downloadRevision.value.trim() || "main");
    };

    row.appendChild(selectBtn);
    item.appendChild(row);
    els.remoteModels.appendChild(item);
  });
}

function renderJobs() {
  els.downloadJobs.innerHTML = "";
  if (!state.jobs.length) {
    els.downloadJobs.innerHTML = '<p class="hint">هیچ jobی ثبت نشده است.</p>';
    return;
  }

  state.jobs.forEach((job) => {
    const node = els.jobTemplate.content.firstElementChild.cloneNode(true);
    node.querySelector(".job-title").textContent = `${job.job_id.slice(0, 8)} · ${job.source}`;
    const statusEl = node.querySelector(".job-status");
    statusEl.textContent = job.status;
    if (job.status === "completed") statusEl.classList.add("ok");
    if (job.status === "failed") statusEl.classList.add("bad");
    if (job.status === "running") statusEl.classList.add("warn");

    node.querySelector(".job-url").textContent = job.resolved_url;

    const p = Number(job.progress_percent || 0);
    node.querySelector(".progress > span").style.width = `${Math.max(0, Math.min(100, p))}%`;

    const meta = node.querySelector(".item-meta");
    meta.innerHTML = `
      <span>progress: ${p.toFixed(1)}%</span>
      <span>${formatBytes(job.bytes_downloaded)} / ${job.bytes_total ? formatBytes(job.bytes_total) : "?"}</span>
      <span>${job.output_path || "-"}</span>
      <span>${job.error || ""}</span>
    `;

    els.downloadJobs.appendChild(node);
  });
}

async function loadHealth() {
  const health = await apiFetch("/health");
  els.healthStatus.textContent = health.status;
  els.ffmpegStatus.textContent = health.ffmpeg_available ? "OK" : "Missing";
  els.ffprobeStatus.textContent = health.ffprobe_available ? "OK" : "Missing";
  els.defaultProvider.textContent = health.default_provider;
}

async function loadProviders() {
  state.providers = await apiFetch("/providers");
  fillProviders();
  renderProviderModels();
}

async function loadPresets() {
  const presets = await apiFetch("/admin/models/presets", { admin: true });
  state.presets = presets.items || [];
  renderPresets();
}

async function loadLocalModels() {
  const data = await apiFetch("/admin/models/local", { admin: true });
  state.localModels = data.items || [];
  renderLocalModels();
}

async function loadRemoteModels(query = "faster-whisper") {
  const q = (query || "faster-whisper").trim();
  const data = await apiFetch(`/admin/models/remote/repos?query=${encodeURIComponent(q)}&limit=30`, {
    admin: true,
    timeoutMs: 7000,
  });
  state.remoteModels = data.items || [];
  renderRemoteModels();
}

async function loadRemoteRepoFiles(repoId, revision = "main") {
  const data = await apiFetch(
    `/admin/models/remote/files?repo_id=${encodeURIComponent(repoId)}&revision=${encodeURIComponent(revision)}`,
    { admin: true, timeoutMs: 10000 }
  );
  state.remoteRepoFiles = data.items || [];
  state.recommendedFiles = data.recommended_files || [];
  if (state.recommendedFiles.length) {
    els.downloadFiles.value = state.recommendedFiles.join(",");
  }
  renderRemoteRepoFiles();
}

async function loadJobs() {
  const data = await apiFetch("/admin/downloads", { admin: true });
  state.jobs = data.items || [];
  renderJobs();
}

async function refreshAll() {
  setStatus("در حال بروزرسانی اطلاعات...");
  const errors = [];
  const tasks = [
    loadHealth().catch((err) => errors.push(`health: ${err.message}`)),
    loadProviders().catch((err) => errors.push(`providers: ${err.message}`)),
    loadPresets().catch((err) => errors.push(`presets: ${err.message}`)),
    loadLocalModels().catch((err) => errors.push(`local: ${err.message}`)),
    loadJobs().catch((err) => errors.push(`jobs: ${err.message}`)),
  ];
  await Promise.all(tasks);

  if (errors.length) {
    setStatus(`بخشی از داده‌ها بارگذاری نشد: ${errors.join(" | ")}`, "warn");
    return;
  }
  setStatus("اطلاعات بروزرسانی شد.", "ok");
}

async function transcribeHandler(event) {
  event.preventDefault();
  const file = els.fileInput.files && els.fileInput.files[0];
  if (!file) {
    setStatus("فایل انتخاب نشده است.", "bad");
    return;
  }

  const form = new FormData();
  form.append("file", file);

  const appendIf = (key, value) => {
    if (value !== null && value !== undefined && `${value}`.trim() !== "") {
      form.append(key, `${value}`);
    }
  };

  appendIf("provider", els.providerInput.value);
  appendIf("model", els.modelInput.value);
  appendIf("language", els.languageInput.value);
  appendIf("prompt", els.promptInput.value);
  appendIf("response_format", els.responseFormatInput.value);
  appendIf("temperature", els.temperatureInput.value);

  form.append("word_timestamps", String(els.wordTimestampsInput.checked));
  form.append("segment_timestamps", String(els.segmentTimestampsInput.checked));
  form.append("vad_filter", String(els.vadFilterInput.checked));

  setStatus("در حال آپلود فایل...", "warn");
  els.transcribeResult.textContent = "...";
  setTranscribeProgress(0, "uploading", "-");

  try {
    const job = await createTranscribeJobWithProgress(form, (uploadPercent) => {
      setTranscribeProgress(uploadPercent, "uploading", "-");
      setStatus(`در حال آپلود فایل... ${uploadPercent.toFixed(0)}%`, "warn");
    });
    state.currentTranscribeJobId = job.job_id;
    setTranscribeProgress(Number(job.progress_percent || 0), job.stage || "queued", job.job_id);
    setStatus("job ترنسکریپت ساخته شد؛ در حال پردازش...", "warn");
    startTranscribePolling(job.job_id);
  } catch (err) {
    els.transcribeResult.textContent = `خطا: ${err.message}`;
    setStatus("پردازش ناموفق بود.", "bad");
    setTranscribeProgress(0, "failed", "-");
  }
}

async function downloadModelHandler() {
  const files = (els.downloadFiles.value || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

  const payload = {
    preset_name: els.downloadPreset.value || null,
    repo_id: els.downloadRepo.value.trim() || null,
    revision: els.downloadRevision.value.trim() || "main",
    output_subdir: els.downloadSubdir.value.trim() || null,
    files: files.length ? files : null,
  };

  setStatus("در حال ساخت jobهای دانلود مدل...", "warn");
  try {
    const out = await apiFetch("/admin/models/local/download", {
      method: "POST",
      admin: true,
      body: payload,
    });
    setStatus(`${out.total} job ایجاد شد.`, "ok");
    await loadJobs();
    setTimeout(() => loadLocalModels().catch(() => {}), 3000);
  } catch (err) {
    setStatus(`دانلود مدل شروع نشد: ${err.message}`, "bad");
  }
}

function stopTranscribePolling() {
  if (state.transcribePollHandle) {
    clearInterval(state.transcribePollHandle);
    state.transcribePollHandle = null;
  }
}

function renderTranscribeResult(out) {
  state.latestText = out.text || "";
  const pretty = {
    text: out.text,
    language: out.language,
    duration_seconds: out.duration_seconds,
    usage: out.usage,
    metadata: out.metadata,
    segments_count: Array.isArray(out.segments) ? out.segments.length : 0,
    words_count: Array.isArray(out.words) ? out.words.length : 0,
  };
  els.transcribeResult.textContent = JSON.stringify(pretty, null, 2);
}

function startTranscribePolling(jobId) {
  stopTranscribePolling();
  state.transcribePollHandle = setInterval(async () => {
    try {
      const job = await apiFetch(`/transcribe/jobs/${jobId}`);
      setTranscribeProgress(Number(job.progress_percent || 0), job.stage || "-", job.job_id);

      if (job.status === "completed") {
        stopTranscribePolling();
        if (job.result) {
          renderTranscribeResult(job.result);
        }
        setStatus("پردازش با موفقیت انجام شد.", "ok");
        return;
      }

      if (job.status === "failed" || job.status === "cancelled") {
        stopTranscribePolling();
        els.transcribeResult.textContent = `خطا: ${job.error || job.status}`;
        setStatus("پردازش ناموفق بود.", "bad");
      }
    } catch (err) {
      stopTranscribePolling();
      setStatus(`خطا در خواندن progress: ${err.message}`, "bad");
    }
  }, 1500);
}

function copyTextHandler() {
  const text = state.latestText || els.transcribeResult.textContent || "";
  if (!text.trim()) {
    setStatus("متنی برای کپی وجود ندارد.", "warn");
    return;
  }
  navigator.clipboard.writeText(text).then(
    () => setStatus("کپی شد.", "ok"),
    () => setStatus("کپی انجام نشد.", "bad")
  );
}

function attachEvents() {
  els.btnSaveAdmin.addEventListener("click", () => {
    saveAdmin();
    setStatus("تنظیمات admin ذخیره شد.", "ok");
  });

  els.btnReloadAll.addEventListener("click", refreshAll);
  els.btnRefreshModels.addEventListener("click", async () => {
    try {
      await loadPresets();
      await loadLocalModels();
      await loadRemoteModels(els.remoteSearchInput?.value || "faster-whisper");
      setStatus("مدل‌ها بروزرسانی شدند.", "ok");
    } catch (err) {
      setStatus(`خطا: ${err.message}`, "bad");
    }
  });

  els.btnSearchRemote?.addEventListener("click", async () => {
    try {
      await loadRemoteModels(els.remoteSearchInput?.value || "faster-whisper");
      setStatus("لیست مدل‌های آنلاین بروزرسانی شد.", "ok");
    } catch (err) {
      setStatus(`خطا در جستجوی آنلاین: ${err.message}`, "bad");
    }
  });

  els.btnRefreshJobs.addEventListener("click", async () => {
    try {
      await loadJobs();
      setStatus("jobها بروزرسانی شدند.", "ok");
    } catch (err) {
      setStatus(`خطا: ${err.message}`, "bad");
    }
  });

  els.transcribeForm.addEventListener("submit", transcribeHandler);
  els.btnDownloadModel.addEventListener("click", downloadModelHandler);
  els.btnCopyText.addEventListener("click", copyTextHandler);

  els.downloadPreset.addEventListener("change", () => {
    const chosen = state.presets.find((x) => x.name === els.downloadPreset.value);
    if (!chosen) return;
    els.downloadRepo.value = chosen.repo_id;
    if (!els.downloadSubdir.value.trim()) {
      els.downloadSubdir.value = chosen.name;
    }
    refreshRepoFiles().catch(() => {});
  });

  const refreshRepoFiles = async () => {
    const repo = els.downloadRepo.value.trim();
    if (!repo) return;
    try {
      await loadRemoteRepoFiles(repo, els.downloadRevision.value.trim() || "main");
      setStatus("فایل‌های واقعی repo دریافت شد.", "ok");
    } catch (err) {
      setStatus(`خطا در خواندن فایل‌های repo: ${err.message}`, "warn");
    }
  };
  els.downloadRepo.addEventListener("blur", refreshRepoFiles);
  els.downloadRevision.addEventListener("blur", refreshRepoFiles);
}

function startPolling() {
  if (state.pollHandle) {
    clearInterval(state.pollHandle);
  }
  state.pollHandle = setInterval(async () => {
    try {
      await loadJobs();
    } catch (_) {
      // silent in polling
    }
  }, 4000);
}

async function init() {
  loadAdmin();
  attachEvents();
  await refreshAll();
  setTimeout(() => {
    loadRemoteModels(els.remoteSearchInput?.value || "faster-whisper").catch(() => {});
  }, 50);
  startPolling();
}

init().catch((err) => {
  setStatus(`خطا در بارگذاری اولیه: ${err.message}`, "bad");
});
