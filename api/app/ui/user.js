const $ = (id) => document.getElementById(id);

const STABLE_PROFILE = {
  provider: "local",
  response_format: "verbose_json",
  temperature: "0",
  beam_size: "10",
  best_of: "10",
  patience: "1.3",
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
  chunking_enabled: true,
};

const DEFAULT_RUNTIME_SETTINGS = {
  model: "large-v3",
  chunkMinutes: 10,
  chunkOverlapMinutes: 5,
};

const LANGUAGE_CODES = [
  "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh", "yue",
];

const I18N = {
  fa: {
    app_badge: "Tootak · پنل کاربری",
    app_title: "پنل کاربری تبدیل گفتار",
    health_service: "سرویس",
    health_ffmpeg: "ffmpeg",
    health_ffprobe: "ffprobe",
    health_provider: "Provider",
    panel_processing: "پردازش",
    label_file: "فایل صوتی/ویدیویی",
    label_language: "زبان متن",
    label_vocab: "واژگان کمکی (اختیاری)",
    placeholder_vocab: "نام‌ها، اصطلاحات و واژه‌های حساس",
    label_progress: "پیشرفت",
    panel_output: "متن خروجی",
    result_empty: "هنوز پردازشی انجام نشده است.",
    result_loading: "در حال آماده سازی...",
    tip_ui_lang: "تغییر زبان رابط",
    tip_theme: "حالت روشن/تاریک",
    tip_settings: "تنظیمات",
    tip_lab: "رفتن به پنل Lab",
    tip_start: "شروع پردازش",
    tip_copy: "کپی متن",
    tip_download: "دانلود فایل",
    tip_prompt_modal: "پرامپت آماده سازی خروجی",
    tip_copy_prompt: "کپی پرامپت",
    tip_close: "بستن",
    tip_save_settings: "ذخیره تنظیمات",
    tip_language_help: "زبان متن خروجی را مشخص می‌کند. حالت خودکار برای فایل‌های چندزبانه مناسب است.",
    tip_vocab_help: "کلمات مهم پروژه را وارد کن تا مدل در تشخیص آن‌ها دقیق‌تر عمل کند.",
    lang_auto: "تشخیص خودکار",
    lang_fa: "فارسی (fa)",
    lang_en: "English (en)",
    status_ready: "آماده پردازش",
    status_file_missing: "فایل انتخاب نشده است.",
    status_uploading: "در حال آپلود فایل...",
    status_uploading_pct: "در حال آپلود فایل... {{percent}}%",
    status_job_started: "پردازش شروع شد.",
    status_running: "در حال پردازش...",
    status_queued: "در صف پردازش...",
    status_success: "پردازش با موفقیت انجام شد.",
    status_failed_start: "شروع پردازش ناموفق بود.",
    status_failed: "پردازش ناموفق بود.",
    status_poll_error: "خطا در دریافت پیشرفت: {{msg}}",
    status_copy_empty: "متنی برای کپی وجود ندارد.",
    status_copy_ok: "متن کپی شد.",
    status_copy_fail: "کپی انجام نشد.",
    status_download_empty: "خروجی برای دانلود وجود ندارد.",
    status_download_ok: "فایل خروجی دانلود شد.",
    status_load_error: "خطا در بارگذاری اولیه: {{msg}}",
    status_settings_saved: "تنظیمات ذخیره شد.",
    status_settings_invalid: "اورلپ باید کمتر از چانک باشد.",
    status_settings_invalid_number: "مقادیر تنظیمات معتبر نیست.",
    status_prompt_copied: "پرامپت کپی شد.",
    status_prompt_copy_failed: "کپی پرامپت انجام نشد.",
    error_prefix: "خطا",
    health_ok: "OK",
    health_missing: "ناموجود",
    job_label: "job",
    stage_label: "stage",
    stage_uploading: "آپلود",
    stage_queued: "در صف",
    stage_validating: "اعتبارسنجی",
    stage_preparing_audio: "استخراج صدا",
    stage_loading_model: "بارگذاری مدل",
    stage_transcribing: "ترنسکریپت",
    stage_finalizing: "نهایی سازی",
    stage_completed: "تکمیل",
    stage_failed: "خطا",
    stage_cancelled: "لغو",
    settings_title: "تنظیمات",
    settings_tab: "تنظیمات",
    about_tab: "درباره ما",
    settings_model: "مدل",
    settings_chunk: "چانک (دقیقه)",
    settings_overlap: "اورلپ (دقیقه)",
    settings_hint: "تنظیمات در اجرای بعدی اعمال می‌شود.",
    settings_service_title: "وضعیت سرویس",
    about_title: "درباره Tootak",
    about_text_1: "Tootak یک پنل دقیق برای تبدیل گفتار به متن است که روی پایداری خروجی فایل‌های بلند تمرکز دارد.",
    about_text_2: "طراحی این پنل برای کاربران عمومی و حرفه‌ای انجام شده: اجرای ساده در پنل کاربری و کنترل کامل در پنل Lab.",
    about_text_3: "هسته پردازش برای مدیریت فایل‌های طولانی، کاهش تکرارهای انتهایی و نگه‌داشتن پیوستگی متن بهینه‌سازی شده است.",
    about_text_4: "در پنل کاربری تلاش شده خروجی مرحله‌به‌مرحله نمایش داده شود تا کاربر حین پردازش، از وضعیت واقعی کار مطلع باشد.",
    about_text_5: "خروجی نهایی به شکلی آماده می‌شود که بتوانی راحت آن را ویرایش کنی، ارائه بدهی یا به فرمت‌های قابل انتشار تبدیل کنی.",
    prompt_modal_title: "آماده ساز پرامپت خروجی",
    prompt_helper_intro: "برای تبدیل خروجی خام به متن تمیز و قابل ارائه، این پرامپت را کپی کن و همراه متن خروجی استفاده کن.",
    prompt_step_1: "اول متن خروجی را از همین صفحه کپی کن.",
    prompt_step_2: "پرامپت آماده را کپی کن.",
    prompt_step_3: "پرامپت را ارسال کن و متن خروجی را جایگزین placeholder کن.",
    prompt_target_format: "فرمت مقصد",
    prompt_language_label: "زبان پرامپت",
    prompt_topic_label: "موضوع متن (اختیاری)",
    prompt_topic_placeholder: "مثلا: جلسه تحقیقاتی، مصاحبه، کلاس آموزشی",
    prompt_lang_fa: "فارسی",
    prompt_lang_en: "English",
  },
  en: {
    app_badge: "Tootak · User Panel",
    app_title: "Speech-to-Text User Panel",
    health_service: "Service",
    health_ffmpeg: "ffmpeg",
    health_ffprobe: "ffprobe",
    health_provider: "Provider",
    panel_processing: "Processing",
    label_file: "Audio/Video file",
    label_language: "Transcription language",
    label_vocab: "Vocabulary bias (optional)",
    placeholder_vocab: "Names, terms, and sensitive words",
    label_progress: "Progress",
    panel_output: "Output text",
    result_empty: "No transcription yet.",
    result_loading: "Preparing...",
    tip_ui_lang: "Switch UI language",
    tip_theme: "Toggle light/dark mode",
    tip_settings: "Settings",
    tip_lab: "Open Lab panel",
    tip_start: "Start processing",
    tip_copy: "Copy text",
    tip_download: "Download file",
    tip_prompt_modal: "Prompt helper",
    tip_copy_prompt: "Copy prompt",
    tip_close: "Close",
    tip_save_settings: "Save settings",
    tip_language_help: "Sets the output transcription language. Auto is useful for multilingual files.",
    tip_vocab_help: "Add important project words to improve recognition consistency.",
    lang_auto: "Auto detect",
    lang_fa: "Persian (fa)",
    lang_en: "English (en)",
    status_ready: "Ready",
    status_file_missing: "No file selected.",
    status_uploading: "Uploading file...",
    status_uploading_pct: "Uploading file... {{percent}}%",
    status_job_started: "Job created. Processing started.",
    status_running: "Processing...",
    status_queued: "Queued...",
    status_success: "Processing completed successfully.",
    status_failed_start: "Failed to start processing.",
    status_failed: "Processing failed.",
    status_poll_error: "Progress polling failed: {{msg}}",
    status_copy_empty: "No text to copy.",
    status_copy_ok: "Text copied.",
    status_copy_fail: "Copy failed.",
    status_download_empty: "No output to download.",
    status_download_ok: "Output file downloaded.",
    status_load_error: "Initial load failed: {{msg}}",
    status_settings_saved: "Settings saved.",
    status_settings_invalid: "Overlap must be smaller than chunk size.",
    status_settings_invalid_number: "Settings values are invalid.",
    status_prompt_copied: "Prompt copied.",
    status_prompt_copy_failed: "Prompt copy failed.",
    error_prefix: "Error",
    health_ok: "OK",
    health_missing: "Missing",
    job_label: "job",
    stage_label: "stage",
    stage_uploading: "uploading",
    stage_queued: "queued",
    stage_validating: "validating",
    stage_preparing_audio: "preparing audio",
    stage_loading_model: "loading model",
    stage_transcribing: "transcribing",
    stage_finalizing: "finalizing",
    stage_completed: "completed",
    stage_failed: "failed",
    stage_cancelled: "cancelled",
    settings_title: "Settings",
    settings_tab: "Settings",
    about_tab: "About",
    settings_model: "Model",
    settings_chunk: "Chunk (min)",
    settings_overlap: "Overlap (min)",
    settings_hint: "Settings will be used in the next run.",
    settings_service_title: "Service status",
    about_title: "About Tootak",
    about_text_1: "Tootak is a precision speech-to-text panel focused on stable output for long-form recordings.",
    about_text_2: "It is designed for both everyday and advanced users: simple execution in User Panel and full control in Lab.",
    about_text_3: "The processing core is tuned for long files, reducing tail repeats and keeping text continuity stable.",
    about_text_4: "The user panel streams output progressively so you can track real progress while transcription is running.",
    about_text_5: "Final output is prepared so you can edit, present, or convert it into publishable formats faster.",
    prompt_modal_title: "Output prompt helper",
    prompt_helper_intro: "Copy this prepared prompt and use it with your raw output to get clean, presentable text.",
    prompt_step_1: "Copy the output text from this page.",
    prompt_step_2: "Copy the prepared prompt.",
    prompt_step_3: "Send the prompt and replace the placeholder with your transcription text.",
    prompt_target_format: "Target format",
    prompt_language_label: "Prompt language",
    prompt_topic_label: "Text topic (optional)",
    prompt_topic_placeholder: "e.g. research meeting, interview, educational class",
    prompt_lang_fa: "Persian",
    prompt_lang_en: "English",
  },
};

