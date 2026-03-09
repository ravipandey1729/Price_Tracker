"""
Pytest Fixtures

Shared test fixtures used across multiple test files.
Fixtures provide reusable test components like database sessions,
mock configurations, and sample data.

Usage:
    def test_something(db_session, sample_product):
        # db_session and sample_product are automatically provided
        product = db_session.query(Product).first()
        assert product.name == sample_product.name
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Product, Price, Threshold
from database.connection import init_engine


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_engine():
    """
    Create a test database engine (in-memory SQLite).
    Scope: session (created once per test session, shared by all tests)
    """
    # Use in-memory SQLite for fast tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup after all tests
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Create a database session for a single test.
    Scope: function (new session for each test, isolated)
    
    After each test, all changes are rolled back.
    """
    # Create session
    Session = sessionmaker(bind=test_engine)
    session = Session()
    
    yield session
    
    # Rollback all changes after test
    session.rollback()
    session.close()


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_product(db_session):
    """
    Create a sample product for testing.
    """
    product = Product(
        product_id="test_prod_001",
        name="Test Product - Sony Headphones",
        sku="TEST-SKU-001",
        category="Electronics"
    )
    db_session.add(product)
    db_session.commit()
    return product


@pytest.fixture
def sample_prices(db_session, sample_product):
    """
    Create sample price records for testing.
    """
    from datetime import datetime, timedelta
    
    prices = []
    base_price = 100.0
    
    # Create 7 days of price history
    for i in range(7):
        price = Price(
            product_id=sample_product.id,
            price=base_price - (i * 5),  # Decreasing price trend
            currency="USD",
            raw_price_text=f"${base_price - (i * 5):.2f}",
            source_site="Amazon",
            source_url="https://example.com/product",
            in_stock=True,
            scraped_at=datetime.utcnow() - timedelta(days=6-i)
        )
        db_session.add(price)
        prices.append(price)
    
    db_session.commit()
    return prices


@pytest.fixture
def sample_threshold(db_session, sample_product):
    """
    Create a sample alert threshold for testing.
    """
    threshold = Threshold(
        product_id=sample_product.id,
        target_price=80.0,
        percentage_drop=10.0,
        enabled=True,
        send_email=True,
        send_slack=False
    )
    db_session.add(threshold)
    db_session.commit()
    return threshold


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture
def mock_config():
    """
    Mock configuration dictionary for testing.
    """
    return {
        "database": {
            "path": ":memory:",
            "backup_enabled": False,
        },
        "scraping": {
            "min_delay": 0,  # No delay in tests
            "max_delay": 0,
            "max_retries": 2,
            "timeout_seconds": 10,
        },
        "alerts": {
            "email": {
                "enabled": False,  # Don't send real emails in tests
                "recipients": ["test@example.com"],
            },
            "slack": {
                "enabled": False,
            },
        },
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Mock environment variables for testing.
    """
    monkeypatch.setenv("EMAIL_USERNAME", "test@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "test_password")
    monkeypatch.setenv("EMAIL_FROM", "test@example.com")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST")


# ============================================================================
# HTTP MOCKING FIXTURES
# ============================================================================

@pytest.fixture
def mock_html_response():
    """
    Mock HTML response for scraper testing.
    """
    return """
    <html>
        <head><title>Test Product</title></head>
        <body>
            <h1 id="productTitle">Test Product - Sony Headphones</h1>
            <span id="priceblock_ourprice">$99.99</span>
            <span id="availability">In Stock</span>
        </body>
    </html>
    """


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_files():
    """
    Automatically cleanup test files after each test.
    autouse=True means this runs for every test automatically.
    """
    yield
    
    # Cleanup after test
    test_files = [
        "test_price_tracker.db",
        "test_config.yaml",
    ]
    
    for filename in test_files:
        if os.path.exists(filename):
            os.remove(filename)
