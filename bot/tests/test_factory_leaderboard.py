def test_dispatcher_includes_leaderboard_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    assert len(dp.sub_routers) >= 8  # + leaderboard
