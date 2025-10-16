from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import User
from app.repositories import get_or_create_user, log_message
from app.dynamic_products import fetch_categories_with_counts, fetch_products_for_category
from .keyboards import (
    consent_kb, main_menu_kb, support_menu_kb, tv_menu_kb, net_menu_kb
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

@router.message(F.text == "🛍 Магазин")
async def shop_entry(m: Message, session: AsyncSession):
    cats = await fetch_categories_with_counts(session)
    if not cats:
        await m.answer("Категории пока не загружены. Попробуйте позже.", reply_markup=main_menu_kb())
        return
    lines = [f"• {slug} — {cnt} шт." for slug, cnt in cats]
    await m.answer("Категории магазина:\n" + "\n".join(lines))
    await m.answer("Чтобы посмотреть товары категории, введите ее слаг, например: products_televizory\n\n"
                   "⚠️ При желании можно вернуть инлайн-кнопки.", reply_markup=main_menu_kb())

@router.message(F.text.regexp(r"^products_[\wа-яё_]+$"))
async def shop_show_category(m: Message, session: AsyncSession):
    slug = m.text.removeprefix("products_")
    items = await fetch_products_for_category(session, slug, limit=20)
    if not items:
        await m.answer("В этой категории пока пусто.", reply_markup=main_menu_kb())
        return
    lines = []
    for it in items:
        line = f"• <b>{it['title']}</b>"
        if it.get("price"):
            line += f" — {it['price']}"
        if it.get("url"):
            line += f"\n{it['url']}"
        lines.append(line)
    await m.answer("Товары:\n\n" + "\n\n".join(lines), disable_web_page_preview=True, reply_markup=main_menu_kb())

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
