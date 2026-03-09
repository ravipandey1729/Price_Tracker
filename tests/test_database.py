"""
Test Database Models

Unit tests for database models and basic operations.
This verifies our database schema works correctly.

Run: pytest tests/test_database.py -v
"""

import pytest
from datetime import datetime

from database.models import Product, Price, Threshold, ScraperRun, AlertSent
from database.models import ScraperStatus, AlertType


# ============================================================================
# PRODUCT MODEL TESTS
# ============================================================================

def test_create_product(db_session):
    """Test creating a product"""
    product = Product(
        product_id="prod_test_001",
        name="Test Product",
        sku="TEST-SKU",
        category="Test Category"
    )
    
    db_session.add(product)
    db_session.commit()
    
    # Verify product was created
    assert product.id is not None
    assert product.product_id == "prod_test_001"
    assert product.name == "Test Product"
    assert product.created_at is not None


def test_product_unique_constraint(db_session, sample_product):
    """Test that product_id must be unique"""
    # Try to create product with same product_id
    duplicate = Product(
        product_id=sample_product.product_id,  # Same ID
        name="Duplicate Product"
    )
    
    db_session.add(duplicate)
    
    with pytest.raises(Exception):  # Should raise IntegrityError
        db_session.commit()


def test_product_relationships(db_session, sample_product, sample_prices):
    """Test product has relationship to prices"""
    # Reload product from database
    product = db_session.query(Product).first()
    
    # Check relationship
    assert len(product.prices) == len(sample_prices)
    assert product.prices[0].product_id == product.id


# ============================================================================
# PRICE MODEL TESTS
# ============================================================================

def test_create_price(db_session, sample_product):
    """Test creating a price record"""
    price = Price(
        product_id=sample_product.id,
        price=99.99,
        currency="USD",
        raw_price_text="$99.99",
        source_site="Amazon",
        in_stock=True
    )
    
    db_session.add(price)
    db_session.commit()
    
    assert price.id is not None
    assert price.price == 99.99
    assert price.scraped_at is not None


def test_price_query_by_site(db_session, sample_product):
    """Test querying prices by site"""
    # Create prices from different sites
    sites = ["Amazon", "eBay", "Walmart"]
    for site in sites:
        price = Price(
            product_id=sample_product.id,
            price=100.0,
            source_site=site
        )
        db_session.add(price)
    
    db_session.commit()
    
    # Query prices from Amazon
    amazon_prices = db_session.query(Price).filter(
        Price.source_site == "Amazon"
    ).all()
    
    assert len(amazon_prices) == 1
    assert amazon_prices[0].source_site == "Amazon"


# ============================================================================
# THRESHOLD MODEL TESTS
# ============================================================================

def test_create_threshold(db_session, sample_product):
    """Test creating alert threshold"""
    threshold = Threshold(
        product_id=sample_product.id,
        target_price=79.99,
        percentage_drop=15.0,
        enabled=True
    )
    
    db_session.add(threshold)
    db_session.commit()
    
    assert threshold.id is not None
    assert threshold.target_price == 79.99
    assert threshold.enabled is True


def test_threshold_relationship(db_session, sample_product, sample_threshold):
    """Test threshold relationship to product"""
    product = db_session.query(Product).first()
    
    assert len(product.thresholds) == 1
    assert product.thresholds[0].target_price == sample_threshold.target_price


# ============================================================================
# SCRAPER RUN MODEL TESTS
# ============================================================================

def test_create_scraper_run(db_session):
    """Test creating scraper run record"""
    run = ScraperRun(
        site_name="Amazon",
        status=ScraperStatus.RUNNING,
        products_attempted=10,
        products_succeeded=8,
        products_failed=2
    )
    
    db_session.add(run)
    db_session.commit()
    
    assert run.id is not None
    assert run.status == ScraperStatus.RUNNING
    assert run.products_succeeded == 8


def test_scraper_run_duration_calculation(db_session):
    """Test calculating scraper run duration"""
    from datetime import timedelta
    
    start = datetime.utcnow()
    end = start + timedelta(seconds=45)
    
    run = ScraperRun(
        site_name="eBay",
        status=ScraperStatus.SUCCESS,
        start_time=start,
        end_time=end,
        duration_seconds=45.0
    )
    
    db_session.add(run)
    db_session.commit()
    
    assert run.duration_seconds == 45.0


# ============================================================================
# ALERT SENT MODEL TESTS
# ============================================================================

def test_create_alert_sent(db_session, sample_product):
    """Test creating alert sent record"""
    alert = AlertSent(
        product_id=sample_product.id,
        alert_type=AlertType.PERCENTAGE_DROP,
        message="Price dropped by 15%",
        old_price=100.0,
        new_price=85.0,
        percentage_change=-15.0,
        sent_to="user@example.com",
        delivery_method="email",
        delivery_status="sent"
    )
    
    db_session.add(alert)
    db_session.commit()
    
    assert alert.id is not None
    assert alert.alert_type == AlertType.PERCENTAGE_DROP
    assert alert.percentage_change == -15.0


def test_alert_cooldown_check(db_session, sample_product):
    """Test checking if alert was recently sent"""
    from datetime import timedelta
    
    # Create recent alert
    recent_alert = AlertSent(
        product_id=sample_product.id,
        alert_type=AlertType.PERCENTAGE_DROP,
        message="Test",
        new_price=90.0,
        sent_to="user@example.com",
        delivery_method="email",
        sent_at=datetime.utcnow() - timedelta(hours=2)  # 2 hours ago
    )
    
    db_session.add(recent_alert)
    db_session.commit()
    
    # Check for alerts in last 6 hours
    cooldown_hours = 6
    cutoff_time = datetime.utcnow() - timedelta(hours=cooldown_hours)
    
    recent_alerts = db_session.query(AlertSent).filter(
        AlertSent.product_id == sample_product.id,
        AlertSent.sent_at >= cutoff_time
    ).all()
    
    assert len(recent_alerts) == 1


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
