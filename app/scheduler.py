from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from aiogram import Bot

from .config import AppConfig
from .notifier import ControlNotifier
from .catalog_refresh import refresh_catalog


def _parse_hhmm(s: str) -> tuple[int, int]:
    hh, mm = s.strip().split(":")
    return int(hh), int(mm)


def setup_scheduler(cfg: AppConfig, bot: Bot) -> AsyncIOScheduler:
    tz = ZoneInfo(cfg.tz)
    scheduler = AsyncIOScheduler(timezone=tz)

    hh, mm = _parse_hhmm(cfg.scrape.daily_time)
    scheduler.add_job(
        func=_daily_scrape_full_replace,
        trigger="cron",
        hour=hh,
        minute=mm,
        args=[cfg],
        id="daily_scrape_replace",
        replace_existing=True,
    )

    # авторассылка пользователям отключена по ТЗ (плейсхолдер)
    if cfg.broadcast.autosend_daily_time:
        bh, bm = _parse_hhmm(cfg.broadcast.autosend_daily_time)
        scheduler.add_job(
            func=_autosend_job,
            trigger="cron",
            hour=bh,
            minute=bm,
            args=[cfg, bot],
            id="daily_autosend",
            replace_existing=True,
        )

    return scheduler


async def _daily_scrape_full_replace(cfg: AppConfig):
    """
    Ежедневный парсинг:
      - парсим сайт(ы)
      - раскладываем по категориям
      - ПОЛНОСТЬЮ заменяем товарные таблицы (по 1 таблице на категорию)
      - отправляем отчёт в контрольный бот (только админам)
    """
    notifier = ControlNotifier(cfg.control_bot_token, cfg.control_admin_ids)
    try:
        total_cats, total_items = await refresh_catalog(cfg)
        await notifier.send(
            f"✅ Парсинг завершён: категорий {total_cats}, товаров {total_items}. Каталог обновлён."
        )
    except Exception as e:
        await notifier.send(f"❌ Ошибка парсинга/обновления: <code>{e}</code>")
        raise


async def _autosend_job(cfg: AppConfig, bot: Bot):
    # По ТЗ пользователям служебные уведомления не отправляем.
    return
