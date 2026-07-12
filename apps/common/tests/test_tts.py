from unittest.mock import MagicMock, patch

from apps.common.tts import GTTSProvider, TTSProvider, get_tts_provider


def test_get_tts_provider_returns_configured_instance(settings):
    settings.TTS_PROVIDER = "apps.common.tts.GTTSProvider"
    provider = get_tts_provider()
    assert isinstance(provider, GTTSProvider)
    assert isinstance(provider, TTSProvider)


@patch("apps.common.tts.gTTS")
def test_gtts_provider_synthesizes_bytes(mock_gtts):
    def fake_write(fp):
        fp.write(b"ID3-audio")

    instance = MagicMock()
    instance.write_to_fp.side_effect = fake_write
    mock_gtts.return_value = instance

    data = GTTSProvider().synthesize("hello", lang="en")
    assert data == b"ID3-audio"
    mock_gtts.assert_called_once()


class _FakeCommunicate:
    last_voice = None

    def __init__(self, text, voice):
        _FakeCommunicate.last_voice = voice
        self._text = text

    async def stream(self):
        yield {"type": "audio", "data": b"AB"}
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"CD"}


def test_edge_tts_passes_voice_and_joins_audio():
    from apps.common.tts import EdgeTTSProvider

    with patch("edge_tts.Communicate", _FakeCommunicate):
        out = EdgeTTSProvider().synthesize("hello", lang="en", voice="en-US-GuyNeural")
    assert out == b"ABCD"
    assert _FakeCommunicate.last_voice == "en-US-GuyNeural"


def test_edge_tts_defaults_voice_per_lang():
    from apps.common.tts import EdgeTTSProvider

    with patch("edge_tts.Communicate", _FakeCommunicate):
        EdgeTTSProvider().synthesize("salom", lang="uz")
    assert _FakeCommunicate.last_voice == "uz-UZ-MadinaNeural"


def test_gtts_accepts_and_ignores_voice_kwarg():
    with patch("apps.common.tts.gTTS") as g:
        g.return_value.write_to_fp.side_effect = lambda fp: fp.write(b"X")
        out = GTTSProvider().synthesize("hi", lang="en", voice="ignored")
    assert out == b"X"


def test_voice_label_known_and_unknown():
    from apps.common.tts import voice_label

    assert "Madina" in voice_label("uz-UZ-MadinaNeural")
    assert voice_label("nope") == "nope"
