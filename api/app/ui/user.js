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
  outputEnabled: true,
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
    label_provider: "موتور پردازش",
    label_language: "زبان متن",
    label_vocab: "واژگان کمکی (اختیاری)",
    placeholder_vocab: "نام‌ها، اصطلاحات و واژه‌های حساس",
    label_progress: "پیشرفت",
    panel_output: "نتایج پردازش",
    label_queue: "صف درخواست‌ها",
    queue_empty: "هنوز درخواستی در صف نیست.",
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
    tip_provider_help: "Local روی همین سیستم اجرا می‌شود. OpenAI و Groq فقط وقتی فعال می‌شوند که کلیدشان در تنظیمات معتبر باشد.",
    tip_language_help: "زبان متن خروجی را مشخص می‌کند. حالت خودکار برای فایل‌های چندزبانه مناسب است.",
    tip_vocab_help: "کلمات مهم پروژه را وارد کن تا مدل در تشخیص آن‌ها دقیق‌تر عمل کند.",
    lang_auto: "تشخیص خودکار",
    lang_fa: "فارسی (fa)",
    lang_en: "English (en)",
    status_ready: "آماده پردازش",
    status_file_missing: "فایل انتخاب نشده است.",
    status_uploading: "در حال آپلود فایل...",
    status_uploading_pct: "در حال آپلود فایل... {{percent}}%",
    status_enqueued: "درخواست به صف اضافه شد.",
    status_cancel_requested: "لغو درخواست در حال انجام است...",
    status_removed_from_queue: "درخواست از صف حذف شد.",
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
    provider_local: "Local (مدل داخلی)",
    provider_openai: "OpenAI API",
    provider_groq: "Groq API",
    provider_available: "{{name}} آماده است.",
    provider_unavailable: "{{name}} غیرفعال است: {{reason}}",
    provider_status_loading: "در حال بررسی providerها...",
    provider_status_failed: "بررسی providerها ناموفق بود؛ فقط Local فعال است.",
    local_model_missing_title: "مدل لوکال آماده نیست",
    local_model_missing_message: "مدل {{model}} روی این سیستم پیدا نشد. حجم تقریبی دانلود {{size}} است. اگر می‌خواهی از مدل لوکال استفاده کنی، دانلود را شروع کن؛ در غیر این صورت این مرحله را اسکیپ کن.",
    local_model_size_label: "حجم تقریبی",
    local_model_download: "دانلود مدل",
    local_model_retry: "تلاش دوباره",
    local_model_skip: "فعلا اسکیپ کن",
    local_model_token_label: "توکن Hugging Face (در صورت نیاز)",
    local_model_token_placeholder: "hf_...",
    local_model_token_help: "برای مدل‌های عمومی معمولا لازم نیست. اگر خطای دسترسی یا Rate limit دیدی، از این لینک token بساز:",
    local_model_progress_waiting: "منتظر تصمیم شماست.",
    local_model_progress_running: "در حال دانلود {{done}} از {{total}} فایل، {{bytes}}",
    local_model_download_done: "دانلود مدل کامل شد. درخواست به صف اضافه می‌شود.",
    local_model_download_failed: "دانلود مدل ناموفق بود: {{msg}}",
    local_model_token_needed: "Hugging Face خطای دسترسی/محدودیت داد. token را از لینک زیر بساز، اینجا وارد کن و دوباره تلاش کن.",
    status_local_model_checking: "در حال بررسی مدل لوکال...",
    status_local_model_skipped: "دانلود مدل لوکال اسکیپ شد.",
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
    queue_status_waiting: "منتظر اجرا",
    queue_status_uploading: "آپلود",
    queue_status_pending: "در صف پردازش",
    queue_status_running: "در حال پردازش",
    queue_status_completed: "تکمیل",
    queue_status_failed: "ناموفق",
    queue_status_cancelled: "لغو",
    queue_remove: "حذف از صف",
    queue_retry: "Retry",
    settings_title: "تنظیمات",
    settings_tab: "تنظیمات",
    about_tab: "درباره ما",
    settings_model: "مدل",
    settings_chunk: "چانک (دقیقه)",
    settings_overlap: "اورلپ (دقیقه)",
    settings_output_hint: "نمایش باکس خروجی متن",
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
    label_provider: "Processing engine",
    label_language: "Transcription language",
    label_vocab: "Vocabulary bias (optional)",
    placeholder_vocab: "Names, terms, and sensitive words",
    label_progress: "Progress",
    panel_output: "Processing results",
    label_queue: "Request queue",
    queue_empty: "No requests in queue yet.",
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
    tip_provider_help: "Local runs on this machine. OpenAI and Groq are enabled only when their configured API key validates successfully.",
    tip_language_help: "Sets the output transcription language. Auto is useful for multilingual files.",
    tip_vocab_help: "Add important project words to improve recognition consistency.",
    lang_auto: "Auto detect",
    lang_fa: "Persian (fa)",
    lang_en: "English (en)",
    status_ready: "Ready",
    status_file_missing: "No file selected.",
    status_uploading: "Uploading file...",
    status_uploading_pct: "Uploading file... {{percent}}%",
    status_enqueued: "Request added to queue.",
    status_cancel_requested: "Cancelling request...",
    status_removed_from_queue: "Request removed from queue.",
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
    provider_local: "Local model",
    provider_openai: "OpenAI API",
    provider_groq: "Groq API",
    provider_available: "{{name}} is ready.",
    provider_unavailable: "{{name}} disabled: {{reason}}",
    provider_status_loading: "Checking providers...",
    provider_status_failed: "Provider check failed; only Local is enabled.",
    local_model_missing_title: "Local model is not ready",
    local_model_missing_message: "Model {{model}} was not found on this system. Estimated download size is {{size}}. Start the download to use Local, or skip this step.",
    local_model_size_label: "Estimated size",
    local_model_download: "Download model",
    local_model_retry: "Retry",
    local_model_skip: "Skip for now",
    local_model_token_label: "Hugging Face token (if needed)",
    local_model_token_placeholder: "hf_...",
    local_model_token_help: "Usually not required for public models. If you hit access or rate-limit errors, create a token here:",
    local_model_progress_waiting: "Waiting for your decision.",
    local_model_progress_running: "Downloading {{done}} of {{total}} files, {{bytes}}",
    local_model_download_done: "Model download completed. The request will be queued.",
    local_model_download_failed: "Model download failed: {{msg}}",
    local_model_token_needed: "Hugging Face returned an access/rate-limit error. Create a token from the link below, paste it here, and retry.",
    status_local_model_checking: "Checking local model...",
    status_local_model_skipped: "Local model download skipped.",
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
    queue_status_waiting: "waiting",
    queue_status_uploading: "uploading",
    queue_status_pending: "queued",
    queue_status_running: "processing",
    queue_status_completed: "completed",
    queue_status_failed: "failed",
    queue_status_cancelled: "cancelled",
    queue_remove: "Remove from queue",
    queue_retry: "Retry",
    settings_title: "Settings",
    settings_tab: "Settings",
    about_tab: "About",
    settings_model: "Model",
    settings_chunk: "Chunk (min)",
    settings_overlap: "Overlap (min)",
    settings_output_hint: "Show transcription output panel",
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
const PROVIDER_SELECTION_KEY = "tootak_user_provider";