const THEME_KEY = "tootak_user_theme";
const UI_LANG_KEY = "tootak_user_ui_lang";
const TRANSCRIBE_LANG_KEY = "tootak_user_transcribe_lang";
const RUNTIME_SETTINGS_KEY = "tootak_runtime_profile";

const els = {
  toastRoot: $("toastRoot"),
  uiLangToggle: $("uiLangToggle"),
  themeToggle: $("themeToggle"),
  themeIcon: $("themeIcon"),
  settingsBtn: $("settingsBtn"),

  transcribeForm: $("transcribeForm"),
  fileInput: $("fileInput"),
  languageSelect: $("languageSelect"),
  vocabularyBiasInput: $("vocabularyBiasInput"),
  btnTranscribe: $("btnTranscribe"),
  transcribeStatus: $("transcribeStatus"),
  transcribeResult: $("transcribeResult"),
  transcribePercent: $("transcribePercent"),
  transcribeProgressBar: $("transcribeProgressBar"),
  transcribeJobMeta: $("transcribeJobMeta"),
  btnCopyText: $("btnCopyText"),
  btnDownloadResult: $("btnDownloadResult"),

  btnOpenPromptModal: $("btnOpenPromptModal"),
  promptModal: $("promptModal"),
  promptModalClose: $("promptModalClose"),
  promptFormatSelect: $("promptFormatSelect"),
  promptLanguageSelect: $("promptLanguageSelect"),
  promptTopicInput: $("promptTopicInput"),
  preparedPromptText: $("preparedPromptText"),
  btnCopyPrompt: $("btnCopyPrompt"),

  settingsModal: $("settingsModal"),
  settingsModalClose: $("settingsModalClose"),
  settingsModalTitle: $("settingsModalTitle"),
  modalTabSettings: $("modalTabSettings"),
  modalTabAbout: $("modalTabAbout"),
  settingsView: $("settingsView"),
  aboutView: $("aboutView"),
  settingModel: $("settingModel"),
  settingChunkMinutes: $("settingChunkMinutes"),
  settingOverlapMinutes: $("settingOverlapMinutes"),
  btnSaveRuntimeSettings: $("btnSaveRuntimeSettings"),
  settingsSaveHint: $("settingsSaveHint"),

  modalHealthStatus: $("modalHealthStatus"),
  modalFfmpegStatus: $("modalFfmpegStatus"),
  modalFfprobeStatus: $("modalFfprobeStatus"),
  modalDefaultProvider: $("modalDefaultProvider"),
};

