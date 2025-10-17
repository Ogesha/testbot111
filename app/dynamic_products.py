from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9а-яё]+", "_", name.lower(), flags=re.IGNORECASE)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "cat"


async def _drop_legacy_tables(session: AsyncSession) -> None:
    """Удаляем устаревшие таблицы вида products_* (по категориям)."""

    res = await session.execute(
        sa_text(
            """
        SELECT tablename FROM pg_tables
        WHERE schemaname = current_schema()
          AND tablename LIKE 'products_%';
        """
        )
    )
    for (table_name,) in res.fetchall():
        await session.execute(sa_text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;'))


async def replace_all_categories_and_products(session: AsyncSession, categorized: dict[str, list[dict]]):
    """Пересобирает таблицы категорий и товаров заново."""

    await _drop_legacy_tables(session)

    await session.execute(
        sa_text(
            """
        CREATE TABLE IF NOT EXISTS product_categories (
            slug TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            position INTEGER NOT NULL
        );
        """
        )
    )

    await session.execute(
        sa_text(
            """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            category_slug TEXT NOT NULL REFERENCES product_categories(slug) ON DELETE CASCADE,
            category_title TEXT NOT NULL,
            title TEXT NOT NULL,
            price TEXT,
            url TEXT,
            image_path TEXT,
            image_url TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
        )
    )

    # Используем TRUNCATE ... CASCADE, чтобы корректно очистить связанные таблицы
    await session.execute(
        sa_text("TRUNCATE TABLE product_categories RESTART IDENTITY CASCADE;")
    )

    for position, (category_title, items) in enumerate(categorized.items(), start=1):
        slug = slugify(category_title)
        await session.execute(
            sa_text(
                "INSERT INTO product_categories (slug, title, position) VALUES (:slug, :title, :pos)"
            ),
            {"slug": slug, "title": category_title, "pos": position},
        )

        for item in items:
            await session.execute(
                sa_text(
                    """
                INSERT INTO products (category_slug, category_title, title, price, url, image_path, image_url)
                VALUES (:slug, :category_title, :title, :price, :url, :image_path, :image_url)
                """
                ),
                {
                    "slug": slug,
                    "category_title": category_title,
                    "title": item.get("title", ""),
                    "price": item.get("price"),
                    "url": item.get("url"),
                    "image_path": item.get("image_path"),
                    "image_url": item.get("image_url"),
                },
            )

    await session.commit()


async def fetch_categories_with_counts(session: AsyncSession) -> list[dict]:
    res = await session.execute(
        sa_text(
            """
        SELECT c.slug, c.title, COUNT(p.id) AS count
        FROM product_categories c
        LEFT JOIN products p ON p.category_slug = c.slug
        GROUP BY c.slug, c.title, c.position
        ORDER BY c.position;
        """
        )
    )
    return [
        {"slug": row[0], "title": row[1], "count": row[2]}
        for row in res.fetchall()
    ]


async def fetch_products_for_category(
    session: AsyncSession, cat_slug: str, limit: int = 20
) -> list[dict]:
    res = await session.execute(
        sa_text(
            """
        SELECT id, title, price, url, image_path, image_url
        FROM products
        WHERE category_slug = :slug
        ORDER BY id DESC
        LIMIT :limit;
        """
        ),
        {"slug": cat_slug, "limit": limit},
    )
    return [
        {
            "id": row[0],
            "title": row[1],
            "price": row[2],
            "url": row[3],
            "image_path": row[4],
            "image_url": row[5],
        }
        for row in res.fetchall()
    ]


async def fetch_category_title(session: AsyncSession, slug: str) -> str | None:
    res = await session.execute(
        sa_text("SELECT title FROM product_categories WHERE slug = :slug"),
        {"slug": slug},
    )
    return res.scalar_one_or_none()


async def fetch_product(session: AsyncSession, slug: str, product_id: int) -> dict | None:
    res = await session.execute(
        sa_text(
            """
        SELECT id, title, price, url, image_path, image_url
        FROM products
        WHERE category_slug = :slug AND id = :pid;
        """
        ),
        {"slug": slug, "pid": product_id},
    )
    row = res.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "price": row[2],
        "url": row[3],
        "image_path": row[4],
        "image_url": row[5],
    }
