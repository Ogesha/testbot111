from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import User
from app.repositories import get_or_create_user, log_message
from app.dynamic_products import (
    fetch_categories_with_counts,
    fetch_products_for_category,
    fetch_category_title,
    fetch_product,
    get_catalog_storage_dir,
)
from .keyboards import (
    consent_kb,
    main_menu_kb,
    support_menu_kb,
    tv_menu_kb,
    net_menu_kb,
    shop_categories_kb,
    shop_products_kb,
    product_detail_kb,
)

router = Router()

CONSENT_TEXT = (
    "Продолжая пользоваться данным ботом вы соглашаетесь на акционные рассылки, "
    "оповещения об технических работах."
)

SUPPORT_PHONE = "39-16-16 (городской), +375(29)888-50-50 (МТС)"
WIFI_GUIDE_URL = "https://garant.by/wp-content/uploads/pdf/pamyatka-polzovatelya-04-2022-tp-link-i-snr.pdf"

# ====== Онбординг / старт ======
@router.message(CommandStart())
async def start(m: Message, session: AsyncSession):
    # регистрируем пользователя (без автопринятия)
    await get_or_create_user(session, m.from_user.id, m.from_user.username, m.from_user.full_name)
    # проверим согласие
    res = await session.execute(select(User.accepted_terms).where(User.tg_id == m.from_user.id))
    accepted = res.scalar() or False
    if not accepted:
        await m.answer(CONSENT_TEXT, reply_markup=consent_kb())
        return
    await m.answer("Добро пожаловать! Выберите раздел:", reply_markup=main_menu_kb())

@router.callback_query(F.data == "consent:accept")
async def accept_consent(c: CallbackQuery, session: AsyncSession):
    await session.execute(update(User).where(User.tg_id == c.from_user.id).values(accepted_terms=True))
    await session.commit()
    await c.message.edit_text("Спасибо! Согласие принято ✅")
    await c.message.answer("Добро пожаловать! Выберите раздел:", reply_markup=main_menu_kb())
    await c.answer()

# ====== Главное меню / навигация ======
@router.message(F.text == "⬅️ В главное меню")
async def go_home(m: Message):
    await m.answer("Главное меню:", reply_markup=main_menu_kb())

@router.message(F.text == "🛠 Техническая помощь")
async def support_root(m: Message):
    await m.answer("Выберите направление:", reply_markup=support_menu_kb())

async def _send_categories(message: Message | CallbackQuery, session: AsyncSession):
    cats = await fetch_categories_with_counts(session)
    if not cats:
        text = "Категории пока не загружены. Попробуйте позже."
        if isinstance(message, CallbackQuery):
            await message.message.edit_text(text)
            await message.answer()
        else:
            await message.answer(text, reply_markup=main_menu_kb())
        return False

    keyboard = shop_categories_kb(cats)
    text = "Выберите категорию магазина:"
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
        await message.answer()
    else:
        await message.answer(text, reply_markup=keyboard)
    return True


@router.message(F.text == "🛍 Магазин")
async def shop_entry(m: Message, session: AsyncSession):
    await _send_categories(m, session)


@router.callback_query(F.data == "shop:cats")
async def shop_categories_callback(c: CallbackQuery, session: AsyncSession):
    await _send_categories(c, session)


@router.callback_query(F.data == "shop:menu")
async def shop_menu_callback(c: CallbackQuery):
    await c.message.delete()
    await c.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await c.answer()


@router.callback_query(F.data.startswith("shop:cat:"))
async def shop_show_category(c: CallbackQuery, session: AsyncSession):
    slug = c.data.split(":", 2)[2]
    title = await fetch_category_title(session, slug)
    if not title:
        await c.answer("Категория не найдена", show_alert=True)
        return

    items = await fetch_products_for_category(session, slug, limit=20)
    if not items:
        await c.message.edit_text(
            f"Категория «{title}» пока пуста.",
            reply_markup=shop_products_kb(slug, []),
        )
        await c.answer()
        return

    keyboard = shop_products_kb(slug, items)
    await c.message.edit_text(
        f"Категория «{title}». Выберите товар:",
        reply_markup=keyboard,
    )
    await c.answer()


