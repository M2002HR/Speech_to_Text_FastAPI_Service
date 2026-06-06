from pathlib import Path


def test_live_panel_has_clear_microphone_errors_and_gpt_oss_default():
    live_html = Path(__file__).resolve().parents[1] / "api" / "app" / "ui" / "live.html"
    text = live_html.read_text(encoding="utf-8")
    assert "NotFoundError" in text
    assert "میکروفون پیدا نشد" in text
    assert "NotAllowedError" in text
    assert "openai/gpt-oss-120b" in text
    assert "m.type==='fatal'" in text
    assert "خطای provider" in text
    assert "startStandaloneChunk" in text
    assert "فایل مستقل" in text
    assert "audioTopic" in text
    assert "موضوع صدا" in text
    assert "whisper-large-v3" in text
    assert "6000" in text


def test_live_backend_has_rolling_context_for_stt_and_llm():
    live_py = Path(__file__).resolve().parents[1] / "api" / "app" / "live.py"
    text = live_py.read_text(encoding="utf-8")
    assert "LIVE_LLM_CONTEXT_TOKENS" in text
    assert "LIVE_STT_CONTEXT_TOKENS" in text
    assert "LIVE_AUDIO_TOPIC" in text
    assert "audio_topic" in text
    assert "_build_stt_prompt" in text
    assert "previous_context_token_budget" in text
    assert "if provider != \"local\"" in text
    assert "_DEFAULT_GROQ_STT_MODEL = \"whisper-large-v3\"" in text
    assert "_FALLBACK_GROQ_STT_MODEL = \"whisper-large-v3-turbo\"" in text
    assert "live_model_fallback" in text
    assert "403_forbidden" in text
