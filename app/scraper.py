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

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


def _build_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that tolerates Horizont's TLS configuration."""

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        context.set_ciphers("DEFAULT:@SECLEVEL=1")
    except ssl.SSLError:
        pass
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1
    except AttributeError:
        pass
    return context


def _configure_client() -> httpx.Client:
    ssl_context = _build_ssl_context()
    transport = httpx.HTTPTransport(
        retries=3,
        verify=ssl_context,
    )
    client = httpx.Client(
        transport=transport,
        verify=ssl_context,
        timeout=httpx.Timeout(25.0, connect=25.0, read=25.0),
        follow_redirects=True,
        headers={
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
        },
        trust_env=False,
    )
    return client


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
    client = _configure_client()

    try:
        products: List[Dict] = []
        seen: set[tuple[str, str]] = set()
        page = 1

        while page <= 20:  # предохранитель от бесконечных циклов
            page_url = _make_page_url(url, page)
            r = client.get(page_url)
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
        client.close()


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
