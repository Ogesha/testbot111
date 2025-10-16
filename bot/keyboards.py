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


def shop_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cat in categories:
        text = f"{cat['title']} ({cat['count']})"
        row.append(InlineKeyboardButton(text=text, callback_data=f"shop:cat:{cat['slug']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="shop:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_products_kb(slug: str, products: list[dict]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for product in products:
        title = product["title"][:48]
        row.append(InlineKeyboardButton(text=title, callback_data=f"shop:prod:{slug}:{product['id']}"))
        if len(row) == 1:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="shop:cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_detail_kb(slug: str, product: dict) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    if product.get("url"):
        buttons.append([InlineKeyboardButton(text="🌐 Открыть на сайте", url=product["url"])])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад к категории", callback_data=f"shop:cat:{slug}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