const state = {
  latestText: "",
  latestResult: null,
  currentJobId: "-",
  pollHandle: null,
  currentProgress: 0,
  currentStage: "queued",
  uiLang: "fa",
  status: {
    raw: false,
    key: "status_ready",
    params: {},
    cls: "ok",
    text: "",
  },
  stream: {
    displayed: "",
    target: "",
    timer: null,
    lastTargetUpdateAt: 0,
    charsPerSec: 36,
  },
  progress: {
    displayed: 0,
    target: 0,
    animTimer: null,
    lastTargetAt: 0,
    velocityPerSec: 18,
  },
  runtimeSettings: { ...DEFAULT_RUNTIME_SETTINGS },
};

function t(key, params = {}) {
  const bundle = I18N[state.uiLang] || I18N.fa;
  const template = bundle[key] || I18N.fa[key] || key;
  return String(template).replace(/{{\s*([\w-]+)\s*}}/g, (_, name) => {
    const value = params[name];
    return value === undefined || value === null ? "" : String(value);
  });
}

function normalizeUiLang(value) {
  return value === "en" ? "en" : "fa";
}

function setStatusRaw(text, cls = "") {
  state.status = { raw: true, text: String(text || ""), cls, key: "", params: {} };
  renderStatus();
}

function setStatusByKey(key, cls = "", params = {}) {
  state.status = { raw: false, key, params, cls, text: "" };
  renderStatus();
}

