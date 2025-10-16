from sqlalchemy import Table, Column, Integer, String, MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sa_text
import re

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
    q = sa_text(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = current_schema() AND tablename LIKE 'products_%';
        """
    )
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

    existing = await list_existing_product_tables(session)
    for t in existing:
        await drop_table(session, t)

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
    await session.execute(sa_text("TRUNCATE TABLE product_categories;"))

    # При повторных обновлениях SQLAlchemy кэширует таблицы в MetaData,
    # поэтому перед пересозданием очищаем метаданные.
    _meta.clear()

    for position, (cat, items) in enumerate(categorized.items(), start=1):
        tbl = _build_product_table(cat)
        await session.execute(sa_text(CreateTableSQL(tbl)))
        slug = tbl.name.removeprefix("products_")
        await session.execute(
            sa_text(
                "INSERT INTO product_categories (slug, title, position) VALUES (:slug, :title, :pos)"
            ),
            {"slug": slug, "title": cat, "pos": position},
        )
        tname = tbl.name
        for it in items:
            await session.execute(
                sa_text(
                    f'INSERT INTO "{tname}" (title, price, url, image_url) '
                    "VALUES (:title, :price, :url, :image)"
                ),
                {
                    "title": it.get("title", ""),
                    "price": it.get("price", ""),
                    "url": it.get("url"),
                    "image": it.get("image_url"),
                },
            )

    await session.commit()


async def fetch_categories_with_counts(session: AsyncSession) -> list[dict]:
    res = await session.execute(
        sa_text("SELECT slug, title FROM product_categories ORDER BY position")
    )
    rows = res.fetchall()
    out: list[dict] = []
    for slug, title in rows:
        tname = f"products_{slug}"
        cnt_res = await session.execute(sa_text(f'SELECT COUNT(*) FROM "{tname}"'))
        cnt = cnt_res.scalar() or 0
        out.append({"slug": slug, "title": title, "count": cnt})
    return out


async def fetch_products_for_category(session: AsyncSession, cat_slug: str, limit: int = 20) -> list[dict]:
    tname = f"products_{cat_slug}"
    res = await session.execute(
        sa_text(
            f'SELECT id, title, price, url, image_url FROM "{tname}" '
            "ORDER BY id DESC LIMIT :lim"
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


async def fetch_category_title(session: AsyncSession, slug: str) -> str | None:
    res = await session.execute(
        sa_text("SELECT title FROM product_categories WHERE slug = :slug"),
        {"slug": slug},
    )
    return res.scalar_one_or_none()


async def fetch_product(session: AsyncSession, slug: str, product_id: int) -> dict | None:
    tname = f"products_{slug}"
    res = await session.execute(
        sa_text(
            f'SELECT id, title, price, url, image_url FROM "{tname}" '
            "WHERE id = :pid"
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
