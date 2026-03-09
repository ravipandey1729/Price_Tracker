"""
Database Models for Price Tracker

This module defines the database schema using SQLAlchemy ORM.
Each class represents a table in the database.

Tables:
- Product: Master list of products being tracked
- Price: Historical price records (time-series data)
- ScraperRun: Metadata about scraping jobs
- AlertSent: History of sent alerts (prevents duplicates)
- Threshold: Per-product price alert thresholds
"""

from datetime import datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Boolean, ForeignKey, Text, Enum, Index
)
from sqlalchemy.orm import declarative_base, relationship
import enum

# Create base class for all models
Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class ScraperStatus(enum.Enum):
    """Status of a scraper run"""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some products succeeded, some failed
    FAILED = "failed"
    RUNNING = "running"


class AlertType(enum.Enum):
    """Type of price alert"""
    PERCENTAGE_DROP = "percentage_drop"
    TARGET_PRICE = "target_price"
    ALL_TIME_LOW = "all_time_low"
    COMPETITOR_BEAT = "competitor_beat"


# ============================================================================
# MODELS
# ============================================================================

class Product(Base):
    """
    Product model - stores master data about products being tracked.
    
    Each product has a unique ID, name, SKU, and category.
    Products have URLs on multiple competitor sites.
    """
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "prod_001"
    name = Column(String(500), nullable=False)
    sku = Column(String(100))  # Stock Keeping Unit / Model number
    category = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")
    thresholds = relationship("Threshold", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("AlertSent", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.name}')>"


class Price(Base):
    """
    Price model - stores historical price data (time-series).
    
    Each record captures the price of a product from a specific site at a specific time.
    This allows tracking price trends and calculating statistics.
    """
    __tablename__ = "prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Price data
    price = Column(Float, nullable=False)  # Normalized price
    currency = Column(String(10), default="USD", nullable=False)
    raw_price_text = Column(String(50))  # Original price text from site (e.g., "$19.99")
    
    # Source information
    source_site = Column(String(100), nullable=False, index=True)  # e.g., "Amazon"
    source_url = Column(Text)
    
    # Availability
    in_stock = Column(Boolean, default=True)
    availability_text = Column(String(200))  # e.g., "Only 3 left in stock"
    
    # Metadata
    scraper_run_id = Column(Integer, ForeignKey("scraper_runs.id"))
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    product = relationship("Product", back_populates="prices")
    scraper_run = relationship("ScraperRun", back_populates="prices")
    
    # Composite index for fast time-series queries
    __table_args__ = (
        Index('idx_product_time', 'product_id', 'scraped_at'),
        Index('idx_site_time', 'source_site', 'scraped_at'),
    )
    
    def __repr__(self):
        return f"<Price(product_id={self.product_id}, price={self.price}, site='{self.source_site}')>"


class ScraperRun(Base):
    """
    ScraperRun model - tracks metadata about scraping jobs.
    
    Each time the scraper runs, we create a record to track:
    - Which sites were scraped
    - How many products were successfully scraped
    - Any errors that occurred
    - Start and end times
    """
    __tablename__ = "scraper_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    site_name = Column(String(100), nullable=False)
    status = Column(Enum(ScraperStatus), default=ScraperStatus.RUNNING, nullable=False)
    
    # Statistics
    products_attempted = Column(Integer, default=0)
    products_succeeded = Column(Integer, default=0)
    products_failed = Column(Integer, default=0)
    
    # Error information
    error_message = Column(Text)
    error_details = Column(Text)  # JSON string with detailed error info
    
    # Timing
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime)
    duration_seconds = Column(Float)  # Calculated when run completes
    
    # Relationships
    prices = relationship("Price", back_populates="scraper_run")
    
    def __repr__(self):
        return f"<ScraperRun(id={self.id}, site='{self.site_name}', status={self.status.value})>"


class AlertSent(Base):
    """
    AlertSent model - tracks history of sent alerts.
    
    Prevents sending duplicate alerts by recording when each alert was sent.
    Also useful for analytics (how many alerts sent per product, etc.)
    """
    __tablename__ = "alerts_sent"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Alert details
    alert_type = Column(Enum(AlertType), nullable=False)
    message = Column(Text, nullable=False)
    
    # Price information at time of alert
    old_price = Column(Float)
    new_price = Column(Float, nullable=False)
    percentage_change = Column(Float)
    source_site = Column(String(100))
    
    # Delivery
    sent_to = Column(String(200))  # Email or Slack channel
    delivery_method = Column(String(20))  # "email" or "slack"
    delivery_status = Column(String(20), default="sent")  # "sent", "failed", "pending"
    
    # Timing
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    product = relationship("Product", back_populates="alerts")
    
    # Index for fast cooldown checks
    __table_args__ = (
        Index('idx_product_sent_time', 'product_id', 'sent_at'),
    )
    
    def __repr__(self):
        return f"<AlertSent(product_id={self.product_id}, type={self.alert_type.value}, sent_at={self.sent_at})>"


class Threshold(Base):
    """
    Threshold model - stores per-product alert thresholds.
    
    Each product can have custom alert conditions:
    - Target price (alert when price drops below this)
    - Percentage drop (alert when price drops by X%)
    - Enabled/disabled flag
    """
    __tablename__ = "thresholds"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # Threshold settings
    target_price = Column(Float)  # Alert if price drops below this
    percentage_drop = Column(Float)  # Alert if price drops by this % or more
    
    # Control
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Alert channels (can override global settings per product)
    send_email = Column(Boolean, default=True)
    send_slack = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="thresholds")
    
    def __repr__(self):
        return f"<Threshold(product_id={self.product_id}, target={self.target_price}, drop={self.percentage_drop}%)>"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_all_tables(engine):
    """
    Create all tables in the database.
    Call this once to initialize the database.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.create_all(engine)
    print("✓ All database tables created successfully")


def drop_all_tables(engine):
    """
    Drop all tables from the database.
    WARNING: This deletes all data!
    
    Args:
        engine: SQLAlchemy engine instance
    """
    Base.metadata.drop_all(engine)
    print("✓ All database tables dropped")
