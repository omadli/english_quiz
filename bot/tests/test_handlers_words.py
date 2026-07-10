from unittest.mock import AsyncMock, MagicMock, patch

from bot import strings
from bot.handlers import words


def test_format_words_lists_en_uz_pos():
    unit = MagicMock()
    unit.book.title = "Book 1"
    unit.number = 3
    w = MagicMock(en="afraid", uz="qo'rqqan, cho'chigan", part_of_speech="adj.")
    text = words.format_words(unit, [w])
    assert "afraid" in text
    assert "qo'rqqan, cho'chigan" in text
    assert "adj." in text
    assert "Book 1" in text
    assert "Unit 3" in text


@patch("bot.handlers.words._active_books")
async def test_menu_words_lists_books(mock_books):
    b = MagicMock(pk=1, title="Book 1")
    mock_books.return_value = [b]
    message = AsyncMock()
    await words.menu_words(message)
    message.answer.assert_awaited()
    assert message.answer.call_args.kwargs.get("reply_markup") is not None


@patch("bot.handlers.words._active_books", return_value=[])
async def test_menu_words_no_books(mock_books):
    message = AsyncMock()
    await words.menu_words(message)
    assert strings.NO_BOOKS in message.answer.call_args.args


@patch("bot.handlers.words._unit_with_words")
async def test_wl_unit_shows_word_list(mock_uw):
    unit = MagicMock(number=1, book_id=1)
    unit.book.title = "Book 1"
    w = MagicMock(en="afraid", uz="qo'rqqan", part_of_speech="adj.")
    mock_uw.return_value = (unit, [w])
    callback = AsyncMock()
    callback.data = "wl:unit:5"
    await words.wl_unit(callback)
    callback.message.edit_text.assert_awaited()
    assert "afraid" in callback.message.edit_text.call_args.args[0]


@patch("bot.handlers.words._unit_with_words", return_value=None)
async def test_wl_unit_missing_unit_noops(mock_uw):
    callback = AsyncMock()
    callback.data = "wl:unit:999"
    await words.wl_unit(callback)
    callback.message.edit_text.assert_not_awaited()


def test_detail_block_rich_formatting_and_strips_example_tags():
    w = MagicMock(en="afraid", uz="qo'rqqan", part_of_speech="adj.",
                  pronunciation="[əˈfreid]", definition="feel fear",
                  example="was <strong>afraid</strong>")
    block = words._detail_block(1, w)
    assert "<b>afraid</b>" in block
    assert "<code>[əˈfreid]</code>" in block
    assert "<blockquote>feel fear</blockquote>" in block
    assert "<strong>" not in block  # example HTML stripped


def test_pack_splits_over_limit():
    msgs = words._pack("H", ["a" * 2000, "b" * 2000, "c" * 2000], limit=3900)
    assert len(msgs) >= 2
    assert all(len(m) <= 3900 for m in msgs)


@patch("bot.handlers.words._unit_with_words")
async def test_wl_detail_sends_messages(mock_uw):
    unit = MagicMock(number=1, book_id=1)
    unit.book.title = "Book 1"
    w = MagicMock(en="afraid", uz="qo'rqqan", part_of_speech="adj.",
                  pronunciation="", definition="d", example="")
    mock_uw.return_value = (unit, [w])
    callback = AsyncMock()
    callback.data = "wl:detail:5"
    await words.wl_detail(callback)
    callback.message.answer.assert_awaited()
    assert "afraid" in callback.message.answer.call_args.args[0]


@patch("bot.handlers.words._synth_unit_mp3")
@patch("bot.handlers.words._unit_audio_file_id", return_value="CACHED_FILE_ID")
async def test_wl_audio_uses_cached_file_id(mock_fid, mock_synth):
    """A cached Telegram file_id is re-sent directly — no gTTS synthesis."""
    callback = AsyncMock()
    callback.data = "wl:audio:5"
    await words.wl_audio(callback)
    callback.message.answer_audio.assert_awaited_once_with("CACHED_FILE_ID")
    mock_synth.assert_not_called()


@patch("bot.handlers.words._cache_unit_audio")
@patch("bot.handlers.words._synth_unit_mp3", return_value=b"ID3mp3bytes")
@patch("bot.handlers.words._unit_with_words")
@patch("bot.handlers.words._unit_audio_file_id", return_value="")
async def test_wl_audio_synthesizes_and_caches(mock_fid, mock_uw, mock_synth, mock_cache):
    """No cache → synthesize, send the MP3, then cache the returned file_id."""
    unit = MagicMock(number=3)
    unit.book.title = "Book 1"
    mock_uw.return_value = (unit, [MagicMock(en="afraid"), MagicMock(en="angry")])
    sent = MagicMock()
    sent.audio.file_id = "NEW_FILE_ID"
    callback = AsyncMock()
    callback.data = "wl:audio:5"
    callback.message.answer_audio.return_value = sent

    await words.wl_audio(callback)

    mock_synth.assert_called_once()
    callback.message.answer_audio.assert_awaited()
    mock_cache.assert_called_once_with(5, "NEW_FILE_ID")


@patch("bot.handlers.words._synth_unit_mp3", side_effect=RuntimeError("gTTS down"))
@patch("bot.handlers.words._unit_with_words")
@patch("bot.handlers.words._unit_audio_file_id", return_value="")
async def test_wl_audio_synthesis_failure_is_graceful(mock_fid, mock_uw, mock_synth):
    """A gTTS failure tells the user instead of crashing the handler."""
    unit = MagicMock(number=3)
    unit.book.title = "Book 1"
    mock_uw.return_value = (unit, [MagicMock(en="afraid")])
    callback = AsyncMock()
    callback.data = "wl:audio:5"
    await words.wl_audio(callback)
    assert strings.AUDIO_FAILED in callback.message.answer.call_args.args
