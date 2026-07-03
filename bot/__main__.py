import asyncio
import logging
import os

import django

logging.basicConfig(level=logging.INFO)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()


async def main() -> None:
    from bot.factory import build_bot, build_dispatcher

    bot = build_bot()
    dp = build_dispatcher()
    logging.getLogger("bot").info("Bot started (long polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
