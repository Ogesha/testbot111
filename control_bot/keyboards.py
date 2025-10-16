from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def control_kb(is_running: bool) -> ReplyKeyboardMarkup:
    start_stop_text = "⏹ Остановить основной бот" if is_running else "▶️ Запустить основной бот"

    rows = [
        [KeyboardButton(text=start_stop_text)],
        [KeyboardButton(text="🔄 Перезапуск основного бота")],
        [KeyboardButton(text="🧾 Обновить каталог магазина")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="ℹ️ Статус")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
