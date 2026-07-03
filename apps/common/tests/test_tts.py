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
