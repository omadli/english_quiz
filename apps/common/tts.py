from __future__ import annotations

import asyncio
from importlib import import_module
from io import BytesIO

from django.conf import settings
from gtts import gTTS

# Curated voice catalogs (edge-tts). Uzbek has exactly these two neural voices.
EN_VOICES: list[tuple[str, str]] = [
    ("en-US-AriaNeural", "Aria (ayol)"),
    ("en-US-JennyNeural", "Jenny (ayol)"),
    ("en-US-GuyNeural", "Guy (erkak)"),
    ("en-US-ChristopherNeural", "Christopher (erkak)"),
    ("en-GB-SoniaNeural", "Sonia (UK, ayol)"),
    ("en-GB-RyanNeural", "Ryan (UK, erkak)"),
]
UZ_VOICES: list[tuple[str, str]] = [
    ("uz-UZ-MadinaNeural", "Madina (ayol)"),
    ("uz-UZ-SardorNeural", "Sardor (erkak)"),
]
_DEFAULT_VOICE = {"en": "en-US-AriaNeural", "uz": "uz-UZ-MadinaNeural"}
_LABELS = dict(EN_VOICES + UZ_VOICES)


def voice_label(voice_id: str) -> str:
    return _LABELS.get(voice_id, voice_id)


class TTSProvider:
    """Interface for text-to-speech backends returning MP3 bytes."""

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    def __init__(self, tld: str = "co.uk", slow: bool = False) -> None:
        self.tld = tld
        self.slow = slow

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        # gTTS has no voice selection — `voice` is accepted for interface parity, ignored.
        fp = BytesIO()
        gTTS(text, lang=lang, slow=self.slow, tld=self.tld).write_to_fp(fp)
        return fp.getvalue()


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge online neural voices (free, no API key). Voice-aware."""

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        voice = voice or _DEFAULT_VOICE.get(lang, _DEFAULT_VOICE["en"])
        return asyncio.run(self._synth(text, voice))

    async def _synth(self, text: str, voice: str) -> bytes:
        import edge_tts

        buf = bytearray()
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        if not buf:
            raise RuntimeError("edge-tts returned no audio")
        return bytes(buf)


def get_tts_provider() -> TTSProvider:
    path = getattr(settings, "TTS_PROVIDER", "apps.common.tts.GTTSProvider")
    module_path, _, cls_name = path.rpartition(".")
    return getattr(import_module(module_path), cls_name)()
