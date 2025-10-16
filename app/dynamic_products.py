from __future__ import annotations

from sqlalchemy import Table, Column, Integer, String, MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
import re

_CATEGORIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_categories (
    slug VARCHAR(128) PRIMARY KEY,
    title VARCHAR(256) NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0
);
"""

_meta = MetaData()

def _slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9а-яё_]+", "_", s, flags=re.IGNORECASE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "cat"
    return s

def _table_name_for_category(cat_name: str) -> str:
    return f"products_{_slugify(cat_name)}"

def _build_product_table(cat_name: str) -> Table:
    return Table(
        _table_name_for_category(cat_name),
        _meta,
        Column("id", Integer, primary_key=True),
        Column("title", String(512), nullable=False),
        Column("price", String(128), nullable=True),
        Column("url", String(1024), nullable=True),
        Column("image_url", String(1024), nullable=True),
        Column("created_at", String(64), server_default=text("now()")),
    )

def CreateTableSQL(tbl: Table) -> str:
    cols = []
    for c in tbl.columns:
        if c.primary_key:
            cols.append(f'{c.name} SERIAL PRIMARY KEY')
        elif c.name == "created_at":
            cols.append(f'{c.name} TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()')
        else:
            if isinstance(c.type, String):
                ln = c.type.length or 255
                cols.append(f'{c.name} VARCHAR({ln})')
            elif isinstance(c.type, Integer):
                cols.append(f'{c.name} INTEGER')
            else:
                cols.append(f'{c.name} TEXT')
    sql = f'CREATE TABLE IF NOT EXISTS "{tbl.name}" (\n  ' + ",\n  ".join(cols) + "\n);"
    return sql

async def list_existing_product_tables(session: AsyncSession) -> set[str]:
    q = sa_text("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = current_schema() AND tablename LIKE 'products_%';
    """)
    res = await session.execute(q)
    return set(r[0] for r in res.fetchall())

async def drop_table(session: AsyncSession, table_name: str):
    await session.execute(sa_text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE;'))

async def replace_all_categories_and_products(session: AsyncSession, categorized: dict[str, list[dict]]):
    """
    Полная замена каталога:
    - удаляем все старые product-таблицы,
    - создаём новые по категориям,
    - заливаем свежие товары.
    """
    await session.execute(sa_text(_CATEGORIES_TABLE_SQL))
    await session.execute(sa_text("TRUNCATE product_categories"))

    existing = await list_existing_product_tables(session)
    for t in existing:
        await drop_table(session, t)

    used_slugs: set[str] = set()

    for cat, items in categorized.items():
        slug = _slugify(cat)
        original_slug = slug
        suffix = 1
        while slug in used_slugs:
            slug = f"{original_slug}_{suffix}"
            suffix += 1
        used_slugs.add(slug)

        tbl = _build_product_table(slug)
        await session.execute(sa_text(CreateTableSQL(tbl)))
        tname = tbl.name
        for it in items:
            await session.execute(
                sa_text(
                    f'INSERT INTO "{tname}" (title, price, url, image_url) '
                    'VALUES (:title, :price, :url, :image)'
                ),
                {
                    "title": it.get("title", ""),
                    "price": it.get("price", ""),
                    "url": it.get("url"),
                    "image": it.get("image_url"),
                }
            )
        await session.execute(
            sa_text(
                "INSERT INTO product_categories (slug, title, item_count) "
                "VALUES (:slug, :title, :cnt)"
            ),
            {"slug": slug, "title": cat, "cnt": len(items)},
        )
    await session.commit()

async def fetch_categories_with_counts(session: AsyncSession) -> list[dict]:
    q = sa_text(
        "SELECT slug, title, item_count FROM product_categories ORDER BY title"
    )
    res = await session.execute(q)
    return [
        {"slug": r[0], "title": r[1], "count": r[2] or 0}
        for r in res.fetchall()
    ]

async def fetch_products_for_category(session: AsyncSession, cat_slug: str, limit: int = 20) -> list[dict]:
    tname = f"products_{cat_slug}"
    res = await session.execute(
        sa_text(
            f'SELECT id, title, price, url, image_url '
            f'FROM "{tname}" ORDER BY id DESC LIMIT :lim'
        ),
        {"lim": limit},
    )
    rows = res.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "url": r[3],
            "image_url": r[4],
        }
        for r in rows
    ]

async def fetch_category_by_slug(session: AsyncSession, slug: str) -> dict | None:
    res = await session.execute(
        sa_text(
            "SELECT slug, title, item_count FROM product_categories WHERE slug = :slug"
        ),
        {"slug": slug},
    )
    row = res.fetchone()
    if not row:
        return None
    return {"slug": row[0], "title": row[1], "count": row[2] or 0}

async def fetch_product_by_id(session: AsyncSession, cat_slug: str, product_id: int) -> dict | None:
    tname = f"products_{cat_slug}"
    res = await session.execute(
        sa_text(
            f'SELECT id, title, price, url, image_url '
            f'FROM "{tname}" WHERE id = :pid'
        ),
        {"pid": product_id},
    )
    row = res.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "price": row[2],
        "url": row[3],
        "image_url": row[4],
    }