function renderStatus() {
  if (!els.transcribeStatus) return;
  const text = state.status.raw ? state.status.text : t(state.status.key, state.status.params);
  els.transcribeStatus.className = `hint ${state.status.cls}`.trim();
  els.transcribeStatus.textContent = text;
}

function showToast(message, type = "info", durationMs = 3200) {
  if (!els.toastRoot) return;
  const node = document.createElement("div");
  node.className = `toast toast-${type}`;
  node.textContent = message;
  els.toastRoot.appendChild(node);
  requestAnimationFrame(() => node.classList.add("show"));

  setTimeout(() => {
    node.classList.remove("show");
    setTimeout(() => node.remove(), 220);
  }, durationMs);
}

function toastByKey(key, type = "info", params = {}, durationMs = 3200) {
  showToast(t(key, params), type, durationMs);
}

function applyI18nText() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!key) return;
    if (el.id === "transcribeResult" && state.stream.displayed.trim()) return;
    el.textContent = t(key);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });

  document.querySelectorAll("[data-i18n-title-key]").forEach((el) => {
    const key = el.getAttribute("data-i18n-title-key");
    if (!key) return;
    el.setAttribute("data-tooltip", t(key));
  });

  if (els.transcribeResult && !state.stream.displayed.trim()) {
    els.transcribeResult.textContent = t("result_empty");
  }

  if (els.settingsSaveHint) {
    els.settingsSaveHint.textContent = t("settings_hint");
  }

  if (els.promptLanguageSelect) {
    const current = els.promptLanguageSelect.value || "fa";
    els.promptLanguageSelect.innerHTML = `
      <option value="fa">${t("prompt_lang_fa")}</option>
      <option value="en">${t("prompt_lang_en")}</option>
    `;
    els.promptLanguageSelect.value = current === "en" ? "en" : "fa";
  }
}

function applyUiLanguage(lang) {
  state.uiLang = normalizeUiLang(lang);
  localStorage.setItem(UI_LANG_KEY, state.uiLang);

  document.documentElement.setAttribute("lang", state.uiLang);
  document.documentElement.setAttribute("dir", state.uiLang === "fa" ? "rtl" : "ltr");

  applyI18nText();
  initLanguageSelect();
  updatePromptTemplate();
  setProgress(state.currentProgress, state.currentStage, state.currentJobId);
  renderStatus();
}

function toggleUiLanguage() {
  applyUiLanguage(state.uiLang === "fa" ? "en" : "fa");
}

function applyTheme(theme) {
  const normalized = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", normalized);
  localStorage.setItem(THEME_KEY, normalized);
  if (els.themeIcon) {
    els.themeIcon.className = normalized === "dark" ? "fi fi-rr-moon-stars" : "fi fi-rr-sun";
  }
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  applyTheme(saved || "dark");
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
}

function initLanguageSelect() {
  if (!els.languageSelect) return;

  const previous = (els.languageSelect.value || localStorage.getItem(TRANSCRIBE_LANG_KEY) || "").trim();
  const seen = new Set(["fa", "en"]);

  els.languageSelect.innerHTML = "";

  const autoOpt = document.createElement("option");
  autoOpt.value = "";
  autoOpt.textContent = t("lang_auto");
  els.languageSelect.appendChild(autoOpt);

  const faOpt = document.createElement("option");
  faOpt.value = "fa";
  faOpt.textContent = t("lang_fa");
  els.languageSelect.appendChild(faOpt);

  const enOpt = document.createElement("option");
  enOpt.value = "en";
  enOpt.textContent = t("lang_en");
  els.languageSelect.appendChild(enOpt);

  LANGUAGE_CODES.forEach((code) => {
    if (seen.has(code)) return;
    const opt = document.createElement("option");
    opt.value = code;
    opt.textContent = code;
    els.languageSelect.appendChild(opt);
  });

  const picked = previous && (previous === "" || LANGUAGE_CODES.includes(previous)) ? previous : "";
  els.languageSelect.value = picked;
}

function normalizeStageKey(stage) {
  const clean = String(stage || "").trim().toLowerCase();
  if (!clean) return "";
  return clean.replace(/[^a-z0-9]+/g, "_");
}

function stageLabel(stage) {
  const normalized = normalizeStageKey(stage);
  if (!normalized) return "-";
  const key = `stage_${normalized}`;
  const translated = t(key);
  return translated === key ? String(stage) : translated;
}

function updateProgressUi(value) {
  const shown = Math.max(0, Math.min(100, Number(value || 0)));
  if (els.transcribeProgressBar) {
    els.transcribeProgressBar.style.width = `${shown}%`;
  }
  if (els.transcribePercent) {
    els.transcribePercent.textContent = `${shown.toFixed(1)}%`;
  }
}

