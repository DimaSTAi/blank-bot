from aiogram.fsm.state import State, StatesGroup


class Form(StatesGroup):
    choosing_doc = State()
    choosing_subtype = State()
    filling = State()
    confirm = State()
    payment = State()
