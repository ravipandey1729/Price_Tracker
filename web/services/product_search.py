"""
Product search service for marketplace keyword search.
"""

from typing import Dict, List
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _to_float(price_text: str) -> float | None:
    cleaned = "".join(ch for ch in price_text if ch.isdigit() or ch in ".,")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _search_amazon(query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://www.amazon.com/s?k={quote(query)}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    items = []

    for card in soup.select("div.s-result-item[data-component-type='s-search-result']"):
        title_el = card.select_one("h2 a span")
        link_el = card.select_one("h2 a")
        price_whole = card.select_one("span.a-price-whole")
        price_frac = card.select_one("span.a-price-fraction")

        if not title_el or not link_el:
            continue

        title = title_el.get_text(strip=True)
        href = link_el.get("href", "")
        if not href:
            continue

        full_url = href if href.startswith("http") else f"https://www.amazon.com{href}"

        price = None
        currency = "USD"
        if price_whole:
            whole = price_whole.get_text(strip=True).replace(",", "")
            frac = price_frac.get_text(strip=True) if price_frac else "00"
            price = _to_float(f"{whole}.{frac}")

        items.append(
            {
                "site": "Amazon",
                "title": title,
                "url": full_url,
                "price": price,
                "currency": currency,
            }
        )

        if len(items) >= max_results:
            break

    return items


def _search_ebay(query: str, max_results: int = 5) -> List[Dict]:
    url = f"https://www.ebay.com/sch/i.html?_nkw={quote(query)}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    items = []

    for card in soup.select("li.s-item"):
        title_el = card.select_one(".s-item__title")
        link_el = card.select_one("a.s-item__link")
        price_el = card.select_one(".s-item__price")

        if not title_el or not link_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or title.lower().startswith("shop on ebay"):
            continue

        full_url = link_el.get("href", "")
        if not full_url:
            continue

        price = _to_float(price_el.get_text(strip=True)) if price_el else None

        items.append(
            {
                "site": "eBay",
                "title": title,
                "url": full_url,
                "price": price,
                "currency": "USD",
            }
        )

        if len(items) >= max_results:
            break

    return items


def search_products(query: str, sites: List[str], max_results_per_site: int = 5) -> Dict:
    """Search product candidates across requested sites."""
    query = query.strip()
    if not query:
        return {"query": query, "results": {}, "errors": {}}

    site_map = {
        "Amazon": _search_amazon,
        "eBay": _search_ebay,
    }

    results: Dict[str, List[Dict]] = {}
    errors: Dict[str, str] = {}

    for site in sites:
        search_func = site_map.get(site)
        if not search_func:
            errors[site] = "Site not supported yet"
            continue

        try:
            results[site] = search_func(query, max_results=max_results_per_site)
        except Exception as exc:
            errors[site] = str(exc)
            results[site] = []

    return {"query": query, "results": results, "errors": errors}
