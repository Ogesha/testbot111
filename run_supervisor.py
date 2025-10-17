import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage


from app.config import load_config
from app.db import init_engine, get_sessionmaker
from app.mainbot_runtime import MainBotManager
from app.parserbot_runtime import ParserBotManager
from control_bot.handlers import init_control_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    cfg = load_config()

    # Инициализируем движок/Session один раз
    engine, Session = init_engine(cfg.database_url)

    # Менеджер основного бота (создание таблиц/миграции/админы)
    manager = MainBotManager(cfg)
    await manager.ensure_infra()

    parser_manager = ParserBotManager(cfg)
    if cfg.parser_bot_token:
        try:
            await parser_manager.start()
            logger.info("Парсер-бот запущен supervisor'ом")
        except Exception:
            logger.exception("Не удалось запустить парсер-бот при старте supervisor")
    else:
        logger.warning("PARSER_BOT_TOKEN не задан — парсер-бот не будет запущен")

    # После перезапуска supervisor автоматически поднимаем основной бот,
    # чтобы пользователям не приходилось делать это вручную из контрольного
    # бота. Ранее после рестарта supervisor основной бот оставался в
    # состоянии "остановлен", из-за чего не работали рассылки, планировщик
    # и каталог оставался пустым.
    if not manager.status()["running"]:
        await manager.start()
        logger.info("Основной бот автоматически запущен supervisor'ом")

    # Контрольный бот (только для указанных CONTROL_ADMINS)
    if not cfg.control_bot_token or not cfg.control_admin_ids:
        raise RuntimeError("CONTROL_BOT_TOKEN / CONTROL_ADMINS не заданы в .env")

    control_bot = Bot(
        cfg.control_bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher(storage=MemoryStorage())

    allowed_ids = set(cfg.control_admin_ids)
    dp.include_router(
        init_control_router(manager, parser_manager, allowed_ids, Session, cfg)
    )

    logger.info("Supervisor запущен. Используйте контрольного бота для управления основным.")
    try:
        await dp.start_polling(control_bot)
    finally:
        try:
            if manager.status()["running"]:
                await manager.stop()
        except Exception:
            logger.exception("Не удалось корректно остановить основной бот при завершении supervisor")
        try:
            if parser_manager.status().running:
                await parser_manager.stop()
        except Exception:
            logger.exception("Не удалось корректно остановить парсер-бот")
        await control_bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