const els = {
  toastRoot: $("toastRoot"),
  uiLangToggle: $("uiLangToggle"),
  themeToggle: $("themeToggle"),
  themeIcon: $("themeIcon"),
  settingsBtn: $("settingsBtn"),

  transcribeForm: $("transcribeForm"),
  fileInput: $("fileInput"),
  providerSelect: $("providerSelect"),
  providerStatusHint: $("providerStatusHint"),
  languageSelect: $("languageSelect"),
  vocabularyBiasInput: $("vocabularyBiasInput"),
  btnTranscribe: $("btnTranscribe"),
  transcribeStatus: $("transcribeStatus"),
  outputPanel: $("outputPanel"),
  transcribeResult: $("transcribeResult"),
  transcribePercent: $("transcribePercent"),
  transcribeProgressBar: $("transcribeProgressBar"),
  transcribeJobMeta: $("transcribeJobMeta"),
  btnCopyText: $("btnCopyText"),
  btnDownloadResult: $("btnDownloadResult"),
  queueSummary: $("queueSummary"),
  jobQueueList: $("jobQueueList"),

  btnOpenPromptModal: $("btnOpenPromptModal"),
  promptModal: $("promptModal"),
  promptModalClose: $("promptModalClose"),
  promptFormatSelect: $("promptFormatSelect"),
  promptLanguageSelect: $("promptLanguageSelect"),
  promptTopicInput: $("promptTopicInput"),
  preparedPromptText: $("preparedPromptText"),
  btnCopyPrompt: $("btnCopyPrompt"),

  localModelModal: $("localModelModal"),
  localModelModalClose: $("localModelModalClose"),
  localModelModalTitle: $("localModelModalTitle"),
  localModelMessage: $("localModelMessage"),
  localModelName: $("localModelName"),
  localModelSize: $("localModelSize"),
  localModelRepo: $("localModelRepo"),
  localModelTokenInput: $("localModelTokenInput"),
  localModelTokenHelp: $("localModelTokenHelp"),
  localModelProgressPercent: $("localModelProgressPercent"),
  localModelProgressBar: $("localModelProgressBar"),
  localModelProgressMeta: $("localModelProgressMeta"),
  btnLocalModelDownload: $("btnLocalModelDownload"),
  btnLocalModelSkip: $("btnLocalModelSkip"),

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
  settingOutputEnabled: $("settingOutputEnabled"),
  btnSaveRuntimeSettings: $("btnSaveRuntimeSettings"),
  settingsSaveHint: $("settingsSaveHint"),
  providerSettingsList: $("providerSettingsList"),
  providerSettingsHint: $("providerSettingsHint"),

  modalHealthStatus: $("modalHealthStatus"),
  modalFfmpegStatus: $("modalFfmpegStatus"),
  modalFfprobeStatus: $("modalFfprobeStatus"),
  modalDefaultProvider: $("modalDefaultProvider"),
};

const state = {
  latestText: "",
  latestResult: null,
  currentJobId: "-",
  currentProgress: 0,
  currentStage: "queued",
  queueItems: [],
  queueCounter: 0,
  queueRunnerActive: false,
  activeQueueLocalId: null,
  selectedQueueLocalId: null,
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
  providerStatus: null,
  selectedProvider: localStorage.getItem(PROVIDER_SELECTION_KEY) || "local",
  providerSettings: null,
  localModelDownload: {
    status: null,
    jobs: [],
    active: false,
    resolver: null,
  },
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

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  const digits = unitIndex >= 3 ? 2 : 1;
  return `${size.toFixed(digits)} ${units[unitIndex]}`;
}

function formatEstimatedSize(status) {
  const total = Number(status?.estimated_total_mb || status?.estimated_model_bin_mb || 0);
  return total > 0 ? `~${total.toLocaleString()} MB` : "-";
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
  renderProviderSelect();
  updatePromptTemplate();
  renderQueueList();
  syncSelectedOutput({ animate: false });
  renderStatus();
  renderLocalModelModal();
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

function providerLabel(name) {
  const key = `provider_${String(name || "").toLowerCase()}`;
  const translated = t(key);
  return translated === key ? String(name || "-") : translated;
}

function providerByName(name) {
  const providers = state.providerStatus?.providers || [];
  return providers.find((item) => item.name === name) || null;
}

function providerEnabled(name) {
  const item = providerByName(name);
  return Boolean(item && item.enabled_for_user);
}

function currentProviderInfo() {
  return providerByName(state.selectedProvider) || providerByName("local") || null;
}

function updateProviderHint() {
  if (!els.providerStatusHint) return;
  const info = currentProviderInfo();
  if (!info) {
    els.providerStatusHint.textContent = t("provider_status_loading");
    els.providerStatusHint.className = "hint provider-status-hint warn";
    return;
  }

  const name = providerLabel(info.name);
  if (info.enabled_for_user) {
    const model = info.model ? ` (${info.model})` : "";
    els.providerStatusHint.textContent = `${t("provider_available", { name })}${model}`;
    els.providerStatusHint.className = "hint provider-status-hint ok";
    return;
  }

  els.providerStatusHint.textContent = t("provider_unavailable", { name, reason: info.reason || "-" });
  els.providerStatusHint.className = "hint provider-status-hint bad";
}

function renderProviderSelect() {
  if (!els.providerSelect) return;
  const providers = state.providerStatus?.providers || [
    {
      name: "local",
      enabled_for_user: true,
      valid: true,
      model: state.runtimeSettings.model,
      reason: "local backend is available",
    },
  ];

  els.providerSelect.innerHTML = "";
  providers
    .filter((item) => ["local", "openai", "groq"].includes(item.name))
    .forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.name;
      opt.disabled = !item.enabled_for_user;
      const suffix = item.enabled_for_user ? "" : ` - ${item.reason || "disabled"}`;
      opt.textContent = `${providerLabel(item.name)}${suffix}`;
      els.providerSelect.appendChild(opt);
    });

  if (!providerEnabled(state.selectedProvider)) {
    state.selectedProvider = "local";
    localStorage.setItem(PROVIDER_SELECTION_KEY, state.selectedProvider);
  }
  els.providerSelect.value = state.selectedProvider;
  updateProviderHint();
}

