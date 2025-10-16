from __future__ import annotations

from typing import Tuple

from .scraper import scrape_products_multi
from .categorizer import pick_category_name
from .dynamic_products import replace_all_categories_and_products
from .config import AppConfig


async def refresh_catalog(cfg: AppConfig) -> Tuple[int, int]:
    """Собирает каталог с сайта и полностью обновляет товарные таблицы."""
    sources = [(src.url, src.category) for src in cfg.scrape.sources]

    items = scrape_products_multi(
        sources,
        {
            "card": cfg.scrape.selectors.card,
            "title": cfg.scrape.selectors.title,
            "price": cfg.scrape.selectors.price,
            "link_from_title": cfg.scrape.selectors.link_from_title,
            "image": getattr(cfg.scrape.selectors, "image", []) or [],
        },
    )

    categorized: dict[str, list[dict]] = {}
    for _, cat_title in sources:
        if cat_title:
            categorized.setdefault(cat_title, [])

    for it in items:
        cat_name = it.get("category") or pick_category_name(it["title"], cfg.categories) or "Прочее"
        categorized.setdefault(cat_name, []).append(it)

    # Удаляем категории без товаров
    categorized = {k: v for k, v in categorized.items() if v}

    total_items = sum(len(v) for v in categorized.values())
    total_cats = len(categorized)

    await replace_all_categories_and_products(None, categorized)

    return total_cats, total_items
