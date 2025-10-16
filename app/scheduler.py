from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from .scraper import scrape_products_multi
from .categorizer import pick_category_name
from .dynamic_products import replace_all_categories_and_products
from .db import get_sessionmaker
from .config import AppConfig
from .notifier import ControlNotifier


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
    Session = get_sessionmaker()
    notifier = ControlNotifier(cfg.control_bot_token, cfg.control_admin_ids)
    try:
        items = scrape_products_multi(
            cfg.scrape.urls,
            {
                "card": cfg.scrape.selectors.card,
                "title": cfg.scrape.selectors.title,
                "price": cfg.scrape.selectors.price,
                "link_from_title": cfg.scrape.selectors.link_from_title,
            },
        )

        categorized: dict[str, list[dict]] = {}
        for it in items:
            cat_name = pick_category_name(it["title"], cfg.categories) or "Прочее"
            categorized.setdefault(cat_name, []).append(it)

        total_items = sum(len(v) for v in categorized.values())
        total_cats = len(categorized)

        async with Session() as s:  # type: AsyncSession
            await replace_all_categories_and_products(s, categorized)

        await notifier.send(
            f"✅ Парсинг завершён: категорий {total_cats}, товаров {total_items}. Каталог обновлён."
        )
    except Exception as e:
        await notifier.send(f"❌ Ошибка парсинга/обновления: <code>{e}</code>")
        raise


async def _autosend_job(cfg: AppConfig, bot: Bot):
    # По ТЗ пользователям служебные уведомления не отправляем.
    return
