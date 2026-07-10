from __future__ import annotations

# Semantic name → Telegram custom (premium) emoji document ID.
#
# Fill these with IDs of existing, well-made custom emojis — no need to create a
# bot-owned sticker set. To get an id: forward a message containing the emoji to
# @idstickerbot, or read the message's `custom_emoji` entity id.
#
# This works when the BOT OWNER has a Telegram Premium subscription; the bot may
# then send any custom emoji directly to private/group/supergroup chats. Non-
# premium viewers (and system notifications / forwards by non-premium users)
# automatically fall back to the plain emoji. Leaving a name unset uses the
# plain fallback — zero risk, identical to today's output.
IDS: dict[str, str] = {
    # "finish": "5368324170671202286",
    # "trophy": "5386560348219989059",
    # "fire": "...",
    # "target": "...",
}


def custom_emoji(name: str, fallback: str) -> str:
    """Wrap `fallback` (must be exactly one emoji) in a ``<tg-emoji>`` for the
    named custom emoji, or return `fallback` unchanged when no id is configured.

    Requires the bot's global ``parse_mode=HTML`` (already set in bot.factory).
    """
    emoji_id = IDS.get(name)
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
