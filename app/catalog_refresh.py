from __future__ import annotations

from typing import Tuple

from .scraper import scrape_products_multi
from .categorizer import pick_category_name
from .dynamic_products import replace_all_categories_and_products
from .db import get_sessionmaker
from .config import AppConfig


async def refresh_catalog(cfg: AppConfig) -> Tuple[int, int]:
    """Собирает каталог с сайта и полностью обновляет товарные таблицы."""
    items = scrape_products_multi(
        cfg.scrape.urls,
        {
            "card": cfg.scrape.selectors.card,
            "title": cfg.scrape.selectors.title,
            "price": cfg.scrape.selectors.price,
            "link_from_title": cfg.scrape.selectors.link_from_title,
            "image": getattr(cfg.scrape.selectors, "image", []) or [],
        },
    )

    categorized: dict[str, list[dict]] = {}
    for it in items:
        cat_name = pick_category_name(it["title"], cfg.categories) or "Прочее"
        categorized.setdefault(cat_name, []).append(it)

    total_items = sum(len(v) for v in categorized.values())
    total_cats = len(categorized)

    Session = get_sessionmaker()
    async with Session() as session:
        await replace_all_categories_and_products(session, categorized)

    return total_cats, total_items
