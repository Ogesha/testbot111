from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def control_kb(is_running: bool):
    if is_running:
        start_stop_text = "⏹ Остановить основной бот"
    else:
        start_stop_text = "▶️ Запустить основной бот"

    rows = [
        [KeyboardButton(text=start_stop_text)],
        [KeyboardButton(text="🔄 Перезапуск основного бота")],
        [KeyboardButton(text="📡 Пинг основного бота")],    # ← новая кнопка
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="ℹ️ Статус")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def control_kb(is_running: bool):
    if is_running:
        start_stop_text = "⏹ Остановить основной бот"
    else:
        start_stop_text = "▶️ Запустить основной бот"

    rows = [
        [KeyboardButton(text=start_stop_text)],
        [KeyboardButton(text="🔄 Перезапуск основного бота")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="ℹ️ Статус")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
