from bot.keyboards.onboarding import (
    intro_keyboard,
    weekdays_keyboard,
    words_keyboard,
)


def _all_buttons(markup):
    return [btn for row in markup.inline_keyboard for btn in row]


def test_intro_keyboard_has_start_and_defaults():
    cbs = {b.callback_data for b in _all_buttons(intro_keyboard())}
    assert "onb:start" in cbs
    assert "onb:defaults" in cbs


def test_words_keyboard_offers_presets():
    cbs = {b.callback_data for b in _all_buttons(words_keyboard())}
    assert "onb:words:10" in cbs
    assert "onb:words:20" in cbs


def test_weekdays_keyboard_marks_selected():
    markup = weekdays_keyboard([0, 2])
    texts = [b.text for b in _all_buttons(markup)]
    # selected days are prefixed with a check
    assert any(t.startswith("✅") and "Du" in t for t in texts)
    assert any("Se" in t and not t.startswith("✅") for t in texts)
    cbs = {b.callback_data for b in _all_buttons(markup)}
    assert "onb:wd:done" in cbs
    assert "onb:wd:all" in cbs
