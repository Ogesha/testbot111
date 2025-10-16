from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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


def scrape_products(url: str, selectors: dict) -> List[Dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TGShopBot/1.0; +https://example.com/bot)"
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    products = []
    cards = []
    for css in selectors["card"]:
        cards.extend(soup.select(css))
    seen = set()
    for c in cards:
        title_el = _first_match(c, selectors["title"])
        price_el = _first_match(c, selectors["price"])
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or title in seen:
            continue
        seen.add(title)
        price = price_el.get_text(strip=True) if price_el else ""
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

        products.append({
            "title": title,
            "price": price,
            "url": link,
            "image_url": image_url,
        })
    return products

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
