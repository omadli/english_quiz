from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    words = State()
    weekdays = State()
    morning = State()
    exam = State()
    audio = State()
    audio_repeat = State()
    confirm = State()
