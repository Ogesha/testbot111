import asyncio
import time
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text

from .config import AppConfig
from .db import get_engine, get_sessionmaker, Base
from .repositories import admins_bootstrap
from .scheduler import setup_scheduler
from .notifier import ControlNotifier
from bot.handlers import build_main_router

logger = logging.getLogger(__name__)


class MainBotManager:
    """
    Управляет жизненным циклом основного бота: start / stop / restart / status.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._Session = None
        self._task: asyncio.Task | None = None
        self._bot: Bot | None = None
        self._dp: Dispatcher | None = None
        self._scheduler = None
        self._started_at: float | None = None
        self._is_running: bool = False
        self._started_event: asyncio.Event | None = None

    async def ensure_infra(self):
        """
        Создаёт таблицы и выполняет мягкие миграции (BIGINT, accepted_terms).
        """
        engine = get_engine()
        Session = get_sessionmaker()
        self._Session = Session

        MIGRATION_SQL = """
        DO $$
        BEGIN
            -- Добавление accepted_terms
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='accepted_terms'
            ) THEN
                ALTER TABLE users ADD COLUMN accepted_terms BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;

            -- users.tg_id -> BIGINT
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='users' AND column_name='tg_id' AND data_type IN ('integer','int4')
            ) THEN
                ALTER TABLE users ALTER COLUMN tg_id TYPE BIGINT USING tg_id::bigint;
            END IF;

            -- chat_logs.tg_id -> BIGINT
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='chat_logs' AND column_name='tg_id' AND data_type IN ('integer','int4')
            ) THEN
                ALTER TABLE chat_logs ALTER COLUMN tg_id TYPE BIGINT USING tg_id::bigint;
            END IF;
        END $$;
        """

        last_err = None
        for attempt in range(1, 6):
            try:
                # 1. создать таблицы
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

                # 2. выполнить миграции
                async with engine.begin() as conn:
                    await conn.exec_driver_sql(MIGRATION_SQL)

                # 3. инициализировать админов
                async with Session() as s:
                    await admins_bootstrap(s, self.cfg.admin_ids)
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(min(2 * attempt, 10))
        else:
            raise last_err

    async def _run_polling(self):
        """Внутренний запуск aiogram-поллинга."""
        self._bot = Bot(
            self.cfg.bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        self._dp = Dispatcher(storage=MemoryStorage())
        self._dp.include_router(build_main_router())

        # Middleware для сессии БД
        @self._dp.update.outer_middleware()
        async def db_session_middleware(handler, event: Update, data: dict):
            async with self._Session() as s:
                data["session"] = s  # type: AsyncSession
                return await handler(event, data)

        # Удаляем webhook (важно для polling)
        try:
            await self._bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook удалён (drop_pending_updates=True).")
        except Exception as e:
            logger.warning("Не удалось удалить webhook: %s", e)

        # Планировщик
        self._scheduler = setup_scheduler(self.cfg, self._bot)
        self._scheduler.start()
        self._started_at = time.time()
        self._is_running = True
        if self._started_event and not self._started_event.is_set():
            self._started_event.set()

        # Уведомления админам
        notifier = ControlNotifier(self.cfg.control_bot_token, self.cfg.control_admin_ids)
        try:
            await notifier.send("🟢 Основной бот запущен и готов к работе.")
        except Exception:
            pass

        try:
            await self._dp.start_polling(self._bot)
        except Exception as e:
            try:
                await notifier.send(f"❌ Основной бот упал: <code>{e}</code>")
            except Exception:
                pass
            logger.exception("Критическая ошибка основного бота: ")
            raise
        finally:
            self._started_at = None
            self._is_running = False
            if self._started_event and not self._started_event.is_set():
                self._started_event.set()
            try:
                if self._scheduler:
                    self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            if self._bot:
                try:
                    await self._bot.session.close()
                except Exception:
                    pass
            try:
                await notifier.send("🔴 Основной бот остановлен.")
            except Exception:
                pass

    async def start(self) -> str:
        """Запуск основного бота."""
        if self._task and not self._task.done():
            return "Основной бот уже запущен."
        if self._Session is None:
            await self.ensure_infra()
        start_event = asyncio.Event()
        self._started_event = start_event
        self._task = asyncio.create_task(self._run_polling(), name="mainbot-polling")
        try:
            await asyncio.wait_for(start_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("Основной бот не подтвердил запуск за 10 секунд")
        finally:
            self._started_event = None
        if self._task and self._task.done():
            exc = self._task.exception()
            if exc:
                self._task = None
                self._is_running = False
                raise exc
        return "Основной бот запущен."

    async def stop(self) -> str:
        """Остановка основного бота."""
        if not self._task or self._task.done():
            return "Основной бот уже остановлен."
        if self._dp:
            self._dp.stop_polling()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._dp = None
            self._bot = None
            self._scheduler = None
            self._started_at = None
            self._is_running = False
            self._started_event = None
        return "Основной бот остановлен."

    async def restart(self) -> str:
        """Перезапуск основного бота."""
        await self.stop()
        return await self.start()

    def status(self) -> dict:
        """Возвращает текущее состояние бота."""
        running = bool(self._task and not self._task.done())
        if self._is_running:
            running = True
        if not running:
            uptime = None
        else:
            uptime = int(time.time() - self._started_at) if self._started_at else None
        return {"running": running, "uptime_sec": uptime}
