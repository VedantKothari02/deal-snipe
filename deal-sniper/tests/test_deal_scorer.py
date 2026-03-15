import pytest
from engine.deal_scorer import score_deal

def test_score_deal_high_discount():
    # > 70% discount should give +40 points
    data = {
        'product_name': 'Generic Shirt',
        'price': 100,
        'mrp': 1000,
        'discount': 90.0,
        'site': 'amazon'
    }
    score = score_deal(data)
    assert score == 40

def test_score_deal_medium_discount():
    # > 50% discount should give +25 points
    data = {
        'product_name': 'Generic Shirt',
        'price': 400,
        'mrp': 1000,
        'discount': 60.0,
        'site': 'amazon'
    }
    score = score_deal(data)
    assert score == 25

def test_score_deal_price_drop():
    # mrp - price > 1000 INR should give +20 points
    data = {
        'product_name': 'Generic Phone',
        'price': 10000,
        'mrp': 12000,
        'discount': 16.6,
        'site': 'amazon'
    }
    score = score_deal(data)
    assert score == 20

def test_score_deal_keywords():
    # keywords like ssd, router, gpu, headphones should give +20 points
    data = {
        'product_name': 'Crucial 1TB SSD',
        'price': 5000,
        'mrp': 5500,
        'discount': 9.0,
        'site': 'amazon'
    }
    score = score_deal(data)
    assert score == 20

def test_score_deal_channel_keywords():
    # Channel keywords like loot, grab, glitch, steal deal -> +30 points
    data = {
        'product_name': 'Combo Loot 298',
        'price': 298,
        'mrp': None, # new safe none handling
        'discount': 0.0,
        'site': 'flipkart'
    }
    score = score_deal(data)
    assert score == 30

def test_score_deal_combined():
    # 70%+ discount (+40), >1000 drop (+20), keyword (+20) -> 80
    data = {
        'product_name': 'Samsung 1TB SSD',
        'price': 2000,
        'mrp': 10000,
        'discount': 80.0,
        'site': 'amazon'
    }
    score = score_deal(data)
    assert score == 80
