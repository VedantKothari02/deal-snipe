import pytest
from parsers.link_extractor import extract_links

def test_extract_links_basic():
    text = "Here is a link: https://www.amazon.in/dp/B08ABC123 and another one http://flipkart.com/someproduct"
    links = extract_links(text)
    assert len(links) == 2
    assert "https://www.amazon.in/dp/B08ABC123" in links
    assert "http://flipkart.com/someproduct" in links

def test_extract_links_no_links():
    text = "Just some text without any links."
    links = extract_links(text)
    assert len(links) == 0

def test_extract_links_shortened(monkeypatch):
    # Mock requests.head for testing shortened link expansion
    class MockResponse:
        def __init__(self, url):
            self.url = url

    def mock_head(url, *args, **kwargs):
        if "amzn.to" in url:
            return MockResponse("https://www.amazon.in/dp/B08ABC123")
        if "fkrt.cc" in url:
            return MockResponse("https://www.flipkart.com/product123")
        if "bitli.in" in url:
            return MockResponse("https://www.myntra.com/someproduct")
        if "ajiio.in" in url:
            return MockResponse("https://www.ajio.com/clothing")
        return MockResponse(url)

    import requests
    monkeypatch.setattr(requests, "head", mock_head)

    text = """Short links:
    https://amzn.to/short123
    https://fkrt.cc/hLOuuY2
    https://bitli.in/0LubWtVA
    https://ajiio.in/0r56nDT
    """
    links = extract_links(text)
    assert len(links) == 4
    assert links[0] == "https://www.amazon.in/dp/B08ABC123"
    assert links[1] == "https://www.flipkart.com/product123"
    assert links[2] == "https://www.myntra.com/someproduct"
    assert links[3] == "https://www.ajio.com/clothing"

def test_extract_multi_link():
    text = """
    Lino Perros, Caprese :
    https://bittli.in/0LubWtVA
    Lavie, Zouk at ₹279 :
    https://bittli.in/WttmnVkn
    """
    links = extract_links(text)
    assert len(links) == 2
    assert links[0] == "https://bittli.in/0LubWtVA"
    assert links[1] == "https://bittli.in/WttmnVkn"
