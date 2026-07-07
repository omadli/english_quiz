from aiogram.fsm.state import State, StatesGroup


class QuizStates(StatesGroup):
    units = State()  # selecting which units to practice (multiselect)
