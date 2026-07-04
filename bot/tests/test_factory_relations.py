def test_dispatcher_includes_relations_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    # start, onboarding, settings, common, quiz, group_quiz, relations
    assert len(dp.sub_routers) >= 7