async function loadProviderStatus() {
  if (els.providerStatusHint) {
    els.providerStatusHint.textContent = t("provider_status_loading");
    els.providerStatusHint.className = "hint provider-status-hint warn";
  }

  try {
    state.providerStatus = await apiFetch("/providers/status", { timeoutMs: 12000 });
  } catch (err) {
    state.providerStatus = {
      default_provider: "local",
      providers: [
        {
          name: "local",
          configured: true,
          key_present: false,
          valid: true,
          enabled_for_user: true,
          model: state.runtimeSettings.model,
          base_url: null,
          status_code: null,
          reason: "local backend is available",
        },
      ],
    };
    if (els.providerStatusHint) {
      els.providerStatusHint.textContent = t("provider_status_failed");
      els.providerStatusHint.className = "hint provider-status-hint warn";
    }
    showToast(t("provider_status_failed"), "info", 3600);
  }

  renderProviderSelect();
}

function providerChangeHandler() {
  const next = String(els.providerSelect?.value || "local");
  if (!providerEnabled(next)) {
    renderProviderSelect();
    return;
  }
  state.selectedProvider = next;
  localStorage.setItem(PROVIDER_SELECTION_KEY, next);
  updateProviderHint();
}

function normalizeProviderSettingsPayload(payload) {
  const providers = Array.isArray(payload?.providers) ? payload.providers : [];
  const defaults = {
    openai: {
      name: "openai",
      enabled: false,
      base_url: "https://api.openai.com",
      model: "whisper-1",
      transcriptions_path: "/v1/audio/transcriptions",
      timeout_sec: 300,
      api_keys: [],
    },
    groq: {
      name: "groq",
      enabled: false,
      base_url: "https://api.groq.com/openai",
      model: "whisper-large-v3",
      transcriptions_path: "/v1/audio/transcriptions",
      timeout_sec: 300,
      api_keys: [],
    },
  };

  providers.forEach((item) => {
    const name = String(item?.name || "").toLowerCase();
    if (!defaults[name]) return;
    defaults[name] = {
      ...defaults[name],
      ...item,
      name,
      api_keys: Array.isArray(item.api_keys) ? item.api_keys : [],
    };
  });

  return {
    env_path: String(payload?.env_path || ".env"),
    providers: [defaults.openai, defaults.groq],
  };
}

