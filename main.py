"""
Price Tracker - Main Entry Point

Command-line interface for the Price Tracker application.

Usage:
    python main.py init          # Initialize database
    python main.py test-db       # Test database connection
    python main.py test-logging  # Test logging configuration
    
Future commands (Phase 2+):
    python main.py start         # Start scheduler
    python main.py scrape-now    # Run one-time scrape
    python main.py list-jobs     # List scheduled jobs
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database.connection import (
    init_database, 
    test_connection, 
    get_database_path,
    get_table_row_counts,
    database_exists
)
from utils.logging_config import get_logger, log_section_separator


# Setup logger
logger = get_logger(__name__)


def cmd_init(args):
    """Initialize the database"""
    log_section_separator(logger, "Initializing Database")
    
    if database_exists() and not args.force:
        logger.warning("Database already exists. Use --force to recreate.")
        response = input("Recreate database? This will delete all data (y/N): ")
        if response.lower() != 'y':
            logger.info("Initialization cancelled")
            return
    
    # Initialize with drop if forcing
    init_database(drop_existing=args.force)
    
    logger.info(f"Database location: {get_database_path()}")
    logger.info("✓ Database initialized successfully")


def cmd_test_db(args):
    """Test database connection"""
    log_section_separator(logger, "Testing Database Connection")
    
    # Check if database exists
    if not database_exists():
        logger.error("Database does not exist. Run 'python main.py init' first.")
        return
    
    # Test connection
    if test_connection():
        logger.info(f"Database path: {get_database_path()}")
        
        # Show table counts
        logger.info("\nTable row counts:")
        counts = get_table_row_counts()
        for table, count in counts.items():
            logger.info(f"  {table:15s}: {count} rows")
        
        logger.info("\n✓ All database tests passed")
    else:
        logger.error("✗ Database connection failed")


def cmd_test_logging(args):
    """Test logging configuration"""
    log_section_separator(logger, "Testing Logging System")
    
    # Test different log levels
    logger.debug("DEBUG: This is a debug message")
    logger.info("INFO: This is an info message")
    logger.warning("WARNING: This is a warning message")
    logger.error("ERROR: This is an error message")
    
    # Test exception logging
    try:
        _ = 1 / 0
    except Exception as e:
        logger.error("Exception test (this is expected)", exc_info=True)
    
    logger.info("\n✓ Logging test complete. Check logs/ folder for output files.")


def cmd_version(args):
    """Show version information"""
    print("Price Tracker v0.1.0 (Phase 1 Complete)")
    print("Foundation: Database, Logging, Configuration")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Price Tracker - Monitor competitor prices automatically",
        epilog="Phase 1 commands: init, test-db, test-logging"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    parser_init = subparsers.add_parser('init', help='Initialize database')
    parser_init.add_argument('--force', action='store_true', help='Force recreate (deletes existing data)')
    parser_init.set_defaults(func=cmd_init)
    
    # Test database command
    parser_test_db = subparsers.add_parser('test-db', help='Test database connection')
    parser_test_db.set_defaults(func=cmd_test_db)
    
    # Test logging command
    parser_test_log = subparsers.add_parser('test-logging', help='Test logging system')
    parser_test_log.set_defaults(func=cmd_test_logging)
    
    # Version command
    parser_version = subparsers.add_parser('version', help='Show version')
    parser_version.set_defaults(func=cmd_version)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    try:
        args.func(args)
    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
