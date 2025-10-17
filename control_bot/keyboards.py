from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


MAIN_START_TEXT = "▶️ Запустить основной бот"
MAIN_STOP_TEXT = "⏹ Остановить основной бот"
MAIN_RESTART_TEXT = "🔄 Перезапуск основного бота"

PARSER_START_TEXT = "▶️ Запустить парсер-бот"
PARSER_STOP_TEXT = "⏹ Остановить парсер-бот"
PARSER_RESTART_TEXT = "🔄 Перезапуск парсер-бота"

REFRESH_TEXT = "🔁 Обновить каталог"
BROADCAST_TEXT = "📢 Рассылка"
STATUS_TEXT = "ℹ️ Статус"


def control_kb(main_running: bool, parser_running: bool) -> ReplyKeyboardMarkup:
    main_toggle_text = MAIN_STOP_TEXT if main_running else MAIN_START_TEXT
    parser_toggle_text = PARSER_STOP_TEXT if parser_running else PARSER_START_TEXT

    rows = [
        [KeyboardButton(text=main_toggle_text), KeyboardButton(text=parser_toggle_text)],
        [KeyboardButton(text=MAIN_RESTART_TEXT), KeyboardButton(text=PARSER_RESTART_TEXT)],
        [KeyboardButton(text=REFRESH_TEXT)],
        [KeyboardButton(text=BROADCAST_TEXT)],
        [KeyboardButton(text=STATUS_TEXT)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