function ensureProgressAnimator() {
  if (state.progress.animTimer) return;

  state.progress.animTimer = setInterval(() => {
    const displayed = state.progress.displayed;
    const target = state.progress.target;
    const remain = target - displayed;
    if (remain <= 0.01) {
      state.progress.displayed = target;
      updateProgressUi(state.progress.displayed);
      clearInterval(state.progress.animTimer);
      state.progress.animTimer = null;
      return;
    }

    const perTickBase = state.progress.velocityPerSec / 30;
    const step = Math.min(remain, Math.max(0.08, perTickBase));
    state.progress.displayed += step;
    updateProgressUi(state.progress.displayed);
  }, 33);
}

function setProgress(percent, stage = "-", jobId = "-") {
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  const now = performance.now();
  const dtSec = state.progress.lastTargetAt > 0 ? Math.max((now - state.progress.lastTargetAt) / 1000, 0.05) : 1;
  const dp = Math.max(0, p - state.progress.target);

  state.currentProgress = p;
  state.currentStage = stage || "-";
  state.currentJobId = jobId || "-";

  state.progress.target = p;
  state.progress.velocityPerSec = dp > 0 ? Math.min(24, Math.max(1.8, dp / dtSec)) : Math.max(1.2, state.progress.velocityPerSec * 0.92);
  state.progress.lastTargetAt = now;

  if (p === 0) {
    state.progress.displayed = p;
    updateProgressUi(p);
    if (state.progress.animTimer) {
      clearInterval(state.progress.animTimer);
      state.progress.animTimer = null;
    }
  } else {
    if (p >= 100) {
      state.progress.velocityPerSec = Math.max(state.progress.velocityPerSec, 10);
    }
    ensureProgressAnimator();
  }

  if (els.transcribeJobMeta) {
    const shortId = state.currentJobId && state.currentJobId !== "-" ? String(state.currentJobId).slice(0, 8) : "-";
    els.transcribeJobMeta.textContent = `${t("job_label")}: ${shortId} | ${t("stage_label")}: ${stageLabel(state.currentStage)}`;
  }
}

function resetStream() {
  if (state.stream.timer) {
    clearInterval(state.stream.timer);
    state.stream.timer = null;
  }
  state.stream.displayed = "";
  state.stream.target = "";
  state.stream.lastTargetUpdateAt = 0;
  state.stream.charsPerSec = 36;
}

function calcStreamStep(remaining) {
  const perTick = state.stream.charsPerSec / 30;
  return Math.min(remaining, Math.max(1, Math.ceil(perTick)));
}

function renderDisplayedText() {
  if (!els.transcribeResult) return;
  if (state.stream.displayed.trim()) {
    els.transcribeResult.textContent = state.stream.displayed;
    const desired = els.transcribeResult.scrollHeight - els.transcribeResult.clientHeight;
    if (desired > 0) {
      const delta = desired - els.transcribeResult.scrollTop;
      els.transcribeResult.scrollTop += delta * 0.12;
    }
  } else {
    els.transcribeResult.textContent = t("result_empty");
  }
}

function ensureStreamTimer() {
  if (state.stream.timer) return;

  state.stream.timer = setInterval(() => {
    const remaining = state.stream.target.length - state.stream.displayed.length;
    if (remaining <= 0) {
      clearInterval(state.stream.timer);
      state.stream.timer = null;
      return;
    }

    const step = Math.min(calcStreamStep(remaining), remaining);
    state.stream.displayed += state.stream.target.slice(
      state.stream.displayed.length,
      state.stream.displayed.length + step
    );
    renderDisplayedText();
  }, 26);
}

function setStreamTarget(text, { immediate = false } = {}) {
  const normalized = text === null || text === undefined ? "" : String(text);
  state.latestText = normalized;

  const now = performance.now();
  const deltaChars = Math.max(0, normalized.length - state.stream.target.length);
  if (deltaChars > 0) {
    const dtSec = state.stream.lastTargetUpdateAt > 0 ? Math.max((now - state.stream.lastTargetUpdateAt) / 1000, 0.05) : 1;
    const detectedRate = deltaChars / dtSec;
    state.stream.charsPerSec = Math.min(220, Math.max(8, detectedRate * 0.9));
    state.stream.lastTargetUpdateAt = now;
  }

  state.stream.target = normalized;

  if (normalized.length < state.stream.displayed.length) {
    state.stream.displayed = normalized;
    renderDisplayedText();
    return;
  }

  if (immediate) {
    state.stream.displayed = normalized;
    renderDisplayedText();
    if (state.stream.timer) {
      clearInterval(state.stream.timer);
      state.stream.timer = null;
    }
    return;
  }

  ensureStreamTimer();
}

function loadRuntimeSettings() {
  const raw = localStorage.getItem(RUNTIME_SETTINGS_KEY);
  if (!raw) {
    state.runtimeSettings = { ...DEFAULT_RUNTIME_SETTINGS };
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    const chunkMinutes = Number(parsed.chunkMinutes);
    const overlapMinutes = Number(parsed.chunkOverlapMinutes);
    state.runtimeSettings = {
      model: String(parsed.model || DEFAULT_RUNTIME_SETTINGS.model),
      chunkMinutes: Number.isFinite(chunkMinutes) && chunkMinutes > 0 ? chunkMinutes : DEFAULT_RUNTIME_SETTINGS.chunkMinutes,
      chunkOverlapMinutes: Number.isFinite(overlapMinutes) && overlapMinutes >= 0 ? overlapMinutes : DEFAULT_RUNTIME_SETTINGS.chunkOverlapMinutes,
    };
  } catch {
    state.runtimeSettings = { ...DEFAULT_RUNTIME_SETTINGS };
  }
}

