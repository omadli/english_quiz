from aiogram.fsm.state import State, StatesGroup


class QuizStates(StatesGroup):
    units = State()    # multiselect units
    count = State()    # number of questions
    time = State()     # seconds per question
    types = State()    # multiselect question types (en_uz/uz_en/def_word)
    summary = State()  # review card before starting
