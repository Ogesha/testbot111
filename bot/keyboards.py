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


def shop_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    row: list[InlineKeyboardButton] = []
    for idx, cat in enumerate(categories, start=1):
        title = cat.get("title") or cat.get("slug") or "Категория"
        count = cat.get("count") or 0
        text = f"{title} ({count})"
        row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"shop:cat:{cat['slug']}"
            )
        )
        if idx % 2 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Закрыть", callback_data="shop:close")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_products_kb(cat_slug: str, products: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for prod in products:
        title = prod.get("title") or "Товар"
        text = title if len(title) <= 32 else title[:29] + "…"
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"shop:prod:{cat_slug}:{prod['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ К категориям", callback_data="shop:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
