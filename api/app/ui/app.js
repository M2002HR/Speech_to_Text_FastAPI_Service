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
  btnLoadConfig: $("btnLoadConfig"),
  btnUseEffectiveConfig: $("btnUseEffectiveConfig"),
  btnSaveConfig: $("btnSaveConfig"),
  configPresetSelect: $("configPresetSelect"),
  btnApplyConfigPreset: $("btnApplyConfigPreset"),
  configPath: $("configPath"),
  configPersistFile: $("configPersistFile"),
  configReloadRuntime: $("configReloadRuntime"),
  configEditor: $("configEditor"),
  configRaw: $("configRaw"),
  btnRefreshModels: $("btnRefreshModels"),
  btnRefreshJobs: $("btnRefreshJobs"),
  providerInput: $("providerInput"),
  transcribePresetSelect: $("transcribePresetSelect"),
  btnApplyTranscribePreset: $("btnApplyTranscribePreset"),
  modelInput: $("modelInput"),
  fileInput: $("fileInput"),
  languageInput: $("languageInput"),
  responseFormatInput: $("responseFormatInput"),
  temperatureInput: $("temperatureInput"),
  beamSizeInput: $("beamSizeInput"),
  bestOfInput: $("bestOfInput"),
  patienceInput: $("patienceInput"),
  promptInput: $("promptInput"),
  initialPromptInput: $("initialPromptInput"),
  conditionOnPreviousTextInput: $("conditionOnPreviousTextInput"),
  requestIdInput: $("requestIdInput"),
  repetitionPenaltyInput: $("repetitionPenaltyInput"),
  noRepeatNgramSizeInput: $("noRepeatNgramSizeInput"),
  maxNewTokensInput: $("maxNewTokensInput"),
  compressionRatioThresholdInput: $("compressionRatioThresholdInput"),
  logProbThresholdInput: $("logProbThresholdInput"),
  noSpeechThresholdInput: $("noSpeechThresholdInput"),
  promptResetOnTemperatureInput: $("promptResetOnTemperatureInput"),
  hallucinationSilenceThresholdInput: $("hallucinationSilenceThresholdInput"),
  vadThresholdInput: $("vadThresholdInput"),
  vadNegThresholdInput: $("vadNegThresholdInput"),
  vadMinSpeechDurationMsInput: $("vadMinSpeechDurationMsInput"),
  vadMinSilenceDurationMsInput: $("vadMinSilenceDurationMsInput"),
  vadSpeechPadMsInput: $("vadSpeechPadMsInput"),
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
  btnDownloadResult: $("btnDownloadResult"),
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
  latestResult: null,
  currentTranscribeJobId: null,
  transcribePollHandle: null,
  pollHandle: null,
  configFile: {},
  configEffective: {},
  configDraft: {},
  configTypeHints: {},
};

