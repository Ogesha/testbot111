from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.catalog_refresh import refresh_catalog
from .keyboards import control_kb

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

def init_control_router(manager, allowed_ids: set[int], session_maker, cfg):
    router = Router()
    router.message.outer_middleware(AllowedOnly(allowed_ids))

    @router.message(CommandStart())
    async def start(m: Message):
        st = manager.status()
        await m.answer(
            f"Контрольный бот готов.\nОсновной бот: {'🟢 работает' if st['running'] else '🔴 остановлен'}"
            + (f"\nАптайм: {st['uptime_sec']} сек" if st['uptime_sec'] else ""),
            reply_markup=control_kb(st["running"])
        )

    @router.message(F.text.in_(("▶️ Запустить основной бот", "⏹ Остановить основной бот")))
    async def toggle(m: Message):
        st = manager.status()
        if st["running"]:
            res = await manager.stop()
        else:
            res = await manager.start()
        st2 = manager.status()
        await m.answer(
            f"{res}\nСостояние: {'🟢 работает' if st2['running'] else '🔴 остановлен'}",
            reply_markup=control_kb(st2["running"])
        )

    @router.message(F.text == "🔄 Перезапуск основного бота")
    async def restart(m: Message):
        res = await manager.restart()
        st = manager.status()
        await m.answer(
            f"{res}\nСостояние: {'🟢 работает' if st['running'] else '🔴 остановлен'}",
            reply_markup=control_kb(st["running"])
        )

    @router.message(F.text == "ℹ️ Статус")
    async def status(m: Message):
        st = manager.status()
        async with session_maker() as s:  # type: AsyncSession
            res = await s.execute(select(User))
            users = len(list(res.scalars().all()))
        lines = [
            "Статус:",
            f"• Основной бот: {'🟢 работает' if st['running'] else '🔴 остановлен'}",
        ]
        if st["uptime_sec"]:
            lines.append(f"• Аптайм: {st['uptime_sec']} сек")
        lines.append(f"• Пользователей в БД: {users}")

        await m.answer(
            "\n".join(lines),
            reply_markup=control_kb(st["running"])
        )

    @router.message(F.text == "📢 Рассылка")
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
        st = manager.status()
        await m.answer(
            f"Готово. Отправлено: {sent}, ошибок: {failed}.",
            reply_markup=control_kb(st["running"])
        )

    @router.message(F.text == "🔁 Обновить каталог")
    async def manual_refresh(m: Message):
        st = manager.status()
        await m.answer("Запускаю обновление каталога, подождите...", reply_markup=control_kb(st["running"]))

        try:
            total_cats, total_items = await refresh_catalog(cfg)
        except Exception as e:
            st = manager.status()
            await m.answer(
                f"❌ Ошибка обновления: <code>{e}</code>",
                reply_markup=control_kb(st["running"]),
            )
        else:
            st = manager.status()
            await m.answer(
                f"✅ Каталог обновлён вручную: категорий {total_cats}, товаров {total_items}.",
                reply_markup=control_kb(st["running"]),
            )

    return router
