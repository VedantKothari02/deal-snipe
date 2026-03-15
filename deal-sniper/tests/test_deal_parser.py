import pytest
from parsers.deal_parser import parse_deal, detect_site, normalize_url, extract_product_id

def test_detect_site():
    assert detect_site("https://www.amazon.in/dp/B08ABC123") == "amazon"
    assert detect_site("https://www.flipkart.com/p/itm123?pid=XYZ") == "flipkart"
    assert detect_site("https://www.myntra.com/product/123") == "myntra"
    assert detect_site("https://www.ajio.com/product/123") == "ajio"
    assert detect_site("https://www.google.com") == "unknown"

def test_normalize_url():
    # Test Amazon URL stripping
    url = "https://www.amazon.in/dp/B08ABC123?tag=affiliate_id&other=param"
    assert normalize_url(url, "amazon") == "https://www.amazon.in/dp/B08ABC123"

    # Test Flipkart URL parameter preservation
    url_fk = "https://www.flipkart.com/product/p/itm123?pid=XYZ123&tracking=true"
    assert normalize_url(url_fk, "flipkart") == "https://www.flipkart.com/product/p/itm123?pid=XYZ123"

def test_extract_product_id():
    assert extract_product_id("https://www.amazon.in/dp/B08ABC123", "amazon") == "B08ABC123"
    assert extract_product_id("https://www.flipkart.com/p/itm123?pid=XYZ123", "flipkart") == "XYZ123"

def test_parse_deal_basic():
    text = "> DealBee Deals:\nAwesome Samsung SSD\nPrice: ₹899\nMRP: 2999"
    url = "https://www.amazon.in/dp/B08ABC123?tag=something"

    parsed = parse_deal(text, url)

    assert parsed['product_name'] == "Awesome Samsung SSD"
    assert parsed['price'] == 899.0
    assert parsed['mrp'] is None
    assert parsed['site'] == "amazon"
    assert parsed['product_id'] == "B08ABC123"
    assert parsed['url'] == "https://www.amazon.in/dp/B08ABC123"

def test_parse_deal_messy_discount():
    text = "> DealBee Deals:\nUpto 90% Off On Wildhorn Backpack\n\nhttps://amzn.to/4bKjiEw"
    url = "https://amzn.to/4bKjiEw"

    parsed = parse_deal(text, url)
    assert parsed['product_name'] == "Upto 90% Off On Wildhorn Backpack"
    assert parsed['discount'] == 90.0
    assert parsed['price'] is None

def test_parse_deal_coupon_bank_offer():
    text = "> DealBee Deals:\nWhirlpool 1.5 Ton 3 Star, Magicool Inverter Split AC at ₹26,240\n\nApply ₹500 Off Coupon+ ₹2500 Off With HDFC Credit Card\n\nhttps://amzn.to/3EV5HfR"
    url = "https://amzn.to/3EV5HfR"

    parsed = parse_deal(text, url)
    assert parsed['product_name'] == "Whirlpool 1.5 Ton 3 Star, Magicool Inverter Split AC at ₹26,240"
    assert parsed['price'] == 26240.0
    assert "Apply ₹500 Off Coupon+ ₹2500 Off With HDFC Credit Card" in parsed['coupon_info']

def test_parse_deal_fallback_price():
    text = "> DealBee Deals:\n🖼 Combo Loot 298 :\nhttps://fkrt.cc/hLOuuY2"
    url = "https://fkrt.cc/hLOuuY2"

    parsed = parse_deal(text, url)
    assert "Combo Loot 298 :" in parsed['product_name']
    assert parsed['price'] == 298.0

def test_parse_deal_multi_link_different_sites():
    text = """
> DealBee Deals:
Branded Handbags Upto 75% Off

Lino Perros, Caprese :
https://bittli.in/0LubWtVA

Wrangler at ₹ 999
https://fkrt.cc/h13uLSO
"""
    # Test for the Myntra link
    parsed_myntra = parse_deal(text, "https://www.myntra.com/product1")
    assert "Lino Perros" in parsed_myntra['product_name']
    assert parsed_myntra['site'] == 'myntra'
    assert parsed_myntra['discount'] == 75.0

    # Test for the Flipkart link
    parsed_fkrt = parse_deal(text, "https://www.flipkart.com/product2")
    assert "Wrangler" in parsed_fkrt['product_name']
    assert parsed_fkrt['price'] == 999.0
    assert parsed_fkrt['site'] == 'flipkart'
    assert parsed_fkrt['discount'] == 75.0