const CONFIG_PRESETS = {
  "local-max-quality": {
    label: "Local · Max Quality",
    patch: {
      transcription: {
        default_provider: "local",
        default_language: "fa",
        enable_word_timestamps: true,
        enable_segment_timestamps: true,
      },
      local: {
        model_id: "large-v3",
        device: "cuda",
        compute_type: "float16",
        beam_size: 8,
        best_of: 8,
        patience: 1.2,
        temperature: 0.0,
        vad_filter: true,
        condition_on_previous_text: true,
        repetition_penalty: 1.0,
        no_repeat_ngram_size: 0,
        compression_ratio_threshold: 2.4,
        log_prob_threshold: -1.0,
        no_speech_threshold: 0.6,
        prompt_reset_on_temperature: 0.5,
        hallucination_silence_threshold: null,
      },
      processing: {
        always_extract_audio: true,
        audio_sample_rate: 16000,
        audio_channels: 1,
      },
    },
  },
  "local-balanced": {
    label: "Local · Balanced",
    patch: {
      transcription: {
        default_provider: "local",
        default_language: "fa",
      },
      local: {
        model_id: "small",
        device: "auto",
        compute_type: "auto",
        beam_size: 5,
        best_of: 5,
        patience: 1.0,
        temperature: 0.0,
        vad_filter: true,
        condition_on_previous_text: true,
        repetition_penalty: 1.0,
        no_repeat_ngram_size: 0,
      },
    },
  },
  "local-fast": {
    label: "Local · Fast",
    patch: {
      transcription: {
        default_provider: "local",
        default_language: "fa",
        enable_word_timestamps: false,
        enable_segment_timestamps: true,
      },
      local: {
        model_id: "tiny",
        device: "auto",
        compute_type: "int8",
        beam_size: 1,
        best_of: 1,
        patience: 1.0,
        temperature: 0.0,
        vad_filter: true,
        condition_on_previous_text: true,
        repetition_penalty: 1.0,
        no_repeat_ngram_size: 0,
      },
    },
  },
  "api-openai-default": {
    label: "API · OpenAI Default",
    patch: {
      transcription: {
        default_provider: "openai",
      },
      providers: {
        openai: {
          enabled: true,
          base_url: "https://api.openai.com",
          model: "gpt-4o-transcribe",
          transcriptions_path: "/v1/audio/transcriptions",
          timeout_sec: 300,
        },
      },
    },
  },
  "api-groq-default": {
    label: "API · Groq Default",
    patch: {
      transcription: {
        default_provider: "groq",
      },
      providers: {
        groq: {
          enabled: true,
          base_url: "https://api.groq.com/openai",
          model: "whisper-large-v3",
          transcriptions_path: "/v1/audio/transcriptions",
          timeout_sec: 300,
        },
      },
    },
  },
};

const TRANSCRIBE_PRESETS = {
  "fa-max-quality": {
    label: "FA · Max Quality",
    values: {
      provider: "local",
      model: "large-v3",
      language: "fa",
      response_format: "verbose_json",
      temperature: "0",
      beam_size: "8",
      best_of: "8",
      patience: "1.2",
      prompt: "",
      initial_prompt: "",
      word_timestamps: true,
      segment_timestamps: true,
      vad_filter: true,
      condition_on_previous_text: true,
      repetition_penalty: "1.0",
      no_repeat_ngram_size: "0",
      compression_ratio_threshold: "2.4",
      log_prob_threshold: "-1.0",
      no_speech_threshold: "0.6",
      prompt_reset_on_temperature: "0.5",
      hallucination_silence_threshold: "",
    },
  },
  "fa-balanced": {
    label: "FA · Balanced",
    values: {
      provider: "local",
      model: "small",
      language: "fa",
      response_format: "verbose_json",
      temperature: "0",
      beam_size: "5",
      best_of: "5",
      patience: "1.0",
      prompt: "",
      initial_prompt: "",
      word_timestamps: false,
      segment_timestamps: true,
      vad_filter: true,
      condition_on_previous_text: true,
      repetition_penalty: "1.0",
      no_repeat_ngram_size: "0",
      compression_ratio_threshold: "2.4",
      log_prob_threshold: "-1.0",
      no_speech_threshold: "0.6",
      prompt_reset_on_temperature: "0.5",
    },
  },
  "fa-fast": {
    label: "FA · Fast",
    values: {
      provider: "local",
      model: "tiny",
      language: "fa",
      response_format: "text",
      temperature: "0",
      beam_size: "1",
      best_of: "1",
      patience: "1.0",
      prompt: "",
      initial_prompt: "",
      word_timestamps: false,
      segment_timestamps: true,
      vad_filter: true,
      condition_on_previous_text: true,
      repetition_penalty: "1.0",
      no_repeat_ngram_size: "0",
      compression_ratio_threshold: "2.4",
      log_prob_threshold: "-1.0",
      no_speech_threshold: "0.6",
      prompt_reset_on_temperature: "0.5",
    },
  },
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

function createTranscribeJobWithProgress(formData, onUploadProgress, headers = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/transcribe/jobs", true);
    xhr.timeout = 30 * 60 * 1000;
    Object.entries(headers).forEach(([key, value]) => {
      if (value !== null && value !== undefined && String(value).trim() !== "") {
        xhr.setRequestHeader(key, String(value));
      }
    });

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

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value ?? {}));
}

