import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from apps.catalog.models import Word

_ROW_H = 40
_PAD = 20
_WIDTH = 720


def render_daily_card(words: list[Word], date: datetime.date) -> bytes:
    """Render a simple table card (English | Uzbek | POS) as PNG bytes."""
    height = _PAD * 2 + _ROW_H * (len(words) + 1)
    img = Image.new("RGB", (_WIDTH, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.text((_PAD, _PAD), f"Bugungi so'zlar — {date:%d.%m.%Y}", fill="black", font=font)
    y = _PAD + _ROW_H
    for i, word in enumerate(words, start=1):
        line = f"{i}. {word.en}  —  {word.uz}   {word.part_of_speech}"
        draw.text((_PAD, y), line, fill="black", font=font)
        y += _ROW_H

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
