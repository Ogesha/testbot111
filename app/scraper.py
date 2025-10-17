from typing import List, Dict
import logging
import ssl
from urllib.parse import (
    urljoin,
    urlsplit,
    urlunsplit,
    urlencode,
    parse_qsl,
)

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class _LenientHTTPSAdapter(HTTPAdapter):
    """HTTPAdapter with relaxed TLS settings for problematic endpoints."""

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        context = create_urllib3_context()
        # Ослабляем настройки безопасности, чтобы переживать нестандартную конфигурацию TLS на сайте
        try:
            context.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass
        context.check_hostname = False
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1
        except AttributeError:
            pass
        pool_kwargs["ssl_context"] = context
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context()
        try:
            context.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass
        context.check_hostname = False
        try:
            context.minimum_version = ssl.TLSVersion.TLSv1
        except AttributeError:
            pass
        kwargs["ssl_context"] = context
        return super().proxy_manager_for(*args, **kwargs)


def _configure_session(lenient: bool = False) -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # обход прокси из окружения, мешающих доступу к сайту

    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(403, 408, 429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    if lenient:
        lenient_adapter = _LenientHTTPSAdapter(max_retries=retries)
        session.mount("https://", lenient_adapter)
        session.verify = False
    else:
        session.mount("https://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9," "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "close",
            "Referer": "https://horizont.garant.by/",
        }
    )
    return session


def _first_match(el, selectors: list[str]):
    for css in selectors:
        found = el.select_one(css)
        if found:
            return found
    return None


def _extract_image_url(el) -> str | None:
    if el is None:
        return None
    for attr in ("src", "data-src", "data-original", "data-lazy", "data-srcset"):
        val = el.get(attr)
        if not val:
            continue
        if attr == "data-srcset":
            val = val.split()[0]
        return val.strip()
    if el.string:
        return el.string.strip()
    return None


def _extend_cards(soup: BeautifulSoup, selectors: dict) -> list:
    cards: list = []
    for css in selectors["card"]:
        for el in soup.select(css):
            if el not in cards:
                cards.append(el)
    return cards


def _make_page_url(url: str, page: int) -> str:
    if page <= 1:
        return url

    parsed = urlsplit(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(query_pairs)
    pagen_key = None
    for key in query:
        if key.startswith("PAGEN_"):
            pagen_key = key
            break
    if not pagen_key:
        pagen_key = "PAGEN_1"
    query[pagen_key] = str(page)
    new_query = urlencode(query, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def _has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    next_selectors = [
        "a[rel='next']",
        "a.pagination__item--next",
        "a.pagination__next",
        "a.pagination-next",
        "a.js-catalog-pagination-next",
        "button.js-catalog-pagination-next",
    ]
    for css in next_selectors:
        el = soup.select_one(css)
        if not el:
            continue
        classes = el.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        if any(cls in {"disabled", "pagination__item--disabled", "is-disabled"} for cls in classes):
            continue
        if el.get("aria-disabled") in {"true", "1"}:
            continue
        return True

    pagination = soup.select_one(".pagination") or soup.select_one("[data-pagination-pages]")
    if pagination:
        for attr in ("data-pages", "data-pagination-pages", "data-total", "data-max-page"):
            value = pagination.get(attr)
            if value and value.isdigit():
                return current_page < int(value)
    return False


def scrape_products(url: str, selectors: dict) -> List[Dict]:
    session = _configure_session()
    lenient_session: requests.Session | None = None

    try:
        products: List[Dict] = []
        seen: set[tuple[str, str]] = set()
        page = 1

        while page <= 20:  # предохранитель от бесконечных циклов
            page_url = _make_page_url(url, page)
            try:
                r = session.get(page_url, timeout=25)
            except SSLError as exc:
                logger.warning(
                    "SSL error while requesting %s: %s. Retrying with relaxed TLS settings.",
                    page_url,
                    exc,
                )
                if lenient_session is None:
                    lenient_session = _configure_session(lenient=True)
                r = lenient_session.get(page_url, timeout=25)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            cards = _extend_cards(soup, selectors)
            new_items = 0
            for c in cards:
                title_el = _first_match(c, selectors["title"])
                price_el = _first_match(c, selectors["price"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title:
                    continue
                price = price_el.get_text(strip=True) if price_el else ""
                key = (title, price)
                if key in seen:
                    continue
                seen.add(key)

                link = None
                if selectors.get("link_from_title", True):
                    if title_el.name == "a" and title_el.get("href"):
                        link = title_el["href"]
                    else:
                        a = title_el.find("a")
                        if a and a.get("href"):
                            link = a["href"]
                if link:
                    link = urljoin(url, link)

                image_url = None
                image_selectors = selectors.get("image") or []
                if image_selectors:
                    img_el = _first_match(c, image_selectors)
                    image_url = _extract_image_url(img_el)
                    if image_url:
                        image_url = urljoin(url, image_url)

                products.append(
                    {
                        "title": title,
                        "price": price,
                        "url": link,
                        "image_url": image_url,
                    }
                )
                new_items += 1

            if new_items == 0 or not _has_next_page(soup, page):
                break
            page += 1

        return products
    finally:
        session.close()
        if lenient_session is not None:
            lenient_session.close()


def scrape_products_multi(sources: list[tuple[str, str | None]], selectors: dict) -> List[Dict]:
    out: List[Dict] = []
    for url, category in sources:
        try:
            products = scrape_products(url, selectors)
        except Exception:
            pass
        else:
            if category:
                for p in products:
                    p.setdefault("category", category)
            out.extend(products)
    return out