@router.callback_query(F.data.startswith("shop:prod:"))
async def shop_show_product(c: CallbackQuery, session: AsyncSession):
    try:
        _, _, slug, prod_id = c.data.split(":", 3)
        product_id = int(prod_id)
    except ValueError:
        await c.answer("Некорректный запрос", show_alert=True)
        return

    product = await fetch_product(session, slug, product_id)
    if not product:
        await c.answer("Товар не найден", show_alert=True)
        return

    text_parts = [f"<b>{product['title']}</b>"]
    if product.get("price"):
        text_parts.append(f"Цена: {product['price']}")
    if product.get("url"):
        text_parts.append(product["url"])
    caption = "\n".join(text_parts)
    keyboard = product_detail_kb(slug, product)

    storage_dir = get_catalog_storage_dir()
    image_path = product.get("image_path")
    photo_input = None
    if image_path:
        local_file = storage_dir / image_path
        if local_file.is_file():
            photo_input = FSInputFile(local_file)

    if photo_input:
        await c.message.answer_photo(photo_input, caption=caption, reply_markup=keyboard)
    elif product.get("image_url"):
        await c.message.answer_photo(
            product["image_url"],
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        await c.message.answer(caption, reply_markup=keyboard)

    await c.answer()

# ====== Техподдержка: телевидение ======
@router.message(F.text == "📺 Проблемы с телевидением")
async def tv_root(m: Message):
    await m.answer("Выберите проблему с телевидением:", reply_markup=tv_menu_kb())

@router.message(F.text == "🚫 Не показывают каналы")
async def tv_no_channels(m: Message, session: AsyncSession):
    txt = (
        "Проверьте, работают ли у вас остальные каналы или только определённые.\n"
        "Запустите автопоиск каналов.\n"
        f"Если автопоиск не помог — обратитесь в техническую поддержку: {SUPPORT_PHONE}"
    )
    await log_message(session, m.from_user.id, m.from_user.username, "ТВ: не показывают каналы")
    await m.answer(txt, reply_markup=main_menu_kb())

@router.message(F.text == "🟡 Плохое качество передачи")
async def tv_bad_quality(m: Message, session: AsyncSession):
    txt = (
        "Проверьте целостность кабеля и фиксацию в разъёме.\n"
        f"Если не помогло — обратитесь в техническую поддержку: {SUPPORT_PHONE}"
    )
    await log_message(session, m.from_user.id, m.from_user.username, "ТВ: плохое качество")
    await m.answer(txt, reply_markup=main_menu_kb())

# ====== Техподдержка: интернет ======
@router.message(F.text == "🌐 Проблемы с интернетом")
async def net_root(m: Message):
    await m.answer("Выберите проблему с интернетом:", reply_markup=net_menu_kb())

@router.message(F.text == "📶 Нет интернета, Wi-Fi есть")
async def net_no_internet_wifi_exists(m: Message, session: AsyncSession):
    txt = (
        "Достаньте роутер из розетки, подождите 1 минуту и подключите обратно.\n"
        f"Если проблема осталась — обратитесь в техническую поддержку: {SUPPORT_PHONE}"
    )
    await log_message(session, m.from_user.id, m.from_user.username, "ИНТЕРНЕТ: нет интернета, Wi-Fi есть")
    await m.answer(txt, reply_markup=main_menu_kb())

@router.message(F.text == "📴 Нет интернета и Wi-Fi-сети")
async def net_no_internet_no_wifi(m: Message, session: AsyncSession):
    txt = (
        "Переверните роутер и найдите на наклейке надпись SSID.\n"
        "Проверьте её наличие у вас на устройстве. Если сеть видна — необходимо настроить роутер.\n\n"
        f"Руководство по настройке: {WIFI_GUIDE_URL}\n\n"
        f"Если возникнут проблемы — обратитесь в техническую поддержку: {SUPPORT_PHONE}"
    )
    await log_message(session, m.from_user.id, m.from_user.username, "ИНТЕРНЕТ: нет интернета и Wi-Fi")
    await m.answer(txt, disable_web_page_preview=False, reply_markup=main_menu_kb())

@router.message(F.text == "🐢 Плохая скорость / большая задержка")
async def net_slow(m: Message, session: AsyncSession):
    txt = (
        "Достаньте роутер из розетки, подождите 1 минуту и подключите обратно.\n"
        f"Если проблема осталась — обратитесь в техническую поддержку: {SUPPORT_PHONE}"
    )
    await log_message(session, m.from_user.id, m.from_user.username, "ИНТЕРНЕТ: низкая скорость")
    await m.answer(txt, reply_markup=main_menu_kb())

# ====== Фолбэк: логирование прочих сообщений и возврат в меню ======
@router.message()
async def fallback(m: Message, session: AsyncSession):
    await log_message(session, m.from_user.id, m.from_user.username, m.text or "")
    await m.answer("Выберите раздел:", reply_markup=main_menu_kb())
