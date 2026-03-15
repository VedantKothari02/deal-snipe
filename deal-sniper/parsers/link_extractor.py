import re
import requests
import logging


logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'https?://[^\s]+',
    re.IGNORECASE
)

SHORT_DOMAINS = (
    "amzn.to",
    "fkrt.cc",
    "fkrt.it",
    "fktr.in",
    "bit.ly",
    "bitli.in",
    "myntr.it",
    "ajiio.in"
)

def extract_links(text: str) -> list:
    if not text:
        return []

    found_urls = URL_REGEX.findall(text)
    expanded_urls = []

    for url in found_urls:

        if any(domain in url for domain in SHORT_DOMAINS):
            try:
                response = requests.head(
                    url,
                    allow_redirects=True,
                    timeout=5
                )
                expanded = response.url
                expanded_urls.append(expanded)

                logger.info(f"Expanded {url} -> {expanded}")

            except Exception as e:
                logger.warning(f"Failed expanding {url}: {e}")
                expanded_urls.append(url)

        else:
            expanded_urls.append(url)

    return expanded_urls