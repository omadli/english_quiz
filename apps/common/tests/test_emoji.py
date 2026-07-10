from apps.common import emoji


def test_custom_emoji_falls_back_when_id_unset():
    # default map is empty → plain fallback, zero risk to message sends
    assert emoji.custom_emoji("nope", "🔥") == "🔥"


def test_custom_emoji_wraps_when_id_present(monkeypatch):
    monkeypatch.setitem(emoji.IDS, "fire", "123456")
    assert emoji.custom_emoji("fire", "🔥") == '<tg-emoji emoji-id="123456">🔥</tg-emoji>'
