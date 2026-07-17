import pytest


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    """Keep uploads in tests out of the real ./media — FileField saves are otherwise
    written to the working tree and left behind (b1_16OqGlv.pdf and friends)."""
    settings.MEDIA_ROOT = tmp_path
