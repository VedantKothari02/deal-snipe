import re
import time
import random
import logging
from bs4 import BeautifulSoup
from parsers.deal_parser import extract_product_id

logger = logging.getLogger(__name__)


def rate_limit():
    """Sleep 2–5 seconds to mimic human browsing."""
    delay = random.uniform(2, 5)
    time.sleep(delay)


def execute_with_retry(fetch_func, max_retries=2):
    """Retry failed requests with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return fetch_func()
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed after {max_retries} retries: {e}")
                return None
            delay = 2 ** attempt
            logger.warning(f"Request failed, retrying in {delay}s... ({e})")
            time.sleep(delay)


def normalize_flipkart_url(url: str) -> str:
    """
    Converts Flipkart redirect URLs like:
    https://dl.flipkart.com/dl/flipkart/p/item?pid=XXXX
    into a stable product URL.
    """
    match = re.search(r'pid=([A-Z0-9]+)', url)
    if match:
        pid = match.group(1)
        return f"https://www.flipkart.com/item/p/{pid}"
    return url


def fetch_product_data(url: str, session) -> dict:
    """Standard watcher interface for Flipkart."""

    url = normalize_flipkart_url(url)

    def do_fetch():
        rate_limit()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://www.flipkart.com/"
        }

        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Product name
        title_elem = (
            soup.find("span", class_="B_NuCI")
            or soup.find("span", class_="VU-Tz5")
        )
        product_name = title_elem.get_text(strip=True) if title_elem else "Unknown Flipkart Product"

        # Price
        price = 0.0
        price_elem = (
            soup.find("div", class_="_30jeq3 _16Jk6d")
            or soup.find("div", class_="Nx9bqj CxhGGd")
        )

        if price_elem:
            text = price_elem.get_text(strip=True)
            clean = re.sub(r"[^\d.]", "", text.replace(",", ""))
            if clean:
                price = float(clean)

        # MRP
        mrp = price
        mrp_elem = (
            soup.find("div", class_="_3I9_wc _2p6lqe")
            or soup.find("div", class_="yRaY8j A6z5UK")
        )

        if mrp_elem:
            text = mrp_elem.get_text(strip=True)
            clean = re.sub(r"[^\d.]", "", text.replace(",", ""))
            if clean:
                mrp = float(clean)

        product_id = extract_product_id(url, "flipkart")

        return {
            "product_id": product_id,
            "product_name": product_name,
            "price": price,
            "mrp": max(price, mrp),
            "site": "flipkart",
            "url": url,
        }

    return execute_with_retry(do_fetch)