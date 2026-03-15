import re
import logging
import requests
import concurrent.futures
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

def detect_site(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    if 'amazon' in domain or 'amzn' in domain:
        return 'amazon'
    if 'flipkart' in domain or 'fkrt' in domain or 'fktr' in domain:
        return 'flipkart'
    if 'myntra' in domain or 'myntr' in domain:
        return 'myntra'
    if 'ajio' in domain or 'ajiio' in domain:
        return 'ajio'
    return 'unknown'

def normalize_url(url: str, site: str) -> str:
    """Removes tracking parameters to create a consistent URL."""
    try:
        parsed = urlparse(url)
        if site == 'amazon':
            match = re.search(r'/dp/([A-Z0-9]+)', parsed.path)
            if match:
                return f"https://www.amazon.in/dp/{match.group(1)}"
        elif site == 'flipkart':
            qs = parse_qs(parsed.query)
            pid = qs.get('pid', [None])[0]
            if pid:
                return f"https://www.flipkart.com{parsed.path}?pid={pid}"
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception as e:
        logger.warning(f"Failed to normalize url {url}: {e}")
    return url

def extract_product_id(url: str, site: str) -> str:
    """Extracts a unique identifier based on the site."""
    try:
        if site == 'amazon':
            match = re.search(r'/dp/([A-Z0-9]+)', url)
            return match.group(1) if match else url
        if site == 'flipkart':
            qs = parse_qs(urlparse(url).query)
            pid = qs.get('pid', [None])[0]
            return pid if pid else url
    except Exception as e:
        logger.warning(f"Failed to extract product ID from {url}: {e}")
    return url

def _expand_url_fast(short_url: str) -> str:
    """Quick helper for resolving shortened links during parsing."""
    try:
        res = requests.head(short_url, allow_redirects=True, timeout=2)
        return res.url
    except Exception:
        return short_url

def parse_deal(text: str, url: str) -> dict:
    """
    Parses deal information from messy telegram text and link.
    Correctly associates the specific URL with the text preceding it in multi-link messages.
    """
    site = detect_site(url)
    normalized_url = normalize_url(url, site)
    product_id = extract_product_id(normalized_url, site)

    # 1. Clean the text globally
    cleaned_text = re.sub(r'^\s*>\s*[A-Za-z0-9 ]+:\s*\n', '', text, flags=re.MULTILINE)
    cleaned_text = cleaned_text.replace('🖼', '').strip()

    url_pattern = re.compile(r'(https?://(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?://(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})', re.IGNORECASE)

    # Find all short urls in text
    found_urls = url_pattern.findall(cleaned_text)

    # We must find WHICH short url in `found_urls` expands to the target `url`
    # We expand all found URLs concurrently to map them.
    # Note: `extract_links` expands them too, but since we receive the expanded `url`,
    # we need this mapping to locate the exact short URL string in the text.
    url_map = {}
    if len(found_urls) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            expanded_results = list(executor.map(_expand_url_fast, found_urls))
        for orig, exp in zip(found_urls, expanded_results):
            # Normalize expanded result to match against our input `url` safely
            url_map[orig] = normalize_url(exp, detect_site(exp))
    elif len(found_urls) == 1:
        url_map[found_urls[0]] = normalized_url

    target_short_url = None
    for orig, exp in url_map.items():
        if exp == normalized_url or exp == url:
            target_short_url = orig
            break

    # 2. Partition the text into chunks delimited by URLs
    lines = cleaned_text.split('\n')
    chunks = []
    current_chunk = []

    for line in lines:
        current_chunk.append(line)
        if url_pattern.search(line):
            chunks.append("\n".join(current_chunk))
            current_chunk = []

    if current_chunk:
        if chunks:
            chunks[-1] += "\n" + "\n".join(current_chunk)
        else:
            chunks.append("\n".join(current_chunk))

    # 3. Locate the correct chunk for our `url`
    target_text = cleaned_text # Fallback

    if len(chunks) > 1 and target_short_url:
        for chunk in chunks:
            if target_short_url in chunk:
                target_text = chunk
                break
    elif len(chunks) > 1 and not target_short_url:
        # Fallback if mapping failed: match domain
        domain_to_short = {
            'amazon': ['amzn', 'amazon'],
            'flipkart': ['fkrt', 'fktr', 'flipkart', 'fk'],
            'myntra': ['myntr', 'myntra', 'bittli', 'bitli', 'bit.ly'],
            'ajio': ['ajiio', 'ajio', 'bittli', 'bitli', 'bit.ly']
        }
        possible_kws = domain_to_short.get(site, [site])
        for chunk in chunks:
            if any(kw in chunk.lower() for kw in possible_kws):
                target_text = chunk
                break

    # 4. Global Extractions (Discounts, Coupons usually apply to entire message)
    discount = 0.0
    discount_pattern = re.compile(r'(?:upto|min|flat|extra)?\s*(\d{1,3})\s*%\s*off', re.IGNORECASE)
    discount_matches = discount_pattern.findall(cleaned_text)
    if discount_matches:
        try:
            discount = float(max(int(x) for x in discount_matches))
        except ValueError:
            pass

    coupon_lines = []
    for line in cleaned_text.split('\n'):
        line_lower = line.lower()
        if any(kw in line_lower for kw in ['coupon', 'bank offer', 'credit card', 'cashback', 'code', 'hdfc', 'sbi', 'icici', 'axis', 'apply']):
            if 'http' not in line_lower:
                clean_line = re.sub(r'^[\W_]+', '', line).strip()
                if clean_line:
                    coupon_lines.append(clean_line)

    coupon_info = " + ".join(coupon_lines) if coupon_lines else None

    # 5. Local Extractions from the identified target chunk
    price = None

    # Filter out coupon lines from the target chunk so we don't extract "2500" from "2500 off with HDFC"
    filtered_target_text = target_text
    if coupon_info:
        for cl in coupon_lines:
            filtered_target_text = filtered_target_text.replace(cl, '')

    # Priority pattern for explicit price indicators
    price_pattern = re.compile(r'(?:at\s+|under\s+|starts\s+at\s+|for\s+)(?:₹|Rs\.?|INR)?\s*([\d,]+)(?:\.\d+)?', re.IGNORECASE)
    price_matches = price_pattern.findall(filtered_target_text)

    if not price_matches:
        # Generic fallback to any currency symbol
        price_pattern = re.compile(r'(?:₹|Rs\.?|INR)\s*([\d,]+)(?:\.\d+)?', re.IGNORECASE)
        price_matches = price_pattern.findall(filtered_target_text)

    if price_matches:
        try:
            # Pick the LAST matched price in the chunk (closest to the URL)
            price = float(price_matches[-1].replace(',', ''))
        except ValueError:
            pass

    if price is None:
        # Fallback for "Loot 298" without currency/prepositions
        fallback = re.compile(r'(?:loot\s+)([\d,]+)', re.IGNORECASE)
        fallback_matches = fallback.findall(filtered_target_text)
        if fallback_matches:
            try:
                price = float(fallback_matches[-1].replace(',', ''))
            except ValueError:
                pass

    product_name = "Unknown Product"

    # Heuristic: Find valid text lines (not empty, not URL, not coupon) in the target chunk.
    # The line immediately before the URL is generally the product name in multi-link messages.
    valid_name_lines = []
    for line in target_text.split('\n'):
        line_clean = line.strip()
        if not line_clean:
            continue
        if 'http' in line_clean.lower():
            continue

        is_coupon = False
        if coupon_info:
            clean_sub = re.sub(r'^[\W_]+', '', line_clean).strip()
            if clean_sub in coupon_info:
                is_coupon = True

        if not is_coupon:
            valid_name_lines.append(line_clean)

    if valid_name_lines:
        if len(chunks) > 1:
            product_name = valid_name_lines[-1] # closest to the url
        else:
            product_name = valid_name_lines[0] # general heading usually

    return {
        "product_name": product_name,
        "price": price,
        "mrp": None,
        "discount": discount,
        "coupon_info": coupon_info,
        "site": site,
        "product_id": product_id,
        "url": normalized_url
    }
