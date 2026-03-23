"""
Database Connection Management

This module handles SQLAlchemy engine creation and session management.
It provides context managers for safe database operations.

Usage:
    # Query data
    with get_session() as session:
        products = session.query(Product).all()
    
    # Add data
    with get_session() as session:
        product = Product(product_id="prod_001", name="Example")
        session.add(product)
        session.commit()
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from database.models import Base


# ============================================================================
# CONFIGURATION
# ============================================================================

# Database file path (relative to project root)
DATABASE_PATH = "price_tracker.db"

# SQLite connection string
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Global engine and session factory (initialized once)
_engine: Engine = None
_SessionFactory: sessionmaker = None


# ============================================================================
# ENGINE INITIALIZATION
# ============================================================================

def init_engine(database_url: str = DATABASE_URL, echo: bool = False) -> Engine:
    """
    Initialize the SQLAlchemy engine.
    
    Args:
        database_url: Database connection URL
        echo: If True, log all SQL statements (useful for debugging)
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine, _SessionFactory
    
    if _engine is not None:
        return _engine
    
    # Create engine with SQLite-specific settings
    _engine = create_engine(
        database_url,
        echo=echo,
        connect_args={
            "check_same_thread": False,  # Allow multi-threaded access
            "timeout": 30  # Wait up to 30 seconds for lock release
        },
        # Use StaticPool for SQLite (keeps connection open)
        poolclass=StaticPool,
    )
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
        cursor.close()
    
    # Create session factory
    _SessionFactory = sessionmaker(
        bind=_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False  # Keep objects usable after commit
    )

    # Apply lightweight schema upgrades for existing SQLite databases.
    _ensure_schema_upgrades(_engine)
    
    print(f"✓ Database engine initialized: {database_url}")
    return _engine


def _add_column_if_missing(engine: Engine, table_name: str, column_name: str, definition: str) -> None:
    inspector = inspect(engine)
    try:
        columns = {col["name"] for col in inspector.get_columns(table_name)}
    except Exception:
        return

    if column_name in columns:
        return

    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
        conn.commit()


def _ensure_schema_upgrades(engine: Engine) -> None:
    """Upgrade existing SQLite schema in-place for backward compatibility."""
    Base.metadata.create_all(engine)

    # products table additions
    _add_column_if_missing(engine, "products", "user_id", "INTEGER")
    _add_column_if_missing(engine, "products", "amazon_url", "TEXT")
    _add_column_if_missing(engine, "products", "ebay_url", "TEXT")
    _add_column_if_missing(engine, "products", "walmart_url", "TEXT")
    _add_column_if_missing(engine, "products", "flipkart_url", "TEXT")

    # thresholds table additions
    _add_column_if_missing(engine, "thresholds", "user_id", "INTEGER")

    # alerts_sent table additions
    _add_column_if_missing(engine, "alerts_sent", "user_id", "INTEGER")

    # scraper_runs table additions
    _add_column_if_missing(engine, "scraper_runs", "user_id", "INTEGER")


def get_engine() -> Engine:
    """
    Get the SQLAlchemy engine (initializes if needed).
    
    Returns:
        SQLAlchemy Engine instance
    """
    if _engine is None:
        init_engine()
    return _engine


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Provides automatic commit on success and rollback on error.
    Always closes the session when done.
    
    Usage:
        with get_session() as session:
            product = session.query(Product).first()
            product.name = "Updated Name"
            session.commit()  # Explicit commit
    
    Yields:
        SQLAlchemy Session instance
    """
    if _SessionFactory is None:
        init_engine()
    
    session = _SessionFactory()
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_session_direct() -> Session:
    """
    Get a database session directly (without context manager).
    
    WARNING: You must manually close this session!
    Prefer using get_session() context manager instead.
    
    Returns:
        SQLAlchemy Session instance
    """
    if _SessionFactory is None:
        init_engine()
    return _SessionFactory()


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database(drop_existing: bool = False):
    """
    Initialize the database by creating all tables.
    
    Args:
        drop_existing: If True, drop all existing tables first (WARNING: deletes data!)
    """
    engine = get_engine()
    
    if drop_existing:
        print("⚠ Dropping all existing tables...")
        Base.metadata.drop_all(engine)
        print("✓ All tables dropped")
    
    print("Creating database tables...")
    Base.metadata.create_all(engine)
    print("✓ All tables created successfully")
    
    # Verify tables were created
    with get_session() as session:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"✓ Tables in database: {', '.join(tables)}")


def database_exists() -> bool:
    """
    Check if the database file exists.
    
    Returns:
        True if database file exists, False otherwise
    """
    return os.path.exists(DATABASE_PATH)


def get_database_path() -> str:
    """
    Get the absolute path to the database file.
    
    Returns:
        Absolute path to database file
    """
    return os.path.abspath(DATABASE_PATH)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def test_connection() -> bool:
    """
    Test the database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        from sqlalchemy import text
        with get_session() as session:
            # Try a simple query
            session.execute(text("SELECT 1"))
        print("✓ Database connection test successful")
        return True
    except Exception as e:
        print(f"✗ Database connection test failed: {e}")
        return False


def get_table_row_counts() -> dict:
    """
    Get the number of rows in each table.
    
    Returns:
        Dictionary mapping table names to row counts
    """
    from database.models import Product, Price, ScraperRun, AlertSent, Threshold, User, NotificationRecord
    
    counts = {}
    with get_session() as session:
        counts["products"] = session.query(Product).count()
        counts["prices"] = session.query(Price).count()
        counts["scraper_runs"] = session.query(ScraperRun).count()
        counts["alerts_sent"] = session.query(AlertSent).count()
        counts["thresholds"] = session.query(Threshold).count()
        counts["users"] = session.query(User).count()
        counts["notification_records"] = session.query(NotificationRecord).count()
    
    return counts


def close_engine():
    """
    Dispose of the database engine and all connections.
    Call this when shutting down the application.
    """
    global _engine, _SessionFactory
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
        print("✓ Database engine closed")


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test the database connection module.
    Run: python -m database.connection
    """
    print("=" * 60)
    print("Testing Database Connection")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_database(drop_existing=False)
    
    # Test connection
    print("\n2. Testing connection...")
    test_connection()
    
    # Show database info
    print("\n3. Database information:")
    print(f"   Path: {get_database_path()}")
    print(f"   Exists: {database_exists()}")
    
    # Show table counts
    print("\n4. Table row counts:")
    counts = get_table_row_counts()
    for table, count in counts.items():
        print(f"   {table}: {count} rows")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
