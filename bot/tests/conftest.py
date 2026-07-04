"""Shared pytest fixtures for the bot test suite."""

import pytest


@pytest.fixture(autouse=True)
def _detach_handler_routers():
    """Detach handler routers from their Dispatcher after each test.

    ``bot.handlers.*`` modules define module-level singleton ``router``
    objects, and aiogram only allows a ``Router`` to be attached to a single
    parent for its whole lifetime (see ``Router.parent_router``'s setter,
    which raises once ``_parent_router`` is set). Several tests call
    ``build_dispatcher()``, which attaches these same singletons to a fresh
    ``Dispatcher`` every time; without detaching between tests, the second
    call in the process raises
    "RuntimeError: Router is already attached to <Dispatcher ...>".

    aiogram exposes no public "detach" API, so this resets the private
    ``_parent_router`` link directly; production code (``bot/factory.py``)
    is unaffected since it only ever builds one Dispatcher per process.
    """
    yield
    from bot.handlers import common, group_quiz, onboarding, quiz, settings, start

    for module in (common, group_quiz, onboarding, quiz, settings, start):
        router = module.router
        parent = router.parent_router
        if parent is not None:
            parent.sub_routers.remove(router)
            router._parent_router = None  # noqa: SLF001 - aiogram has no public detach API