function renderProviderSettings() {
  if (!els.providerSettingsList) return;
  const settings = normalizeProviderSettingsPayload(state.providerSettings);
  state.providerSettings = settings;
  els.providerSettingsList.innerHTML = "";

  settings.providers.forEach((provider) => {
    const card = document.createElement("div");
    card.className = "provider-settings-card";
    card.dataset.provider = provider.name;

    const keys = provider.api_keys.length ? provider.api_keys : [""];
    const keyRows = keys.map((key, idx) => `
      <div class="provider-key-row" data-key-index="${idx}">
        <input class="provider-key-input" type="password" value="${escapeHtml(key)}" placeholder="${provider.name} api key" autocomplete="off" />
        <button class="pill-btn provider-key-test" type="button" data-provider="${provider.name}" data-key-index="${idx}">Test</button>
        <button class="pill-btn provider-key-remove" type="button" data-provider="${provider.name}" data-key-index="${idx}">Remove</button>
        <span class="hint provider-key-status"></span>
      </div>
    `).join("");

    card.innerHTML = `
      <div class="provider-settings-title">
        <strong>${providerLabel(provider.name)}</strong>
        <label class="switch-field">
          <input class="provider-enabled-input" type="checkbox" ${provider.enabled ? "checked" : ""} />
          <span class="hint">Enabled</span>
        </label>
      </div>
      <div class="grid-2 compact provider-config-grid">
        <label class="field">
          <span>Base URL</span>
          <input class="provider-base-url-input" type="text" value="${escapeHtml(provider.base_url || "")}" />
        </label>
        <label class="field">
          <span>Model</span>
          <input class="provider-model-input" type="text" value="${escapeHtml(provider.model || "")}" />
        </label>
      </div>
      <div class="provider-key-list">${keyRows}</div>
      <button class="pill-btn provider-key-add" type="button" data-provider="${provider.name}">Add key</button>
    `;
    els.providerSettingsList.appendChild(card);
  });

  if (els.providerSettingsHint) {
    els.providerSettingsHint.textContent = `Saved in ${settings.env_path}`;
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function loadProviderSettings() {
  try {
    state.providerSettings = await apiFetch("/providers/settings", { timeoutMs: 12000 });
  } catch (err) {
    state.providerSettings = normalizeProviderSettingsPayload(null);
    if (els.providerSettingsHint) {
      els.providerSettingsHint.textContent = `Provider settings load failed: ${err.message || err}`;
    }
  }
  renderProviderSettings();
}

function collectProviderSettingsFromInputs() {
  const providers = [];
  els.providerSettingsList?.querySelectorAll(".provider-settings-card").forEach((card) => {
    const name = String(card.getAttribute("data-provider") || "");
    const keys = Array.from(card.querySelectorAll(".provider-key-input"))
      .map((input) => String(input.value || "").trim())
      .filter(Boolean);
    providers.push({
      name,
      enabled: Boolean(card.querySelector(".provider-enabled-input")?.checked),
      base_url: String(card.querySelector(".provider-base-url-input")?.value || "").trim(),
      model: String(card.querySelector(".provider-model-input")?.value || "").trim(),
      transcriptions_path: "/v1/audio/transcriptions",
      timeout_sec: 300,
      api_keys: keys,
    });
  });
  return { providers };
}

function addProviderKeyRow(providerName) {
  const card = els.providerSettingsList?.querySelector(`.provider-settings-card[data-provider="${providerName}"]`);
  const list = card?.querySelector(".provider-key-list");
  if (!list) return;
  const idx = list.querySelectorAll(".provider-key-row").length;
  const row = document.createElement("div");
  row.className = "provider-key-row";
  row.setAttribute("data-key-index", String(idx));
  row.innerHTML = `
    <input class="provider-key-input" type="password" value="" placeholder="${providerName} api key" autocomplete="off" />
    <button class="pill-btn provider-key-test" type="button" data-provider="${providerName}" data-key-index="${idx}">Test</button>
    <button class="pill-btn provider-key-remove" type="button" data-provider="${providerName}" data-key-index="${idx}">Remove</button>
    <span class="hint provider-key-status"></span>
  `;
  list.appendChild(row);
  row.querySelector(".provider-key-input")?.focus();
}

async function testProviderKey(button) {
  const providerName = String(button.getAttribute("data-provider") || "");
  const row = button.closest(".provider-key-row");
  const card = button.closest(".provider-settings-card");
  const key = String(row?.querySelector(".provider-key-input")?.value || "").trim();
  const statusEl = row?.querySelector(".provider-key-status");
  if (!key) {
    if (statusEl) statusEl.textContent = "Key is empty";
    return;
  }
  if (statusEl) statusEl.textContent = "Testing...";
  button.disabled = true;
  try {
    const out = await apiFetch("/providers/settings/test-key", {
      method: "POST",
      body: {
        provider: providerName,
        api_key: key,
        base_url: String(card?.querySelector(".provider-base-url-input")?.value || "").trim(),
      },
      timeoutMs: 45000,
    });
    if (statusEl) {
      statusEl.textContent = out.valid ? `Valid (${out.reason || "ok"})` : `Invalid: ${out.reason || out.status_code || "-"}`;
      statusEl.className = `hint provider-key-status ${out.valid ? "ok" : "bad"}`;
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = `Failed: ${err.message || err}`;
      statusEl.className = "hint provider-key-status bad";
    }
  } finally {
    button.disabled = false;
  }
}

async function saveProviderSettingsFromInputs() {
  const payload = collectProviderSettingsFromInputs();
  const saved = await apiFetch("/providers/settings", {
    method: "PUT",
    body: payload,
    timeoutMs: 30000,
  });
  state.providerSettings = saved;
  renderProviderSettings();
  await loadProviderStatus();
}

async function saveAllSettingsFromInputs() {
  const runtimeOk = saveRuntimeSettingsFromInputs();
  if (!runtimeOk) return;
  try {
    await saveProviderSettingsFromInputs();
    setStatusByKey("status_settings_saved", "ok");
    toastByKey("status_settings_saved", "success");
  } catch (err) {
    setStatusRaw(`${t("error_prefix")}: ${err.message || err}`, "bad");
    showToast(`${t("error_prefix")}: ${err.message || err}`, "error", 5200);
  }
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

function queueStatusLabel(status) {
  const key = `queue_status_${String(status || "").trim().toLowerCase()}`;
  const translated = t(key);
  return translated === key ? String(status || "-") : translated;
}

function getSelectedQueueItem() {
  if (!state.selectedQueueLocalId) return null;
  return state.queueItems.find((x) => x.localId === state.selectedQueueLocalId) || null;
}

function isInFlightStatus(status) {
  return ["uploading", "pending", "running"].includes(String(status || "").toLowerCase());
}

function renderQueueList() {
  if (!els.jobQueueList) return;

  if (els.queueSummary) {
    const completed = state.queueItems.filter((x) => x.status === "completed").length;
    els.queueSummary.textContent = `${completed}/${state.queueItems.length}`;
  }

  els.jobQueueList.innerHTML = "";
  if (!state.queueItems.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = t("queue_empty");
    els.jobQueueList.appendChild(empty);
    return;
  }

  state.queueItems.forEach((item) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = `queue-item${item.localId === state.selectedQueueLocalId ? " active" : ""}`;
    row.dataset.localId = item.localId;

    const title = document.createElement("span");
    title.className = "queue-item-title";
    title.textContent = item.sourceFilename;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "queue-item-delete";
    removeBtn.setAttribute("aria-label", t("queue_remove"));
    removeBtn.setAttribute("title", t("queue_remove"));
    removeBtn.setAttribute("data-tooltip", t("queue_remove"));
    removeBtn.setAttribute("data-local-id", item.localId);
    removeBtn.textContent = "×";

    const retryBtn = document.createElement("button");
    retryBtn.type = "button";
    retryBtn.className = "queue-item-retry";
    retryBtn.setAttribute("aria-label", t("queue_retry"));
    retryBtn.setAttribute("title", t("queue_retry"));
    retryBtn.setAttribute("data-tooltip", t("queue_retry"));
    retryBtn.setAttribute("data-local-id", item.localId);
    retryBtn.textContent = "R";
    if (item.status !== "failed" || !item.jobId) {
      retryBtn.classList.add("hidden");
    }

    const meta = document.createElement("span");
    meta.className = "queue-item-meta";
    const shortJob = item.jobId ? String(item.jobId).slice(0, 8) : "-";
    const stage = stageLabel(item.stage || "-");
    const provider = providerLabel(item.provider || item.profile?.provider || "local");
    meta.textContent = `${queueStatusLabel(item.status)} · ${provider} · ${Number(item.progressPercent || 0).toFixed(1)}% · ${t("job_label")}: ${shortJob} · ${t("stage_label")}: ${stage}`;

    row.appendChild(title);
    row.appendChild(removeBtn);
    row.appendChild(retryBtn);
    row.appendChild(meta);
    els.jobQueueList.appendChild(row);
  });
}

function syncSelectedOutput({ animate = false } = {}) {
  const item = getSelectedQueueItem();
  if (!item) {
    resetStream();
    state.latestText = "";
    state.latestResult = null;
    setProgress(0, "queued", "-");
    if (els.transcribeResult) {
      els.transcribeResult.textContent = t("result_empty");
    }
    return;
  }

  state.latestText = String(item.latestText || "");
  state.latestResult = item.result || null;
  setProgress(Number(item.progressPercent || 0), item.stage || "queued", item.jobId || "-");

  if (item.status === "failed" || item.status === "cancelled") {
    const savedText = String(item.latestText || "").trim();
    if (els.transcribeResult) {
      if (savedText) {
        setStreamTarget(`${savedText}\n\n---\n${t("error_prefix")}: ${item.error || item.status}`, { immediate: !animate });
      } else {
        resetStream();
        els.transcribeResult.textContent = `${t("error_prefix")}: ${item.error || item.status}`;
      }
    }
    return;
  }

  if (!state.latestText.trim()) {
    resetStream();
    if (els.transcribeResult) {
      const shouldShowPreparing = ["waiting", "uploading", "pending", "running"].includes(item.status);
      els.transcribeResult.textContent = shouldShowPreparing ? t("result_loading") : t("result_empty");
    }
    return;
  }

  setStreamTarget(state.latestText, { immediate: !animate });
}

function setSelectedQueueItem(localId, { animate = false } = {}) {
  state.selectedQueueLocalId = localId || null;
  renderQueueList();
  syncSelectedOutput({ animate });
}

function removeQueueItem(localId) {
  const idx = state.queueItems.findIndex((x) => x.localId === localId);
  if (idx < 0) return;

  const item = state.queueItems[idx];
  const inFlight = isInFlightStatus(item.status);
  item.cancelRequested = true;

  if (typeof item.uploadAbort === "function") {
    try {
      item.uploadAbort();
    } catch {
      // noop
    }
  }

  if (inFlight && item.jobId) {
    apiFetch(`/transcribe/jobs/${item.jobId}/cancel`, { method: "POST", timeoutMs: 10000 }).catch(() => null);
  }

  state.queueItems.splice(idx, 1);

  if (state.selectedQueueLocalId === localId) {
    const replacement = state.queueItems[idx] || state.queueItems[idx - 1] || null;
    setSelectedQueueItem(replacement?.localId || null, { animate: false });
  } else {
    renderQueueList();
  }

  if (!state.queueItems.length) {
    syncSelectedOutput({ animate: false });
  }

  if (inFlight) {
    setStatusByKey("status_cancel_requested", "warn");
    toastByKey("status_cancel_requested", "info");
  } else {
    setStatusByKey("status_removed_from_queue", "ok");
    toastByKey("status_removed_from_queue", "success");
  }
}

async function retryQueueItem(localId) {
  const item = state.queueItems.find((x) => x.localId === localId);
  if (!item || !item.jobId || item.status !== "failed") return;

  item.status = "pending";
  item.stage = "queued";
  item.error = "";
  item.cancelRequested = false;
  item.cancelSignalSent = false;
  renderQueueList();
  setSelectedQueueItem(item.localId, { animate: false });
  setStatusByKey("status_queued", "warn");

  try {
    const job = await apiFetch(`/transcribe/jobs/${item.jobId}/retry`, { method: "POST", timeoutMs: 20000 });
    item.status = String(job.status || "pending").toLowerCase();
    item.stage = job.stage || "queued";
    item.progressPercent = Number(job.progress_percent || item.progressPercent || 0);
    renderQueueList();
    await monitorQueueItem(item);
  } catch (err) {
    item.status = "failed";
    item.stage = "failed";
    item.error = err.message || String(err);
    renderQueueList();
    syncSelectedOutput({ animate: false });
    setStatusByKey("status_failed_start", "bad");
    toastByKey("status_failed_start", "error");
  }
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
    const outputEnabled = typeof parsed.outputEnabled === "boolean"
      ? parsed.outputEnabled
      : typeof parsed.streamEnabled === "boolean"
        ? parsed.streamEnabled
        : DEFAULT_RUNTIME_SETTINGS.outputEnabled;
    state.runtimeSettings = {
      model: String(parsed.model || DEFAULT_RUNTIME_SETTINGS.model),
      chunkMinutes: Number.isFinite(chunkMinutes) && chunkMinutes > 0 ? chunkMinutes : DEFAULT_RUNTIME_SETTINGS.chunkMinutes,
      chunkOverlapMinutes: Number.isFinite(overlapMinutes) && overlapMinutes >= 0 ? overlapMinutes : DEFAULT_RUNTIME_SETTINGS.chunkOverlapMinutes,
      outputEnabled,
    };
  } catch {
    state.runtimeSettings = { ...DEFAULT_RUNTIME_SETTINGS };
  }
}

function renderRuntimeSettings() {
  if (els.settingModel) els.settingModel.value = state.runtimeSettings.model;
  if (els.settingChunkMinutes) els.settingChunkMinutes.value = String(state.runtimeSettings.chunkMinutes);
  if (els.settingOverlapMinutes) els.settingOverlapMinutes.value = String(state.runtimeSettings.chunkOverlapMinutes);
  if (els.settingOutputEnabled) els.settingOutputEnabled.checked = state.runtimeSettings.outputEnabled !== false;
}

function applyOutputVisibility() {
  const outputEnabled = state.runtimeSettings.outputEnabled !== false;
  if (els.outputPanel) {
    els.outputPanel.classList.toggle("output-hidden", !outputEnabled);
  }
}

function saveRuntimeSettingsFromInputs() {
  const model = String(els.settingModel?.value || "").trim() || DEFAULT_RUNTIME_SETTINGS.model;
  const chunkMinutes = Number(els.settingChunkMinutes?.value);
  const overlapMinutes = Number(els.settingOverlapMinutes?.value);
  const outputEnabled = Boolean(els.settingOutputEnabled?.checked);

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
    outputEnabled,
  };

  localStorage.setItem(RUNTIME_SETTINGS_KEY, JSON.stringify(state.runtimeSettings));
  applyOutputVisibility();
  syncSelectedOutput({ animate: true });
  setStatusByKey("status_settings_saved", "ok");
  toastByKey("status_settings_saved", "success");
  return true;
}