function renderRuntimeSettings() {
  if (els.settingModel) els.settingModel.value = state.runtimeSettings.model;
  if (els.settingChunkMinutes) els.settingChunkMinutes.value = String(state.runtimeSettings.chunkMinutes);
  if (els.settingOverlapMinutes) els.settingOverlapMinutes.value = String(state.runtimeSettings.chunkOverlapMinutes);
}

function saveRuntimeSettingsFromInputs() {
  const model = String(els.settingModel?.value || "").trim() || DEFAULT_RUNTIME_SETTINGS.model;
  const chunkMinutes = Number(els.settingChunkMinutes?.value);
  const overlapMinutes = Number(els.settingOverlapMinutes?.value);

  if (!Number.isFinite(chunkMinutes) || chunkMinutes <= 0 || !Number.isFinite(overlapMinutes) || overlapMinutes < 0) {
    setStatusByKey("status_settings_invalid_number", "bad");
    toastByKey("status_settings_invalid_number", "error");
    return false;
  }

  if (overlapMinutes >= chunkMinutes) {
    setStatusByKey("status_settings_invalid", "bad");
    toastByKey("status_settings_invalid", "error");
    return false;
  }

  state.runtimeSettings = {
    model,
    chunkMinutes,
    chunkOverlapMinutes: overlapMinutes,
  };

  localStorage.setItem(RUNTIME_SETTINGS_KEY, JSON.stringify(state.runtimeSettings));
  setStatusByKey("status_settings_saved", "ok");
  toastByKey("status_settings_saved", "success");
  return true;
}

function buildTranscribeProfile() {
  const chunkMinutes = Number(state.runtimeSettings.chunkMinutes);
  const overlapMinutes = Number(state.runtimeSettings.chunkOverlapMinutes);

  return {
    ...STABLE_PROFILE,
    model: state.runtimeSettings.model,
    chunk_minutes: String(chunkMinutes),
    chunk_overlap_minutes: String(overlapMinutes),
    chunk_min_duration_minutes: String(chunkMinutes),
  };
}

function openModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.remove("hidden");
}

function closeModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.add("hidden");
}

function setSettingsMode(mode) {
  const showSettings = mode !== "about";

  if (els.modalTabSettings) els.modalTabSettings.classList.toggle("active", showSettings);
  if (els.modalTabAbout) els.modalTabAbout.classList.toggle("active", !showSettings);
  if (els.settingsView) els.settingsView.classList.toggle("hidden", !showSettings);
  if (els.aboutView) els.aboutView.classList.toggle("hidden", showSettings);
  if (els.settingsModalTitle) {
    els.settingsModalTitle.textContent = showSettings ? t("settings_title") : t("about_title");
  }
}

function openSettingsModal(mode = "settings") {
  setSettingsMode(mode);
  renderRuntimeSettings();
  loadHealth().catch(() => null);
  openModal(els.settingsModal);
}

function closeAllModals() {
  closeModal(els.settingsModal);
  closeModal(els.promptModal);
}

function currentFormatLabel(format, lang = state.uiLang) {
  switch (format) {
    case "markdown":
      return lang === "fa" ? "مارک‌داون" : "Markdown";
    case "html":
      return "HTML";
    default:
      return lang === "fa" ? "متن ساده" : "Plain text";
  }
}

function buildPreparedPrompt(format, promptLang, topic) {
  const lang = promptLang === "en" ? "en" : "fa";
  const formatLabel = currentFormatLabel(format, lang);
  const topicText = String(topic || "").trim();

  if (lang === "en") {
    const topicBlock = topicText
      ? `\nTopic context:\n- ${topicText}\n`
      : "\n";
    return `You are an expert transcription editor.

I will provide raw speech-to-text output. Rewrite and clean it into a fully readable ${formatLabel} document.
${topicBlock}

Rules:
1. Keep the full content. Do not summarize.
2. Fix misspellings and broken words using context.
3. Preserve the original meaning and order.
4. Remove obvious noise/repetitions unless they carry meaning.
5. Use clean headings/paragraphs appropriate for ${formatLabel}.
6. If a word is unclear, infer it from context.

Output requirements:
- Return only the final ${formatLabel} content.
- No extra explanations.

RAW TRANSCRIPTION:
<<<RAW_TRANSCRIPTION_TEXT>>>`;
  }

  const topicBlockFa = topicText
    ? `\nموضوع تقریبی متن:\n- ${topicText}\n`
    : "\n";
  return `تو یک ویرایشگر حرفه‌ای متن ترنسکریپت هستی.

من خروجی خام تبدیل گفتار را می‌دهم. آن را به یک متن کامل، روان و قابل ارائه در فرمت ${formatLabel} تبدیل کن.
${topicBlockFa}

قوانین:
1) هیچ خلاصه‌سازی انجام نده و کل محتوا را نگه دار.
2) غلط‌های تایپی و واژه‌های شکسته را با توجه به بافت اصلاح کن.
3) معنا و ترتیب کلی متن حفظ شود.
4) نویزها و تکرارهای بی‌معنا حذف شوند.
5) ساختار متن برای فرمت ${formatLabel} تمیز و حرفه‌ای باشد.
6) اگر واژه‌ای مبهم بود، با توجه به متن حدس بزن.

الزامات خروجی:
- فقط خروجی نهایی در فرمت ${formatLabel} را بده.
- توضیح اضافه نده.

متن خام:
<<<RAW_TRANSCRIPTION_TEXT>>>`;
}

