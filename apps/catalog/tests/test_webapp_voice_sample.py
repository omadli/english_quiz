from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db


def test_voice_sample_rejects_unknown_voice(client):
    assert client.get("/webapp/api/voice-sample/?voice=nope&lang=en").status_code == 400
    bad_lang = client.get("/webapp/api/voice-sample/?voice=uz-UZ-MadinaNeural&lang=xx")
    assert bad_lang.status_code == 400


def test_voice_sample_returns_mp3(client):
    with patch("apps.learning.services.audio.voice_sample", return_value=b"MP3DATA"):
        r = client.get("/webapp/api/voice-sample/?voice=uz-UZ-MadinaNeural&lang=uz")
    assert r.status_code == 200
    assert r["Content-Type"] == "audio/mpeg"
    assert r.content == b"MP3DATA"


def test_voice_sample_unavailable(client):
    with patch("apps.learning.services.audio.voice_sample", return_value=None):
        r = client.get("/webapp/api/voice-sample/?voice=en-US-GuyNeural&lang=en")
    assert r.status_code == 503
