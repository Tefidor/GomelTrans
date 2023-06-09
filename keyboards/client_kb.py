from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_kb():
    kb = [
        [
            KeyboardButton(text="🚎/🚌"),
            KeyboardButton(text="🕐"),
            KeyboardButton(text="🔎🚍"),
            KeyboardButton(text="🗺"),
            KeyboardButton(text="💰"),
            KeyboardButton(text="💬")
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True,
                                   input_field_placeholder="Чего желаете в этот раз?")
    return keyboard


def get_trans_choice_kb():
    kb = [
        [
            KeyboardButton(text="🚎"),
            KeyboardButton(text="🚌"),
            KeyboardButton(text="Отмена")

        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True,
                                   input_field_placeholder="Выберите вид транспорта")
    return keyboard


def get_cancel_kb():
    kb = [
        [
            KeyboardButton(text="Отмена")
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return keyboard


def get_nearest_stop_kb():
    kb = [
        [
            KeyboardButton(text="Мое местоположение", request_location=True),
            KeyboardButton(text="Отмена")
        ]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return keyboard