function updatePromptTemplate() {
  const format = String(els.promptFormatSelect?.value || "markdown");
  const promptLang = String(els.promptLanguageSelect?.value || state.uiLang || "fa").toLowerCase() === "en" ? "en" : "fa";
  const topic = els.promptTopicInput?.value || "";
  if (els.preparedPromptText) {
    els.preparedPromptText.value = buildPreparedPrompt(format, promptLang, topic);
  }
}

async function apiFetch(path, { method = "GET", body, timeoutMs = 15000 } = {}) {
  const headers = {};
  let payload = body;

  if (body && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: payload,
      signal: controller.signal,
    });
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
      if (onUploadProgress) onUploadProgress(percent);
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

function appendIf(form, key, value) {
  if (value === null || value === undefined) return;
  const v = `${value}`;
  if (!v.trim()) return;
  form.append(key, v);
}

function stopPolling() {
  if (state.pollHandle) {
    clearInterval(state.pollHandle);
    state.pollHandle = null;
  }
}

function startPolling(jobId) {
  stopPolling();

  state.pollHandle = setInterval(async () => {
    try {
      const job = await apiFetch(`/transcribe/jobs/${jobId}`);
      setProgress(Number(job.progress_percent || 0), job.stage || "-", job.job_id);

      const partialText = String(job?.result?.text || "");
      if (partialText && partialText.length >= state.stream.target.length) {
        setStreamTarget(partialText, { immediate: false });
      }

      if (job.status === "completed") {
        stopPolling();
        if (job.result && typeof job.result === "object") {
          state.stream.charsPerSec = Math.min(320, Math.max(state.stream.charsPerSec, 120));
          setStreamTarget(String(job.result.text || ""), { immediate: false });
          state.latestResult = job.result;
        }
        setStatusByKey("status_success", "ok");
        toastByKey("status_success", "success");
        return;
      }

      if (job.status === "failed" || job.status === "cancelled") {
        stopPolling();
        const err = job.error || job.status;
        resetStream();
        if (els.transcribeResult) {
          els.transcribeResult.textContent = `${t("error_prefix")}: ${err}`;
        }
        setStatusByKey("status_failed", "bad");
        toastByKey("status_failed", "error");
        return;
      }

      if (job.status === "pending") {
        setStatusByKey("status_queued", "warn");
      } else if (job.status === "running") {
        setStatusByKey("status_running", "warn");
      }
    } catch (err) {
      stopPolling();
      setStatusByKey("status_poll_error", "bad", { msg: err.message });
      toastByKey("status_poll_error", "error", { msg: err.message }, 4200);
    }
  }, 1200);
}

async function transcribeHandler(event) {
  event.preventDefault();
  const file = els.fileInput.files && els.fileInput.files[0];
  if (!file) {
    setStatusByKey("status_file_missing", "bad");
    toastByKey("status_file_missing", "error");
    return;
  }

  resetStream();
  state.latestText = "";
  state.latestResult = null;
  if (els.transcribeResult) {
    els.transcribeResult.textContent = t("result_loading");
  }
  setProgress(0, "uploading", "-");
  setStatusByKey("status_uploading", "warn");

  const form = new FormData();
  form.append("file", file);

  const profile = buildTranscribeProfile();
  Object.entries(profile).forEach(([key, value]) => {
    if (typeof value === "boolean") {
      form.append(key, String(value));
      return;
    }
    appendIf(form, key, value);
  });

  const language = (els.languageSelect?.value || "").trim();
  if (language) {
    form.append("language", language);
  }
  localStorage.setItem(TRANSCRIBE_LANG_KEY, language);

  appendIf(form, "vocabulary_bias", els.vocabularyBiasInput.value || "");

  try {
    const job = await createTranscribeJobWithProgress(form, (uploadPercent) => {
      setProgress(uploadPercent, "uploading", "-");
      setStatusByKey("status_uploading_pct", "warn", { percent: uploadPercent.toFixed(1) });
    });

    state.currentJobId = job.job_id;
    setProgress(Number(job.progress_percent || 0), job.stage || "queued", job.job_id);
    setStatusByKey("status_job_started", "warn");
    startPolling(job.job_id);
  } catch (err) {
    resetStream();
    if (els.transcribeResult) {
      els.transcribeResult.textContent = `${t("error_prefix")}: ${err.message}`;
    }
    setStatusByKey("status_failed_start", "bad");
    toastByKey("status_failed_start", "error");
    setProgress(0, "failed", "-");
  }
}

