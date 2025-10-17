from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from .config import AppConfig


def _parse_hhmm(s: str) -> tuple[int, int]:
    hh, mm = s.strip().split(":")
    return int(hh), int(mm)


def setup_scheduler(cfg: AppConfig, bot: Bot) -> AsyncIOScheduler:
    tz = ZoneInfo(cfg.tz)
    scheduler = AsyncIOScheduler(timezone=tz)

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


async def _autosend_job(cfg: AppConfig, bot: Bot):
    # По ТЗ пользователям служебные уведомления не отправляем.
    return