function buildTranscribeProfile() {
  const chunkMinutes = Number(state.runtimeSettings.chunkMinutes);
  const overlapMinutes = Number(state.runtimeSettings.chunkOverlapMinutes);
  const provider = providerEnabled(state.selectedProvider) ? state.selectedProvider : "local";
  const providerInfo = providerByName(provider);
  const model = provider === "local"
    ? state.runtimeSettings.model
    : String(providerInfo?.model || "").trim();

  return {
    ...STABLE_PROFILE,
    provider,
    model: model || state.runtimeSettings.model,
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
  loadProviderStatus().catch(() => null);
  loadProviderSettings().catch(() => null);
  openModal(els.settingsModal);
}

function closeAllModals() {
  closeModal(els.settingsModal);
  closeModal(els.promptModal);
  if (state.localModelDownload.status && !state.localModelDownload.active) {
    resolveLocalModelPrompt(false);
  }
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

function createTranscribeJobWithProgress(formData, onUploadProgress, onAbortReady) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/transcribe/jobs", true);
    xhr.timeout = 30 * 60 * 1000;
    if (onAbortReady) {
      onAbortReady(() => xhr.abort());
    }

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
    xhr.onabort = () => reject(new Error("upload cancelled"));
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildFormFromQueueItem(item) {
  const form = new FormData();
  form.append("file", item.file);

  Object.entries(item.profile).forEach(([key, value]) => {
    if (typeof value === "boolean") {
      form.append(key, String(value));
      return;
    }
    appendIf(form, key, value);
  });

  appendIf(form, "language", item.language || "");
  appendIf(form, "vocabulary_bias", item.vocabularyBias || "");
  return form;
}

function isAuthLikeDownloadError(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("401") || text.includes("403") || text.includes("unauthorized") || text.includes("forbidden") || text.includes("rate");
}

function setLocalModelProgress(percent, metaText) {
  const shown = Math.max(0, Math.min(100, Number(percent || 0)));
  if (els.localModelProgressBar) {
    els.localModelProgressBar.style.width = `${shown}%`;
  }
  if (els.localModelProgressPercent) {
    els.localModelProgressPercent.textContent = `${shown.toFixed(1)}%`;
  }
  if (els.localModelProgressMeta && metaText !== undefined) {
    els.localModelProgressMeta.textContent = metaText;
  }
}

function computeLocalModelDownloadProgress(jobs) {
  const rows = Array.isArray(jobs) ? jobs : [];
  if (!rows.length) {
    return { percent: 0, meta: t("local_model_progress_waiting"), completed: 0, total: 0 };
  }

  const completed = rows.filter((job) => String(job.status || "").toLowerCase() === "completed").length;
  const total = rows.length;
  const knownTotal = rows.reduce((sum, job) => sum + Number(job.bytes_total || 0), 0);
  const downloaded = rows.reduce((sum, job) => sum + Number(job.bytes_downloaded || 0), 0);
  const percent = knownTotal > 0 ? (downloaded / knownTotal) * 100 : (completed / total) * 100;
  const bytes = knownTotal > 0 ? `${formatBytes(downloaded)} / ${formatBytes(knownTotal)}` : "-";
  return {
    percent,
    meta: t("local_model_progress_running", { done: completed, total, bytes }),
    completed,
    total,
  };
}

function renderLocalModelModal() {
  const status = state.localModelDownload.status;
  if (!status) return;

  const size = formatEstimatedSize(status);
  if (els.localModelModalTitle) els.localModelModalTitle.textContent = t("local_model_missing_title");
  if (els.localModelMessage && !state.localModelDownload.active) {
    els.localModelMessage.textContent = t("local_model_missing_message", {
      model: status.canonical_model || status.model || "-",
      size,
    });
  }
  if (els.localModelName) els.localModelName.textContent = status.canonical_model || status.model || "-";
  if (els.localModelSize) els.localModelSize.textContent = size;
  if (els.localModelRepo) els.localModelRepo.textContent = status.repo_id || "-";
  if (els.btnLocalModelDownload) {
    els.btnLocalModelDownload.textContent = t(state.localModelDownload.jobs.length ? "local_model_retry" : "local_model_download");
  }
  if (els.localModelProgressMeta && !state.localModelDownload.jobs.length && !state.localModelDownload.active) {
    els.localModelProgressMeta.textContent = t("local_model_progress_waiting");
  }
}

function setLocalModelTokenAttention(enabled) {
  const field = els.localModelTokenInput?.closest(".model-token-field");
  if (field) field.classList.toggle("attention", Boolean(enabled));
}

function resolveLocalModelPrompt(value) {
  const resolver = state.localModelDownload.resolver;
  state.localModelDownload.resolver = null;
  state.localModelDownload.active = false;
  state.localModelDownload.jobs = [];
  state.localModelDownload.status = null;
  closeModal(els.localModelModal);
  setLocalModelTokenAttention(false);
  if (resolver) resolver(Boolean(value));
}

function skipLocalModelDownloadPrompt() {
  if (state.localModelDownload.active) return;
  resolveLocalModelPrompt(false);
}

function openLocalModelPrompt(status) {
  return new Promise((resolve) => {
    state.localModelDownload.status = status;
    state.localModelDownload.jobs = [];
    state.localModelDownload.active = false;
    state.localModelDownload.resolver = resolve;
    setLocalModelTokenAttention(false);
    if (els.localModelTokenInput) els.localModelTokenInput.value = "";
    if (els.btnLocalModelDownload) els.btnLocalModelDownload.disabled = false;
    if (els.btnLocalModelSkip) els.btnLocalModelSkip.disabled = false;
    if (els.localModelModalClose) els.localModelModalClose.disabled = false;
    setLocalModelProgress(0, t("local_model_progress_waiting"));
    renderLocalModelModal();
    openModal(els.localModelModal);
  });
}

async function startLocalModelDownload() {
  const status = state.localModelDownload.status;
  if (!status || state.localModelDownload.active) return;

  state.localModelDownload.active = true;
  state.localModelDownload.jobs = [];
  setLocalModelTokenAttention(false);
  if (els.btnLocalModelDownload) els.btnLocalModelDownload.disabled = true;
  if (els.btnLocalModelSkip) els.btnLocalModelSkip.disabled = true;
  if (els.localModelModalClose) els.localModelModalClose.disabled = true;
  if (els.localModelMessage) {
    els.localModelMessage.textContent = t("local_model_progress_running", { done: 0, total: 0, bytes: "-" });
  }

  try {
    const token = String(els.localModelTokenInput?.value || "").trim();
    const batch = await apiFetch("/models/local/download", {
      method: "POST",
      body: {
        model: status.canonical_model || status.model,
        hf_token: token || undefined,
      },
      timeoutMs: 90000,
    });
    const jobs = Array.isArray(batch.items) ? batch.items : [];
    state.localModelDownload.jobs = jobs;
    if (!jobs.length) {
      setLocalModelProgress(100, t("local_model_download_done"));
      resolveLocalModelPrompt(true);
      return;
    }
    await pollLocalModelDownloadJobs(jobs.map((job) => job.job_id).filter(Boolean));
  } catch (err) {
    failLocalModelDownload(err.message || String(err));
  }
}

function failLocalModelDownload(message) {
  state.localModelDownload.active = false;
  if (els.btnLocalModelDownload) {
    els.btnLocalModelDownload.disabled = false;
    els.btnLocalModelDownload.textContent = t("local_model_retry");
  }
  if (els.btnLocalModelSkip) els.btnLocalModelSkip.disabled = false;
  if (els.localModelModalClose) els.localModelModalClose.disabled = false;

  const authLike = isAuthLikeDownloadError(message);
  setLocalModelTokenAttention(authLike);
  const text = authLike ? t("local_model_token_needed") : t("local_model_download_failed", { msg: message });
  if (els.localModelMessage) els.localModelMessage.textContent = text;
  setLocalModelProgress(0, t("local_model_download_failed", { msg: message }));
}

async function pollLocalModelDownloadJobs(jobIds) {
  const ids = Array.isArray(jobIds) ? jobIds.filter(Boolean) : [];
  if (!ids.length) {
    resolveLocalModelPrompt(true);
    return;
  }

  while (state.localModelDownload.active) {
    const jobs = await Promise.all(
      ids.map((jobId) => apiFetch(`/models/local/downloads/${encodeURIComponent(jobId)}`, { timeoutMs: 15000 }))
    );
    state.localModelDownload.jobs = jobs;
    const progress = computeLocalModelDownloadProgress(jobs);
    setLocalModelProgress(progress.percent, progress.meta);

    const failed = jobs.find((job) => String(job.status || "").toLowerCase() === "failed");
    if (failed) {
      failLocalModelDownload(failed.error || "download failed");
      return;
    }

    if (progress.completed === progress.total) {
      setLocalModelProgress(100, t("local_model_download_done"));
      if (els.localModelMessage) els.localModelMessage.textContent = t("local_model_download_done");
      await sleep(450);
      resolveLocalModelPrompt(true);
      return;
    }

    await sleep(1200);
  }
}

async function ensureLocalModelReady(model) {
  setStatusByKey("status_local_model_checking", "warn");
  let status;
  try {
    status = await apiFetch(`/models/local/status?model=${encodeURIComponent(model || "large-v3")}`, { timeoutMs: 20000 });
  } catch (err) {
    setStatusRaw(`${t("error_prefix")}: ${err.message || err}`, "bad");
    showToast(`${t("error_prefix")}: ${err.message || err}`, "error", 4600);
    return false;
  }

  if (status.present) {
    return true;
  }

  const downloaded = await openLocalModelPrompt(status);
  if (!downloaded) {
    setStatusByKey("status_local_model_skipped", "warn");
    toastByKey("status_local_model_skipped", "info");
    return false;
  }

  return true;
}

async function monitorQueueItem(item) {
  item.pollErrorCount = 0;

  while (true) {
    if (item.cancelRequested && item.jobId && !item.cancelSignalSent) {
      item.cancelSignalSent = true;
      await apiFetch(`/transcribe/jobs/${item.jobId}/cancel`, { method: "POST", timeoutMs: 10000 }).catch(() => null);
    }

    let job;
    try {
      job = await apiFetch(`/transcribe/jobs/${item.jobId}`, { timeoutMs: 45000 });
      item.pollErrorCount = 0;
    } catch (err) {
      item.pollErrorCount = Number(item.pollErrorCount || 0) + 1;
      const msg = err.message || String(err);
      if (msg.startsWith("404:") || msg.startsWith("410:")) {
        item.status = "failed";
        item.stage = "failed";
        item.error = msg;
        renderQueueList();
        syncSelectedOutput({ animate: false });
        setStatusByKey("status_failed", "bad");
        toastByKey("status_failed", "error");
        break;
      }
      setStatusByKey("status_poll_error", "warn", { msg });
      item.error = msg;
      renderQueueList();
      await sleep(Math.min(8000, 1200 + item.pollErrorCount * 700));
      continue;
    }

    item.status = String(job.status || item.status || "").toLowerCase();
    item.stage = job.stage || item.stage || "-";
    item.progressPercent = Number(job.progress_percent || 0);

    if (job.result && typeof job.result === "object") {
      item.result = job.result;
      const partialText = String(job.result.text || "");
      if (partialText && partialText.length >= item.latestText.length) {
        item.latestText = partialText;
      }
    }

    renderQueueList();
    if (state.selectedQueueLocalId === item.localId) {
      syncSelectedOutput({ animate: true });
    }

    if (item.status === "completed") {
      item.progressPercent = 100;
      item.stage = "completed";
      if (item.result && typeof item.result === "object") {
        item.latestText = String(item.result.text || item.latestText || "");
      }
      renderQueueList();
      if (state.selectedQueueLocalId === item.localId) {
        state.stream.charsPerSec = Math.min(320, Math.max(state.stream.charsPerSec, 120));
        syncSelectedOutput({ animate: true });
      }
      if (!item.cancelRequested) {
        setStatusByKey("status_success", "ok");
        toastByKey("status_success", "success");
      }
      break;
    }

    if (item.status === "failed" || item.status === "cancelled") {
      item.error = job.error || item.error || item.status;
      renderQueueList();
      if (state.selectedQueueLocalId === item.localId) {
        syncSelectedOutput({ animate: false });
      }
      if (!item.cancelRequested) {
        setStatusByKey("status_failed", "bad");
        toastByKey("status_failed", "error");
      }
      break;
    }

    if (item.status === "pending") {
      setStatusByKey("status_queued", "warn");
    } else if (item.status === "running") {
      setStatusByKey("status_running", "warn");
    }

    await sleep(1200);
  }
}

async function runQueueItem(item) {
  if (item.cancelRequested) return;

  item.status = "uploading";
  item.stage = "uploading";
  item.progressPercent = 0;
  item.error = "";
  item.latestText = "";
  item.result = null;
  item.cancelSignalSent = false;
  item.uploadAbort = null;

  setSelectedQueueItem(item.localId, { animate: false });
  setStatusByKey("status_uploading", "warn");
  renderQueueList();

  try {
    const form = buildFormFromQueueItem(item);
    const created = await createTranscribeJobWithProgress(
      form,
      null,
      (abortFn) => {
        item.uploadAbort = abortFn;
      }
    );

    item.uploadAbort = null;
    item.jobId = created.job_id;
    item.status = created.status === "running" ? "running" : "pending";
    item.stage = created.stage || "queued";
    item.progressPercent = Number(created.progress_percent || 0);
    renderQueueList();
    if (state.selectedQueueLocalId === item.localId) {
      syncSelectedOutput({ animate: false });
    }
    setStatusByKey("status_job_started", "warn");
    await monitorQueueItem(item);
  } catch (err) {
    if (item.cancelRequested) {
      return;
    }
    item.status = "failed";
    item.stage = "failed";
    item.error = err.message || String(err);
    renderQueueList();
    if (state.selectedQueueLocalId === item.localId) {
      syncSelectedOutput({ animate: false });
    }
    setStatusByKey("status_failed_start", "bad");
    toastByKey("status_failed_start", "error");
  }
}

async function processQueue() {
  if (state.queueRunnerActive) return;
  state.queueRunnerActive = true;

  try {
    while (true) {
      const next = state.queueItems.find((x) => x.status === "waiting");
      if (!next) break;
      state.activeQueueLocalId = next.localId;
      await runQueueItem(next);
      state.activeQueueLocalId = null;
    }
  } finally {
    state.queueRunnerActive = false;
    state.activeQueueLocalId = null;
    if (!state.queueItems.some((x) => ["waiting", "uploading", "pending", "running"].includes(x.status))) {
      setStatusByKey("status_ready", "ok");
    }
    renderQueueList();
  }
}

async function transcribeHandler(event) {
  event.preventDefault();
  const file = els.fileInput.files && els.fileInput.files[0];
  if (!file) {
    setStatusByKey("status_file_missing", "bad");
    toastByKey("status_file_missing", "error");
    return;
  }

  const profile = buildTranscribeProfile();
  const language = (els.languageSelect?.value || "").trim();
  const vocabularyBias = String(els.vocabularyBiasInput?.value || "");
  localStorage.setItem(TRANSCRIBE_LANG_KEY, language);

  if ((profile.provider || "local") === "local") {
    const ready = await ensureLocalModelReady(profile.model);
    if (!ready) return;
  }

  state.queueCounter += 1;
  const item = {
    localId: `q-${Date.now()}-${state.queueCounter}`,
    sourceFilename: file.name || `file-${state.queueCounter}`,
    file,
    profile,
    provider: profile.provider || "local",
    language,
    vocabularyBias,
    status: "waiting",
    stage: "queued",
    progressPercent: 0,
    latestText: "",
    result: null,
    error: "",
    jobId: "",
    cancelRequested: false,
    cancelSignalSent: false,
    uploadAbort: null,
    createdAt: Date.now(),
  };

  state.queueItems.push(item);
  setSelectedQueueItem(item.localId, { animate: false });
  setStatusByKey("status_enqueued", "ok");
  toastByKey("status_enqueued", "success");

  if (els.fileInput) {
    els.fileInput.value = "";
  }

  processQueue().catch((err) => {
    setStatusByKey("status_failed_start", "bad");
    toastByKey("status_failed_start", "error");
    showToast(`${t("error_prefix")}: ${err.message}`, "error", 4200);
  });
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
  const selected = getSelectedQueueItem();
  const baseName = selected?.sourceFilename
    ? String(selected.sourceFilename).replace(/\.[a-z0-9]+$/i, "")
    : "";

  const link = document.createElement("a");
  link.href = url;
  link.download = baseName ? `${baseName}-transcription.txt` : "transcription.txt";
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
  els.providerSelect?.addEventListener("change", providerChangeHandler);

  els.modalTabSettings?.addEventListener("click", () => setSettingsMode("settings"));
  els.modalTabAbout?.addEventListener("click", () => setSettingsMode("about"));
  els.btnSaveRuntimeSettings?.addEventListener("click", () => {
    saveAllSettingsFromInputs().catch((err) => {
      showToast(`${t("error_prefix")}: ${err.message || err}`, "error", 5200);
    });
  });
  els.providerSettingsList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const addBtn = target.closest(".provider-key-add");
    if (addBtn) {
      addProviderKeyRow(String(addBtn.getAttribute("data-provider") || ""));
      return;
    }
    const removeBtn = target.closest(".provider-key-remove");
    if (removeBtn) {
      removeBtn.closest(".provider-key-row")?.remove();
      return;
    }
    const testBtn = target.closest(".provider-key-test");
    if (testBtn) {
      testProviderKey(testBtn).catch((err) => {
        showToast(`${t("error_prefix")}: ${err.message || err}`, "error", 4200);
      });
    }
  });

  els.transcribeForm?.addEventListener("submit", transcribeHandler);
  els.btnCopyText?.addEventListener("click", copyTextHandler);
  els.btnDownloadResult?.addEventListener("click", downloadResultHandler);
  els.jobQueueList?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const deleteBtn = target.closest(".queue-item-delete");
    if (deleteBtn) {
      const localId = deleteBtn.getAttribute("data-local-id");
      if (!localId) return;
      removeQueueItem(localId);
      return;
    }
    const retryBtn = target.closest(".queue-item-retry");
    if (retryBtn) {
      const localId = retryBtn.getAttribute("data-local-id");
      if (!localId) return;
      retryQueueItem(localId).catch((err) => {
        showToast(`${t("error_prefix")}: ${err.message || err}`, "error", 4200);
      });
      return;
    }
    const row = target.closest(".queue-item");
    if (!row) return;
    const localId = row.getAttribute("data-local-id");
    if (!localId) return;
    setSelectedQueueItem(localId, { animate: false });
  });

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
  els.btnLocalModelDownload?.addEventListener("click", () => {
    startLocalModelDownload().catch((err) => failLocalModelDownload(err.message || String(err)));
  });
  els.btnLocalModelSkip?.addEventListener("click", skipLocalModelDownloadPrompt);
  els.localModelModalClose?.addEventListener("click", skipLocalModelDownloadPrompt);
  els.localModelModal?.addEventListener("click", (event) => {
    if (event.target === els.localModelModal) skipLocalModelDownloadPrompt();
  });

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
  renderProviderSelect();
  applyOutputVisibility();
  updatePromptTemplate();
  attachEvents();

  renderQueueList();
  syncSelectedOutput({ animate: false });
  await loadHealth();
  await loadProviderStatus();
  setStatusByKey("status_ready", "ok");
}

init().catch((err) => {
  setStatusRaw(t("status_load_error", { msg: err.message }), "bad");
  showToast(t("status_load_error", { msg: err.message }), "error", 4200);
});
