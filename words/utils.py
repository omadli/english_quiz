from gtts import gTTS
from io import BytesIO


def speach(word: str, slow: bool = False):
    mp3_fp = BytesIO()
    tts = gTTS(word, lang='en', slow=slow, tld="co.uk")
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return mp3_fp
