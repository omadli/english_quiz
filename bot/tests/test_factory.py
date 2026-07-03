def test_build_dispatcher_includes_routers(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    # at least the four feature routers are attached
    assert len(dp.sub_routers) >= 4


def test_build_bot_uses_token(settings):
    settings.BOT_TOKEN = "123456:TESTTOKEN"
    from bot.factory import build_bot

    bot = build_bot()
    assert bot.token == "123456:TESTTOKEN"
