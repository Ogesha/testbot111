from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, TypeVar
from urllib.parse import urlencode, urljoin

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://horizont.garant.by"


class CatalogFetchError(RuntimeError):
    """Raised when the catalog could not be downloaded."""


@dataclass(slots=True)
class CatalogItem:
    title: str
    price: str | None = None
    url: str | None = None
    image_url: str | None = None


def _create_session(use_env: bool) -> requests.Session:
    session = requests.Session()
    session.trust_env = use_env
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
    )
    return session


T = TypeVar("T")


def _with_fallback(func: Callable[[requests.Session], T]) -> T:
    last_err: Exception | None = None
    for use_env in (True, False):
        session = _create_session(use_env)
        try:
            return func(session)
        except (requests.exceptions.RequestException, CatalogFetchError) as err:
            logger.warning("Request via %s proxies failed: %s", "with" if use_env else "without", err)
            last_err = err
    if last_err is not None:
        raise CatalogFetchError(str(last_err)) from last_err
    raise CatalogFetchError("Не удалось выполнить запрос")


def _request_json(session: requests.Session, url: str) -> tuple[list, requests.Response]:
    logger.debug("Fetching %s", url)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise CatalogFetchError(f"Unexpected response format for {url}")
    return data, resp


def _format_price(prices: dict) -> str | None:
    raw_price = prices.get("price") or prices.get("regular_price")
    if raw_price in (None, ""):
        return None

    decimals = prices.get("decimals")
    try:
        value = Decimal(str(raw_price))
        if decimals is not None:
            value = value / (Decimal(10) ** int(decimals))
    except (InvalidOperation, ValueError):
        return str(raw_price)

    currency = prices.get("currency_symbol") or prices.get("currency_code")
    if currency:
        return f"{value.normalize()} {currency}".strip()
    return str(value.normalize())


def _fetch_categories(session: requests.Session) -> list[dict]:
    url = urljoin(
        BASE_URL,
        "/wp-json/wp/v2/product_cat?per_page=100&_fields=id,name,parent,count",
    )
    data, _ = _request_json(session, url)
    return data


def _fetch_products(session: requests.Session, cat_id: int) -> List[CatalogItem]:
    items: List[CatalogItem] = []
    page = 1
    while True:
        params = {"per_page": 100, "category": cat_id, "page": page}
        url = urljoin(BASE_URL, "/wp-json/wc/store/products?" + urlencode(params))
        data, resp = _request_json(session, url)
        if not data:
            break

        for prod in data:
            name = (prod.get("name") or "").strip()
            permalink = prod.get("permalink")
            price_info = prod.get("prices", {})
            price_html = prod.get("price_html")
            price = _format_price(price_info)
            if not price and price_html:
                price = price_html

            images = prod.get("images") or []
            image_url = None
            if images:
                image_url = images[0].get("src")

            items.append(
                CatalogItem(
                    title=name,
                    price=price.strip() if isinstance(price, str) else price,
                    url=permalink,
                    image_url=image_url,
                )
            )

        total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1

    return items


def fetch_horizont_catalog() -> Dict[str, List[dict]]:
    """Download catalog from horizont.garant.by and return grouped products."""

    categories = _with_fallback(_fetch_categories)
    if not categories:
        raise CatalogFetchError("Не удалось загрузить список категорий")

    top_categories = [
        cat for cat in categories if not cat.get("parent") and (cat.get("count") or 0) > 0
    ]

    catalog: Dict[str, List[dict]] = {}

    for cat in top_categories:
        cat_name = cat.get("name") or f"Категория {cat.get('id')}"
        cat_id = cat.get("id")

        def loader(session: requests.Session) -> List[CatalogItem]:
            return _fetch_products(session, cat_id)

        products = _with_fallback(loader)
        catalog[cat_name] = [
            {
                "title": item.title,
                "price": item.price,
                "url": item.url,
                "image_url": item.image_url,
            }
            for item in products
        ]

    return catalog

