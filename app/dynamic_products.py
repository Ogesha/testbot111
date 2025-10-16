from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any

import requests


_BASE_DIR = Path(__file__).resolve().parent.parent
_CATALOG_DIR = _BASE_DIR / "catalog_data"
_CATEGORIES_FILE = _CATALOG_DIR / "categories.json"


def get_catalog_storage_dir() -> Path:
    """Возвращает директорию локального каталога товаров."""

    return _CATALOG_DIR


def _slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9а-яё_]+", "_", s, flags=re.IGNORECASE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "cat"
    return s


def _guess_extension(url: str, content_type: str | None) -> str:
    suffix = Path(url.split("?", 1)[0]).suffix
    if suffix:
        return suffix
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if ext:
            return ext
    return ".jpg"


def _download_image(image_url: str, images_dir: Path, product_id: int) -> str | None:
    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    ext = _guess_extension(image_url, resp.headers.get("Content-Type"))
    filename = f"{product_id}{ext}"
    dest = images_dir / filename
    try:
        with open(dest, "wb") as f:
            f.write(resp.content)
    except Exception:
        return None
    return dest.relative_to(_CATALOG_DIR).as_posix()


def _write_catalog(categorized: dict[str, list[dict[str, Any]]]):
    tmp_dir = _CATALOG_DIR.with_suffix(".tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    categories_meta: list[dict[str, Any]] = []

    for position, (cat_name, items) in enumerate(categorized.items(), start=1):
        slug = _slugify(cat_name)
        cat_dir = tmp_dir / slug
        images_dir = cat_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        products_out: list[dict[str, Any]] = []
        for idx, item in enumerate(items, start=1):
            image_path = None
            image_url = item.get("image_url")
            if image_url:
                image_path = _download_image(image_url, images_dir, idx)

            products_out.append(
                {
                    "id": idx,
                    "title": item.get("title", ""),
                    "price": item.get("price", ""),
                    "url": item.get("url"),
                    "image_url": image_url,
                    "image_path": image_path,
                }
            )

        products_file = cat_dir / "products.json"
        with open(products_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "category": cat_name,
                    "slug": slug,
                    "products": products_out,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        categories_meta.append(
            {
                "slug": slug,
                "title": cat_name,
                "position": position,
                "count": len(products_out),
            }
        )

    categories_meta.sort(key=lambda x: x["position"])
    with open(tmp_dir / "categories.json", "w", encoding="utf-8") as f:
        json.dump(categories_meta, f, ensure_ascii=False, indent=2)

    if _CATALOG_DIR.exists():
        shutil.rmtree(_CATALOG_DIR)
    tmp_dir.rename(_CATALOG_DIR)


async def replace_all_categories_and_products(session, categorized: dict[str, list[dict[str, Any]]]):
    """Полностью пересобирает локальный каталог товаров."""

    _ = session  # совместимость со старым вызовом
    await asyncio.to_thread(_write_catalog, categorized)


def _load_categories() -> list[dict[str, Any]]:
    if not _CATEGORIES_FILE.exists():
        return []
    with open(_CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_products(slug: str) -> dict[str, Any] | None:
    products_file = _CATALOG_DIR / slug / "products.json"
    if not products_file.exists():
        return None
    with open(products_file, "r", encoding="utf-8") as f:
        return json.load(f)


async def fetch_categories_with_counts(session) -> list[dict[str, Any]]:
    _ = session
    return await asyncio.to_thread(_load_categories)


async def fetch_products_for_category(session, cat_slug: str, limit: int = 20) -> list[dict[str, Any]]:
    _ = session
    data = await asyncio.to_thread(_load_products, cat_slug)
    if not data:
        return []
    products = data.get("products", [])
    if limit:
        products = products[:limit]
    return [dict(p) for p in products]


async def fetch_category_title(session, slug: str) -> str | None:
    _ = session
    categories = await asyncio.to_thread(_load_categories)
    for cat in categories:
        if cat.get("slug") == slug:
            return cat.get("title")
    return None


async def fetch_product(session, slug: str, product_id: int) -> dict[str, Any] | None:
    _ = session
    data = await asyncio.to_thread(_load_products, slug)
    if not data:
        return None
    for product in data.get("products", []):
        if product.get("id") == product_id:
            return dict(product)
    return None
