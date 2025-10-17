import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from .config import AppConfig
from .catalog_refresh import refresh_catalog
from .notifier import ControlNotifier


logger = logging.getLogger(__name__)


@dataclass
class ParserStatus:
    running: bool
    last_refresh_at: datetime | None
    last_totals: tuple[int, int] | None


class ParserBotManager:
    """Управляет служебным парсер-ботом, который обновляет каталог в БД."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._task: asyncio.Task | None = None
        self._bot: Bot | None = None
        self._dp: Dispatcher | None = None
        self._stop_event: asyncio.Event | None = None
        self._started_event: asyncio.Event | None = None
        self._refresh_task: asyncio.Task | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_at: datetime | None = None
        self._last_totals: tuple[int, int] | None = None
        self._is_running: bool = False

    def status(self) -> ParserStatus:
        return ParserStatus(
            running=bool(self._is_running and self._task and not self._task.done()),
            last_refresh_at=self._last_refresh_at,
            last_totals=self._last_totals,
        )

    async def start(self) -> str:
        if self._task and not self._task.done():
            return "Парсер уже запущен."

        if not self.cfg.parser_bot_token:
            raise RuntimeError(
                "PARSER_BOT_TOKEN не задан в .env — служебный парсер-бот не может быть запущен."
            )

        self._stop_event = asyncio.Event()
        self._started_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_polling(), name="parser-bot-polling")

        try:
            await asyncio.wait_for(self._started_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Парсер-бот не подтвердил запуск за 10 секунд")
        finally:
            self._started_event = None

        if self._task and self._task.done():
            exc = self._task.exception()
            self._task = None
            if exc:
                raise exc

        return "Парсер-бот запущен."

    async def stop(self) -> str:
        if not self._task or self._task.done():
            return "Парсер уже остановлен."

        if self._stop_event and not self._stop_event.is_set():
            self._stop_event.set()

        if self._dp:
            self._dp.stop_polling()

        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        try:
            if self._refresh_task:
                await self._refresh_task
        except asyncio.CancelledError:
            pass
        finally:
            self._refresh_task = None

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._dp = None
            if self._bot:
                try:
                    await self._bot.session.close()
                except Exception:
                    pass
                self._bot = None
            self._stop_event = None
            self._is_running = False

        return "Парсер-бот остановлен."

    async def refresh_now(self) -> tuple[int, int]:
        if not self.status().running:
            raise RuntimeError("Парсер-бот не запущен")
        return await self._execute_refresh()

    async def restart(self) -> str:
        await self.stop()
        return await self.start()

    async def _run_polling(self):
        notifier = ControlNotifier(self.cfg.control_bot_token, self.cfg.control_admin_ids)

        self._bot = Bot(
            self.cfg.parser_bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        self._dp = Dispatcher(storage=MemoryStorage())

        @self._dp.message(CommandStart())
        async def serve_start(message: Message):
            await message.answer(
                "Служебный бот каталога. Он автоматически обновляет товары и не предназначен для пользователей."
            )

        @self._dp.startup()
        async def on_startup():
            self._is_running = True
            if self._started_event and not self._started_event.is_set():
                self._started_event.set()
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            try:
                await notifier.send("🟢 Парсер-бот запущен.")
            except Exception:
                pass

        @self._dp.shutdown()
        async def on_shutdown():
            if self._refresh_task and not self._refresh_task.done():
                self._refresh_task.cancel()
                try:
                    await self._refresh_task
                except asyncio.CancelledError:
                    pass
            self._refresh_task = None
            self._is_running = False
            try:
                await notifier.send("🔴 Парсер-бот остановлен.")
            except Exception:
                pass

        try:
            await self._dp.start_polling(self._bot)
        finally:
            if self._bot:
                try:
                    await self._bot.session.close()
                except Exception:
                    pass

    async def _refresh_loop(self):
        notifier = ControlNotifier(self.cfg.control_bot_token, self.cfg.control_admin_ids)
        first_run = True

        while self._stop_event and not self._stop_event.is_set():
            if not first_run:
                delay = self._seconds_until_next_window()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass
            first_run = False

            try:
                total_cats, total_items = await self._execute_refresh()
            except Exception as e:
                logger.exception("Ошибка обновления каталога парсер-ботом")
                try:
                    await notifier.send(
                        f"❌ Парсер-бот: ошибка обновления: <code>{escape(str(e))}</code>"
                    )
                except Exception:
                    pass
            else:
                try:
                    await notifier.send(
                        f"✅ Парсер-бот обновил каталог: категорий {total_cats}, товаров {total_items}."
                    )
                except Exception:
                    pass

    async def _execute_refresh(self) -> tuple[int, int]:
        async with self._refresh_lock:
            total_cats, total_items = await refresh_catalog(self.cfg)
            tz = ZoneInfo(self.cfg.tz)
            self._last_refresh_at = datetime.now(tz)
            self._last_totals = (total_cats, total_items)
            return total_cats, total_items

    def _seconds_until_next_window(self) -> float:
        tz = ZoneInfo(self.cfg.tz)
        now = datetime.now(tz)
        hh, mm = self._parse_daily_time()
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max((target - now).total_seconds(), 60.0)

    def _parse_daily_time(self) -> tuple[int, int]:
        hh, mm = self.cfg.scrape.daily_time.split(":")
        return int(hh), int(mm)
