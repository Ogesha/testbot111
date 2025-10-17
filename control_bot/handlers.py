from html import escape
from typing import TYPE_CHECKING

from aiogram import Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from .keyboards import (
    control_kb,
    MAIN_RESTART_TEXT,
    MAIN_START_TEXT,
    MAIN_STOP_TEXT,
    PARSER_RESTART_TEXT,
    PARSER_START_TEXT,
    PARSER_STOP_TEXT,
    REFRESH_TEXT,
    BROADCAST_TEXT,
    STATUS_TEXT,
)

if TYPE_CHECKING:
    from app.parserbot_runtime import ParserBotManager


class AllowedOnly:
    def __init__(self, allowed_ids: set[int]):
        self.allowed = allowed_ids

    async def __call__(self, handler, event, data):
        user_id = getattr(event.from_user, "id", None)
        if user_id not in self.allowed:
            return
        return await handler(event, data)


class BroadcastState(StatesGroup):
    waiting_text = State()


def init_control_router(manager, parser_manager: "ParserBotManager", allowed_ids: set[int], session_maker, cfg):
    router = Router()
    router.message.outer_middleware(AllowedOnly(allowed_ids))

    async def _format_status(main_status: dict | None = None, include_users: bool = True):
        st_main = main_status or manager.status()
        st_parser = parser_manager.status()

        lines = [
            f"• Основной бот: {'🟢 работает' if st_main['running'] else '🔴 остановлен'}",
        ]
        if st_main.get("uptime_sec"):
            lines.append(f"  └ Аптайм: {st_main['uptime_sec']} сек")

        parser_line = f"• Парсер-бот: {'🟢 запущен' if st_parser.running else '🔴 остановлен'}"
        lines.append(parser_line)
        if st_parser.last_refresh_at:
            totals = ""
            if st_parser.last_totals:
                totals = f" (категорий {st_parser.last_totals[0]}, товаров {st_parser.last_totals[1]})"
            lines.append(
                "  └ Последнее обновление: "
                + st_parser.last_refresh_at.strftime("%d.%m %H:%M")
                + totals
            )

        if include_users:
            async with session_maker() as s:  # type: AsyncSession
                result = await s.execute(select(func.count()).select_from(User))
                user_count = result.scalar_one()
            lines.append(f"• Пользователей в БД: {user_count}")

        return st_main, st_parser, lines

    @router.message(CommandStart())
    async def start(m: Message):
        st, parser_status, lines = await _format_status()
        await m.answer(
            "Контрольный бот готов.\n" + "\n".join(lines),
            reply_markup=control_kb(st["running"], parser_status.running),
        )

    @router.message(F.text.in_((MAIN_START_TEXT, MAIN_STOP_TEXT)))
    async def toggle(m: Message):
        st = manager.status()
        if st["running"]:
            res = await manager.stop()
        else:
            res = await manager.start()
        st2, parser_status, lines = await _format_status()
        await m.answer(
            res + "\n" + "\n".join(lines),
            reply_markup=control_kb(st2["running"], parser_status.running),
        )

    @router.message(F.text == MAIN_RESTART_TEXT)
    async def restart(m: Message):
        res = await manager.restart()
        st, parser_status, lines = await _format_status()
        await m.answer(
            res + "\n" + "\n".join(lines),
            reply_markup=control_kb(st["running"], parser_status.running),
        )

    @router.message(F.text == STATUS_TEXT)
    async def status(m: Message):
        st, parser_status, base_lines = await _format_status()
        lines = ["Статус:", *base_lines]
        await m.answer(
            "\n".join(lines),
            reply_markup=control_kb(st["running"], parser_status.running),
        )

    @router.message(F.text == BROADCAST_TEXT)
    async def ask_broadcast(m: Message, state: FSMContext):
        await m.answer("Введите текст рассылки (отправится всем пользователям):")
        await state.set_state(BroadcastState.waiting_text)

    @router.message(BroadcastState.waiting_text)
    async def do_broadcast(m: Message, state: FSMContext):
        text = (m.text or "").strip()
        await state.clear()

        from aiogram import Bot

        main_bot = Bot(
            cfg.bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )

        sent = failed = 0
        async with session_maker() as s:  # type: AsyncSession
            res = await s.execute(select(User))
            for u in res.scalars().all():
                try:
                    await main_bot.send_message(u.tg_id, text)
                    sent += 1
                except Exception:
                    failed += 1

        await main_bot.session.close()
        st, parser_status, lines = await _format_status()
        await m.answer(
            f"Готово. Отправлено: {sent}, ошибок: {failed}.\n" + "\n".join(lines),
            reply_markup=control_kb(st["running"], parser_status.running),
        )

    @router.message(F.text == REFRESH_TEXT)
    async def manual_refresh(m: Message):
        st_main, st_parser, _ = await _format_status()
        await m.answer(
            "Запускаю обновление каталога, подождите...",
            reply_markup=control_kb(st_main["running"], st_parser.running),
        )

        parser_status = parser_manager.status()
        if not parser_status.running:
            try:
                await parser_manager.start()
            except Exception as e:
                st_main, st_parser, lines = await _format_status()
                await m.answer(
                    f"❌ Не удалось запустить парсер-бот: <code>{escape(str(e))}</code>\n"
                    + "\n".join(lines),
                    reply_markup=control_kb(st_main["running"], st_parser.running),
                )
                return

        try:
            total_cats, total_items = await parser_manager.refresh_now()
        except Exception as e:
            st_main, st_parser, lines = await _format_status()
            await m.answer(
                f"❌ Ошибка обновления: <code>{escape(str(e))}</code>\n" + "\n".join(lines),
                reply_markup=control_kb(st_main["running"], st_parser.running),
            )
        else:
            st_main, st_parser, lines = await _format_status()
            await m.answer(
                "✅ Каталог обновлён вручную: категорий {cats}, товаров {items}.\n".format(
                    cats=total_cats,
                    items=total_items,
                )
                + "\n".join(lines),
                reply_markup=control_kb(st_main["running"], st_parser.running),
            )

    @router.message(F.text.in_((PARSER_START_TEXT, PARSER_STOP_TEXT)))
    async def toggle_parser(m: Message):
        st = parser_manager.status()
        if st.running:
            res = await parser_manager.stop()
        else:
            try:
                res = await parser_manager.start()
            except Exception as e:
                st_main, st_parser, lines = await _format_status()
                await m.answer(
                    f"❌ Не удалось запустить парсер-бот: <code>{escape(str(e))}</code>\n"
                    + "\n".join(lines),
                    reply_markup=control_kb(st_main["running"], st_parser.running),
                )
                return

        st_main, st_parser, lines = await _format_status()
        await m.answer(
            res + "\n" + "\n".join(lines),
            reply_markup=control_kb(st_main["running"], st_parser.running),
        )

    @router.message(F.text == PARSER_RESTART_TEXT)
    async def restart_parser(m: Message):
        try:
            res = await parser_manager.restart()
        except Exception as e:
            st_main, st_parser, lines = await _format_status()
            await m.answer(
                f"❌ Не удалось перезапустить парсер-бот: <code>{escape(str(e))}</code>\n"
                + "\n".join(lines),
                reply_markup=control_kb(st_main["running"], st_parser.running),
            )
            return

        st_main, st_parser, lines = await _format_status()
        await m.answer(
            res + "\n" + "\n".join(lines),
            reply_markup=control_kb(st_main["running"], st_parser.running),
        )

    return router
