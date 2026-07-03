from __future__ import annotations

from importlib import import_module
from io import BytesIO

from django.conf import settings
from gtts import gTTS


class TTSProvider:
    """Interface for text-to-speech backends returning MP3 bytes."""

    def synthesize(self, text: str, lang: str = "en") -> bytes:
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    def __init__(self, tld: str = "co.uk", slow: bool = False) -> None:
        self.tld = tld
        self.slow = slow

    def synthesize(self, text: str, lang: str = "en") -> bytes:
        fp = BytesIO()
        tts = gTTS(text, lang=lang, slow=self.slow, tld=self.tld)
        tts.write_to_fp(fp)
        return fp.getvalue()


def get_tts_provider() -> TTSProvider:
    path = getattr(settings, "TTS_PROVIDER", "apps.common.tts.GTTSProvider")
    module_path, _, cls_name = path.rpartition(".")
    module = import_module(module_path)
    return getattr(module, cls_name)()