function deepMerge(base, override) {
  if (!isPlainObject(base)) return deepClone(override);
  const out = deepClone(base);
  if (!isPlainObject(override)) return out;
  Object.keys(override).forEach((key) => {
    if (isPlainObject(out[key]) && isPlainObject(override[key])) {
      out[key] = deepMerge(out[key], override[key]);
    } else {
      out[key] = deepClone(override[key]);
    }
  });
  return out;
}

function getByPath(obj, path) {
  return path.split(".").reduce((cursor, key) => (cursor == null ? undefined : cursor[key]), obj);
}

function setByPath(obj, path, value) {
  const keys = path.split(".");
  let cursor = obj;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const k = keys[i];
    if (!isPlainObject(cursor[k])) {
      cursor[k] = {};
    }
    cursor = cursor[k];
  }
  cursor[keys[keys.length - 1]] = value;
}

function collectLeafPaths(obj, prefix = "", out = []) {
  if (Array.isArray(obj) || !isPlainObject(obj)) {
    out.push(prefix);
    return out;
  }
  Object.keys(obj).forEach((key) => {
    const next = prefix ? `${prefix}.${key}` : key;
    collectLeafPaths(obj[key], next, out);
  });
  return out;
}

function inferValueType(value) {
  if (Array.isArray(value)) return "array";
  if (value === null) return "null";
  return typeof value;
}

function buildTypeHints() {
  const hints = {};
  [state.configEffective, state.configFile, state.configDraft].forEach((source) => {
    collectLeafPaths(source)
      .filter(Boolean)
      .forEach((path) => {
        const t = inferValueType(getByPath(source, path));
        if (!(path in hints) || hints[path] === "null") {
          hints[path] = t;
        }
      });
  });
  state.configTypeHints = hints;
}

function parseTypedValue(raw, typeHint) {
  if (typeHint === "boolean") {
    return String(raw).toLowerCase() === "true";
  }
  if (typeHint === "number") {
    const n = Number(raw);
    if (!Number.isFinite(n)) throw new Error(`عدد معتبر نیست: ${raw}`);
    return n;
  }
  if (typeHint === "array") {
    const parsed = JSON.parse(raw || "[]");
    if (!Array.isArray(parsed)) throw new Error("برای array باید JSON آرایه وارد شود.");
    return parsed;
  }
  if (raw === "null") return null;
  return String(raw);
}

