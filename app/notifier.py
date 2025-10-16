import asyncio
from typing import Iterable
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties


class ControlNotifier:
    """
    Уведомления в контрольный бот (всем администраторам).
    Используется планировщиком (scheduler) для отчётов об успехе/ошибках парсинга.
    """
    def __init__(self, control_bot_token: str, control_admin_ids: Iterable[int]):
        self._token = control_bot_token
        self._admin_ids = [int(x) for x in control_admin_ids if str(x).isdigit()]

    async def _send_async(self, text: str):
        if not self._token or not self._admin_ids:
            return
        bot = Bot(self._token, default=DefaultBotProperties(parse_mode="HTML"))
        try:
            for uid in self._admin_ids:
                try:
                    await bot.send_message(uid, text)
                except Exception:
                    # проглатываем, чтобы не падать из-за одного пользователя
                    pass
        finally:
            await bot.session.close()

    async def send(self, text: str):
        """Асинхронно отправить сообщение всем администраторам."""
        await self._send_async(text)

    def send_sync(self, text: str):
        """Запланировать отправку (если вызывается из не-async контекста)."""
        asyncio.create_task(self._send_async(text))
