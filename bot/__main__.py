import asyncio
import logging
import os

import django

logging.basicConfig(level=logging.INFO)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

log = logging.getLogger("bot")


async def run_polling() -> None:
    from bot.factory import build_bot, build_dispatcher

    bot = build_bot()
    dp = build_dispatcher()
    await bot.delete_webhook()  # drop any stale webhook so getUpdates won't 409
    log.info("Bot started (long polling)")
    await dp.start_polling(bot)


def run_webhook() -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    from bot.config import get_webhook_config
    from bot.factory import build_bot, build_dispatcher

    cfg = get_webhook_config()
    bot = build_bot()
    dp = build_dispatcher()

    async def on_startup(_: web.Application) -> None:
        await bot.set_webhook(cfg["url"], secret_token=cfg["secret"])

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(lambda _: bot.delete_webhook())
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=cfg["secret"]).register(
        app, path=cfg["path"]
    )
    setup_application(app, dp, bot=bot)
    log.info("Bot started (webhook %s -> :%d%s)", cfg["url"], cfg["port"], cfg["path"])
    web.run_app(app, host="0.0.0.0", port=cfg["port"])


def main() -> None:
    from bot.config import get_bot_mode

    if get_bot_mode() == "webhook":
        run_webhook()
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
