from api.app.live_prompt_guard import _build_limited_stt_prompt, _enhance_live_html, _normalize_text_list


def test_live_stt_prompt_is_below_groq_character_limit():
    prompt = _build_limited_stt_prompt(
        base_prompt="base " * 120,
        audio_topic="topic " * 120,
        previous_context="context " * 250,
        context_tokens=160,
    )
    assert len(prompt) <= 840
    assert prompt.strip()


def test_live_ui_enhancer_adds_auto_language_select():
    html = '<label>زبان<input id="language" value="fa" dir="ltr"></label>'
    enhanced = _enhance_live_html(html)
    assert "Auto /" in enhanced
    assert '<select id="language">' in enhanced


def test_live_normalizes_object_lists_for_ui():
    value = [{"text": "alpha"}, {"word": "beta"}, {"span": "gamma"}]
    assert _normalize_text_list(value) == ["alpha", "beta", "gamma"]
