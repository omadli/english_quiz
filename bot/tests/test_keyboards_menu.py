from bot import strings
from bot.keyboards.menu import main_menu_keyboard


def _texts(kb):
    return [b.text for row in kb.keyboard for b in row]


def test_menu_without_webapp_has_no_webapp_button():
    kb = main_menu_keyboard(None)
    texts = _texts(kb)
    assert strings.MENU_TEST in texts
    assert strings.MENU_WORDS in texts
    assert strings.MENU_BOOKS in texts
    assert strings.MENU_WEBAPP not in texts
    assert kb.resize_keyboard is True


def test_menu_with_webapp_adds_webapp_button():
    kb = main_menu_keyboard("https://example.com/app")
    webapp = [b for row in kb.keyboard for b in row if b.web_app]
    assert len(webapp) == 1
    assert webapp[0].text == strings.MENU_WEBAPP
    assert webapp[0].web_app.url == "https://example.com/app"


def test_menu_is_one_time_and_not_persistent():
    kb = main_menu_keyboard(None)
    assert kb.one_time_keyboard is True
    assert not kb.is_persistent


def test_menu_drops_group_quiz_and_top():
    texts = _texts(main_menu_keyboard(None))
    assert strings.MENU_GROUP_QUIZ not in texts
    assert strings.MENU_TOP not in texts
    for t in (strings.MENU_TODAY, strings.MENU_EXAM, strings.MENU_TEST,
              strings.MENU_WORDS, strings.MENU_BOOKS, strings.MENU_SETTINGS):
        assert t in texts