function renderConfigEditor() {
  els.configEditor.innerHTML = "";
  if (!isPlainObject(state.configDraft) || !Object.keys(state.configDraft).length) {
    els.configEditor.innerHTML = '<p class="hint">ابتدا تنظیمات را بارگذاری کن.</p>';
    return;
  }

  buildTypeHints();
  const allPaths = collectLeafPaths(state.configDraft).filter(Boolean).sort();
  const groups = {};
  allPaths.forEach((path) => {
    const top = path.split(".")[0];
    if (!groups[top]) groups[top] = [];
    groups[top].push(path);
  });

  Object.keys(groups).sort().forEach((section) => {
    const card = document.createElement("article");
    card.className = "item stack-lg";
    card.innerHTML = `<div class="item-head"><strong>${section}</strong><span class="chip">${groups[section].length}</span></div>`;

    const grid = document.createElement("div");
    grid.className = "grid cols-3";

    groups[section].forEach((path) => {
      const typeHint = state.configTypeHints[path] || "string";
      const value = getByPath(state.configDraft, path);
      const label = document.createElement("label");
      const title = document.createElement("span");
      title.textContent = path;
      label.appendChild(title);

      if (typeHint === "boolean") {
        const wrap = document.createElement("label");
        wrap.className = "toggle";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(value);
        input.addEventListener("change", () => {
          setByPath(state.configDraft, path, input.checked);
          syncConfigRawFromDraft();
        });
        const txt = document.createElement("span");
        txt.textContent = input.checked ? "true" : "false";
        input.addEventListener("change", () => {
          txt.textContent = input.checked ? "true" : "false";
        });
        wrap.append(input, txt);
        label.appendChild(wrap);
      } else if (typeHint === "array") {
        const input = document.createElement("textarea");
        input.rows = 2;
        input.className = "mono";
        input.value = JSON.stringify(value ?? [], null, 2);
        input.addEventListener("change", () => {
          setByPath(state.configDraft, path, parseTypedValue(input.value, "array"));
          syncConfigRawFromDraft();
        });
        label.appendChild(input);
      } else {
        const input = document.createElement("input");
        input.type = typeHint === "number" ? "number" : "text";
        if (typeHint === "number") {
          input.step = "any";
        }
        input.value = value === null || value === undefined ? "" : String(value);
        input.placeholder = typeHint;
        input.addEventListener("change", () => {
          const raw = input.value.trim();
          const typed = raw === "" ? (typeHint === "number" ? 0 : "") : parseTypedValue(raw, typeHint);
          setByPath(state.configDraft, path, typed);
          syncConfigRawFromDraft();
        });
        label.appendChild(input);
      }

      grid.appendChild(label);
    });

    card.appendChild(grid);
    els.configEditor.appendChild(card);
  });
}

function syncConfigRawFromDraft() {
  els.configRaw.value = JSON.stringify(state.configDraft, null, 2);
}

function loadDraftFromRawInput() {
  const parsed = JSON.parse(els.configRaw.value || "{}");
  if (!isPlainObject(parsed)) {
    throw new Error("فرمت JSON باید object باشد.");
  }
  state.configDraft = parsed;
}

function setupPresetSelects() {
  els.configPresetSelect.innerHTML = "<option value=''>انتخاب preset</option>";
  Object.entries(CONFIG_PRESETS).forEach(([key, preset]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = preset.label;
    els.configPresetSelect.appendChild(opt);
  });

  els.transcribePresetSelect.innerHTML = "<option value=''>انتخاب preset</option>";
  Object.entries(TRANSCRIBE_PRESETS).forEach(([key, preset]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = preset.label;
    els.transcribePresetSelect.appendChild(opt);
  });
}

function applyConfigPreset(name) {
  const preset = CONFIG_PRESETS[name];
  if (!preset) {
    throw new Error("preset کانفیگ نامعتبر است.");
  }
  if (!isPlainObject(state.configDraft) || !Object.keys(state.configDraft).length) {
    state.configDraft = deepClone(state.configEffective || {});
  }
  state.configDraft = deepMerge(state.configDraft, preset.patch);
  renderConfigEditor();
  syncConfigRawFromDraft();
}

