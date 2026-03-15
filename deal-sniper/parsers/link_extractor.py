import re
import requests
import logging
import concurrent.futures

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(https?://(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?://(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})',
    re.IGNORECASE
)

SHORTENERS = [
    "amzn.to", "fkrt.cc", "fkrt.it",
    "bitli.in", "bit.ly", "bittli.in", "myntr.it", "ajiio.in"
]

def _expand_url(url: str) -> str:
    """Helper to expand a single URL."""
    if any(shortener in url for shortener in SHORTENERS):
        try:
            # Short timeout to avoid blocking main thread too long
            response = requests.head(url, allow_redirects=True, timeout=3)
            return response.url
        except Exception as e:
            logger.warning(f"Failed to expand shortened URL {url}: {e}")
            return url
    return url

def extract_links(text: str) -> list:
    """
    Extracts ALL URLs from a block of text, then expands any shortened links
    using HTTP HEAD requests with redirects enabled.
    Returns the final destination URLs.
    Executes requests concurrently to minimize blocking the calling thread.
    """
    if not text:
        return []

    found_urls = URL_REGEX.findall(text)

    # We must preserve the original order of the URLs as they appear in the text
    expanded_urls = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # map preserves order
        results = executor.map(_expand_url, found_urls)
        expanded_urls = list(results)

    return expanded_urls