function copyTextHandler() {
  const text = state.latestText || "";
  if (!text.trim()) {
    setStatusByKey("status_copy_empty", "warn");
    toastByKey("status_copy_empty", "info");
    return;
  }

  navigator.clipboard.writeText(text).then(
    () => {
      setStatusByKey("status_copy_ok", "ok");
      toastByKey("status_copy_ok", "success");
    },
    () => {
      setStatusByKey("status_copy_fail", "bad");
      toastByKey("status_copy_fail", "error");
    }
  );
}

function downloadResultHandler() {
  const text = (state.latestText || "").trim();
  if (!text) {
    setStatusByKey("status_download_empty", "warn");
    toastByKey("status_download_empty", "info");
    return;
  }

  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");

  const link = document.createElement("a");
  link.href = url;
  link.download = `transcription-${stamp}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
  setStatusByKey("status_download_ok", "ok");
  toastByKey("status_download_ok", "success");
}

function copyPromptHandler() {
  const prompt = String(els.preparedPromptText?.value || "");
  if (!prompt.trim()) return;

  navigator.clipboard.writeText(prompt).then(
    () => {
      toastByKey("status_prompt_copied", "success");
    },
    () => {
      toastByKey("status_prompt_copy_failed", "error");
    }
  );
}

async function loadHealth() {
  const health = await apiFetch("/health");
  if (els.modalHealthStatus) {
    els.modalHealthStatus.textContent = String(health.status || "").toLowerCase() === "ok" ? t("health_ok") : health.status || "-";
  }
  if (els.modalFfmpegStatus) {
    els.modalFfmpegStatus.textContent = health.ffmpeg_available ? t("health_ok") : t("health_missing");
  }
  if (els.modalFfprobeStatus) {
    els.modalFfprobeStatus.textContent = health.ffprobe_available ? t("health_ok") : t("health_missing");
  }
  if (els.modalDefaultProvider) {
    els.modalDefaultProvider.textContent = health.default_provider || "-";
  }
}

function initUiLanguage() {
  const saved = localStorage.getItem(UI_LANG_KEY);
  applyUiLanguage(saved || "fa");
}

function bindModalClosing(backdropEl, closeBtnEl) {
  closeBtnEl?.addEventListener("click", () => closeModal(backdropEl));
  backdropEl?.addEventListener("click", (event) => {
    if (event.target === backdropEl) closeModal(backdropEl);
  });
}

function attachEvents() {
  els.uiLangToggle?.addEventListener("click", toggleUiLanguage);
  els.themeToggle?.addEventListener("click", toggleTheme);

  els.settingsBtn?.addEventListener("click", () => openSettingsModal("settings"));

  els.modalTabSettings?.addEventListener("click", () => setSettingsMode("settings"));
  els.modalTabAbout?.addEventListener("click", () => setSettingsMode("about"));
  els.btnSaveRuntimeSettings?.addEventListener("click", saveRuntimeSettingsFromInputs);

  els.transcribeForm?.addEventListener("submit", transcribeHandler);
  els.btnCopyText?.addEventListener("click", copyTextHandler);
  els.btnDownloadResult?.addEventListener("click", downloadResultHandler);

  els.btnOpenPromptModal?.addEventListener("click", () => {
    updatePromptTemplate();
    openModal(els.promptModal);
  });
  els.promptFormatSelect?.addEventListener("change", updatePromptTemplate);
  els.promptLanguageSelect?.addEventListener("change", updatePromptTemplate);
  els.promptTopicInput?.addEventListener("input", updatePromptTemplate);
  els.btnCopyPrompt?.addEventListener("click", copyPromptHandler);

  bindModalClosing(els.settingsModal, els.settingsModalClose);
  bindModalClosing(els.promptModal, els.promptModalClose);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllModals();
    }
  });
}

async function init() {
  loadRuntimeSettings();
  initTheme();
  initUiLanguage();
  if (els.promptLanguageSelect) {
    els.promptLanguageSelect.value = state.uiLang === "en" ? "en" : "fa";
  }
  renderRuntimeSettings();
  updatePromptTemplate();
  attachEvents();

  setProgress(0, "queued", "-");
  await loadHealth();
  setStatusByKey("status_ready", "ok");
}

init().catch((err) => {
  setStatusRaw(t("status_load_error", { msg: err.message }), "bad");
  showToast(t("status_load_error", { msg: err.message }), "error", 4200);
});
