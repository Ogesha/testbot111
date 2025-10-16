from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Онбординг (согласие)
def consent_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data="consent:accept")]
    ])

# Главное меню
def main_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🛠 Техническая помощь"), KeyboardButton(text="🛍 Магазин")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

# Техническая помощь: первый уровень
def support_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📺 Проблемы с телевидением")],
        [KeyboardButton(text="🌐 Проблемы с интернетом")],
        [KeyboardButton(text="⬅️ В главное меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

# Телевидение — подменю
def tv_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🚫 Не показывают каналы")],
        [KeyboardButton(text="🟡 Плохое качество передачи")],
        [KeyboardButton(text="⬅️ Назад (техподдержка)")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

# Интернет — подменю
def net_menu_kb() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📶 Нет интернета, Wi-Fi есть")],
        [KeyboardButton(text="📴 Нет интернета и Wi-Fi-сети")],
        [KeyboardButton(text="🐢 Плохая скорость / большая задержка")],
        [KeyboardButton(text="⬅️ Назад (техподдержка)")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