function applyTranscribePreset(name) {
  const preset = TRANSCRIBE_PRESETS[name];
  if (!preset) {
    throw new Error("preset ترنسکریپت نامعتبر است.");
  }
  const v = preset.values;
  els.providerInput.value = v.provider;
  els.modelInput.value = v.model;
  els.languageInput.value = v.language;
  els.responseFormatInput.value = v.response_format;
  els.temperatureInput.value = v.temperature;
  els.beamSizeInput.value = v.beam_size;
  els.bestOfInput.value = v.best_of;
  els.patienceInput.value = v.patience;
  els.promptInput.value = v.prompt;
  els.initialPromptInput.value = v.initial_prompt;
  els.repetitionPenaltyInput.value = v.repetition_penalty || "";
  els.noRepeatNgramSizeInput.value = v.no_repeat_ngram_size || "";
  els.maxNewTokensInput.value = v.max_new_tokens || "";
  els.compressionRatioThresholdInput.value = v.compression_ratio_threshold || "";
  els.logProbThresholdInput.value = v.log_prob_threshold || "";
  els.noSpeechThresholdInput.value = v.no_speech_threshold || "";
  els.promptResetOnTemperatureInput.value = v.prompt_reset_on_temperature || "";
  els.hallucinationSilenceThresholdInput.value = v.hallucination_silence_threshold || "";
  els.vadThresholdInput.value = v.vad_threshold || "";
  els.vadNegThresholdInput.value = v.vad_neg_threshold || "";
  els.vadMinSpeechDurationMsInput.value = v.vad_min_speech_duration_ms || "";
  els.vadMinSilenceDurationMsInput.value = v.vad_min_silence_duration_ms || "";
  els.vadSpeechPadMsInput.value = v.vad_speech_pad_ms || "";
  els.wordTimestampsInput.checked = Boolean(v.word_timestamps);
  els.segmentTimestampsInput.checked = Boolean(v.segment_timestamps);
  els.vadFilterInput.checked = Boolean(v.vad_filter);
  els.conditionOnPreviousTextInput.checked = Boolean(v.condition_on_previous_text);
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

function applyConfigPayload(payload, source = "file") {
  state.configFile = isPlainObject(payload.file_config) ? payload.file_config : {};
  state.configEffective = isPlainObject(payload.effective_config) ? payload.effective_config : {};

  const base = deepClone(state.configEffective);
  const fileOverlay = deepClone(state.configFile);
  const mergedDraft = deepMerge(base, fileOverlay);

  state.configDraft = source === "effective" ? deepClone(state.configEffective) : mergedDraft;
  els.configPath.value = payload.config_path || "";
  renderConfigEditor();
  syncConfigRawFromDraft();
}

async function loadConfigEditable(source = "file") {
  const payload = await apiFetch("/admin/system/config-editable", { admin: true });
  applyConfigPayload(payload, source);
}

async function saveConfigEditable() {
  loadDraftFromRawInput();
  const payload = await apiFetch("/admin/system/config-editable", {
    method: "PUT",
    admin: true,
    timeoutMs: 30000,
    body: {
      config: state.configDraft,
      persist_to_file: Boolean(els.configPersistFile.checked),
      reload_runtime: Boolean(els.configReloadRuntime.checked),
    },
  });
  applyConfigPayload(payload, "file");
}

async function refreshAll() {
  setStatus("در حال بروزرسانی اطلاعات...");
  const errors = [];
  const tasks = [
    loadHealth().catch((err) => errors.push(`health: ${err.message}`)),
    loadProviders().catch((err) => errors.push(`providers: ${err.message}`)),
    loadConfigEditable("file").catch((err) => errors.push(`config: ${err.message}`)),
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
  appendIf("beam_size", els.beamSizeInput.value);
  appendIf("best_of", els.bestOfInput.value);
  appendIf("patience", els.patienceInput.value);
  appendIf("initial_prompt", els.initialPromptInput.value);
  appendIf("repetition_penalty", els.repetitionPenaltyInput.value);
  appendIf("no_repeat_ngram_size", els.noRepeatNgramSizeInput.value);
  appendIf("max_new_tokens", els.maxNewTokensInput.value);
  appendIf("compression_ratio_threshold", els.compressionRatioThresholdInput.value);
  appendIf("log_prob_threshold", els.logProbThresholdInput.value);
  appendIf("no_speech_threshold", els.noSpeechThresholdInput.value);
  appendIf("prompt_reset_on_temperature", els.promptResetOnTemperatureInput.value);
  appendIf("hallucination_silence_threshold", els.hallucinationSilenceThresholdInput.value);
  appendIf("vad_threshold", els.vadThresholdInput.value);
  appendIf("vad_neg_threshold", els.vadNegThresholdInput.value);
  appendIf("vad_min_speech_duration_ms", els.vadMinSpeechDurationMsInput.value);
  appendIf("vad_min_silence_duration_ms", els.vadMinSilenceDurationMsInput.value);
  appendIf("vad_speech_pad_ms", els.vadSpeechPadMsInput.value);

  form.append("word_timestamps", String(els.wordTimestampsInput.checked));
  form.append("segment_timestamps", String(els.segmentTimestampsInput.checked));
  form.append("vad_filter", String(els.vadFilterInput.checked));
  form.append("condition_on_previous_text", String(els.conditionOnPreviousTextInput.checked));

  const requestId = (els.requestIdInput.value || "").trim();

  setStatus("در حال آپلود فایل...", "warn");
  els.transcribeResult.textContent = "...";
  setTranscribeProgress(0, "uploading", "-");

  try {
    const job = await createTranscribeJobWithProgress(
      form,
      (uploadPercent) => {
        setTranscribeProgress(uploadPercent, "uploading", "-");
        setStatus(`در حال آپلود فایل... ${uploadPercent.toFixed(0)}%`, "warn");
      },
      requestId ? { "x-request-id": requestId } : {}
    );
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
  state.latestResult = out;
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

function downloadResultHandler() {
  const textBody = (state.latestText || "").trim();
  const fallback = state.latestResult ? JSON.stringify(state.latestResult, null, 2) : (els.transcribeResult.textContent || "");
  const body = textBody || fallback;
  if (!body.trim()) {
    setStatus("خروجی برای دانلود وجود ندارد.", "warn");
    return;
  }

  const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const link = document.createElement("a");
  link.href = url;
  link.download = `transcription-${stamp}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus("فایل خروجی دانلود شد.", "ok");
}

function attachEvents() {
  els.btnSaveAdmin.addEventListener("click", () => {
    saveAdmin();
    setStatus("تنظیمات admin ذخیره شد.", "ok");
  });

  els.btnReloadAll.addEventListener("click", refreshAll);
  els.btnLoadConfig.addEventListener("click", async () => {
    try {
      await loadConfigEditable("file");
      setStatus("تنظیمات از فایل بارگذاری شد.", "ok");
    } catch (err) {
      setStatus(`خطا در بارگذاری تنظیمات: ${err.message}`, "bad");
    }
  });
  els.btnUseEffectiveConfig.addEventListener("click", () => {
    state.configDraft = deepClone(state.configEffective || {});
    renderConfigEditor();
    syncConfigRawFromDraft();
    setStatus("Effective config در فرم قرار گرفت.", "ok");
  });
  els.btnSaveConfig.addEventListener("click", async () => {
    try {
      await saveConfigEditable();
      setStatus("تنظیمات ذخیره و اعمال شد.", "ok");
      await loadHealth();
      await loadProviders();
    } catch (err) {
      setStatus(`ذخیره تنظیمات ناموفق بود: ${err.message}`, "bad");
    }
  });
  els.configRaw.addEventListener("blur", () => {
    try {
      loadDraftFromRawInput();
      renderConfigEditor();
    } catch (err) {
      setStatus(`JSON نامعتبر: ${err.message}`, "bad");
    }
  });
  els.btnApplyConfigPreset.addEventListener("click", () => {
    const name = els.configPresetSelect.value;
    if (!name) {
      setStatus("یک preset کانفیگ انتخاب کن.", "warn");
      return;
    }
    try {
      applyConfigPreset(name);
      setStatus("preset کانفیگ اعمال شد.", "ok");
    } catch (err) {
      setStatus(`خطا در preset کانفیگ: ${err.message}`, "bad");
    }
  });
  els.btnApplyTranscribePreset.addEventListener("click", () => {
    const name = els.transcribePresetSelect.value;
    if (!name) {
      setStatus("یک preset ترنسکریپت انتخاب کن.", "warn");
      return;
    }
    try {
      applyTranscribePreset(name);
      setStatus("preset ترنسکریپت اعمال شد.", "ok");
    } catch (err) {
      setStatus(`خطا در preset ترنسکریپت: ${err.message}`, "bad");
    }
  });

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
  els.btnDownloadResult.addEventListener("click", downloadResultHandler);

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
  setupPresetSelects();
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
