"""
Price Tracker - Main Entry Point

Command-line interface for the Price Tracker application.

Usage:
    python main.py init          # Initialize database
    python main.py test-db       # Test database connection
    python main.py test-logging  # Test logging configuration
    python main.py scrape-now    # Run all scrapers once
    python main.py scrape-site <name>  # Run specific site scraper
    python main.py start         # Start scheduler daemon
    python main.py stop          # Stop scheduler daemon
    python main.py restart       # Restart scheduler
    python main.py status        # Show scheduler status
    python main.py list-jobs     # List scheduled jobs
"""

import sys
import argparse
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database.connection import (
    init_database, 
    test_connection, 
    get_database_path,
    get_table_row_counts,
    database_exists,
    get_session
)
from utils.logging_config import get_logger, log_section_separator
from utils.config import load_config
from scrapers.orchestrator import ScraperOrchestrator
from scrapers.scraper_factory import get_available_sites
from scheduler.daemon_manager import SchedulerDaemon


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
    print("Price Tracker v0.3.0 (Phase 3: Job Scheduling)")
    print("Features: Database, Logging, Configuration, Web Scraping, Automated Scheduling")


def cmd_scrape_now(args):
    """Run all configured scrapers once"""
    log_section_separator(logger, "Running All Scrapers")
    
    # Check database exists
    if not database_exists():
        logger.error("Database not initialized. Run 'python main.py init' first.")
        return
    
    try:
        # Load configuration
        config = load_config()
        logger.info(f"Loaded configuration from config.yaml")
        
        # Run scrapers
        with get_session() as session:
            orchestrator = ScraperOrchestrator(session, config, max_workers=args.workers)
            results = orchestrator.run_all_scrapers()
        
        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("SCRAPING COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total products: {results['total_products']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Duration: {results['duration']:.2f} seconds")
        logger.info("=" * 70)
        
        if results['failed'] > 0:
            logger.warning("\nSome products failed to scrape. Check scraper_errors.log for details.")
        
        logger.info("\n✓ Scraping completed successfully")
    
    except Exception as e:
        logger.error(f"✗ Scraping failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_scrape_site(args):
    """Run scraper for a specific site"""
    site_name = args.site
    
    log_section_separator(logger, f"Scraping Site: {site_name}")
    
    # Check if site is supported
    available_sites = get_available_sites()
    if site_name not in available_sites:
        logger.error(f"Site '{site_name}' is not supported.")
        logger.info(f"Available sites: {', '.join(available_sites)}")
        return
    
    # Check database exists
    if not database_exists():
        logger.error("Database not initialized. Run 'python main.py init' first.")
        return
    
    try:
        # Load configuration
        config = load_config()
        
        # Run scraper
        with get_session() as session:
            orchestrator = ScraperOrchestrator(session, config, max_workers=1)
            results = orchestrator.run_site_scraper(site_name)
        
        # Display results
        logger.info("\n" + "=" * 70)
        logger.info(f"SCRAPING COMPLETE: {site_name}")
        logger.info("=" * 70)
        logger.info(f"Total products: {results['total_products']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Duration: {results['duration']:.2f} seconds")
        logger.info("=" * 70)
        
        logger.info("\n✓ Site scraping completed")
    
    except Exception as e:
        logger.error(f"✗ Site scraping failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_list_sites(args):
    """List all supported sites"""
    log_section_separator(logger, "Supported Sites")
    
    sites = get_available_sites()
    
    logger.info(f"Total supported sites: {len(sites)}\n")
    
    for i, site in enumerate(sites, 1):
        logger.info(f"  {i}. {site}")
    
    logger.info("\nUse 'python main.py scrape-site <name>' to scrape a specific site")


def cmd_start(args):
    """Start the scheduler daemon"""
    log_section_separator(logger, "Starting Scheduler")
    
    # Check database exists
    if not database_exists():
        logger.error("Database not initialized. Run 'python main.py init' first.")
        return
    
    try:
        # Load configuration
        config = load_config()
        
        # Create daemon manager
        daemon = SchedulerDaemon(config)
        
        # Check if already running
        if daemon.is_running():
            pid = daemon.get_pid()
            logger.warning(f"Scheduler is already running (PID: {pid})")
            logger.info("Use 'python main.py status' to see details")
            logger.info("Use 'python main.py stop' to stop it")
            return
        
        # Start daemon
        if args.foreground:
            # Start in foreground (blocking)
            logger.info("Starting scheduler in foreground mode...")
            logger.info("Press Ctrl+C to stop\n")
            daemon.start(foreground=True)
        else:
            # Start in background
            if daemon.start(foreground=False):
                logger.info("\n✓ Scheduler started successfully in background")
                
                # Show next run information
                time.sleep(1)  # Give scheduler time to initialize
                status = daemon.get_status()
                
                if status['running']:
                    logger.info(f"  PID: {status['pid']}")
                    logger.info(f"  Log file: {status['log_file']}")
                    logger.info("\nScheduler will run scrapers at configured intervals.")
                    logger.info("Use 'python main.py status' to check status")
                    logger.info("Use 'python main.py stop' to stop the scheduler")
            else:
                logger.error("\n✗ Failed to start scheduler")
                logger.info(f"Check log file: {daemon.daemon_log}")
                sys.exit(1)
    
    except Exception as e:
        logger.error(f"✗ Failed to start scheduler: {e}", exc_info=True)
        sys.exit(1)


def cmd_stop(args):
    """Stop the scheduler daemon"""
    log_section_separator(logger, "Stopping Scheduler")
    
    try:
        # Load configuration
        config = load_config()
        
        # Create daemon manager
        daemon = SchedulerDaemon(config)
        
        # Check if running
        if not daemon.is_running():
            logger.warning("Scheduler is not running")
            return
        
        # Stop daemon
        pid = daemon.get_pid()
        logger.info(f"Stopping scheduler (PID: {pid})...")
        
        if daemon.stop(timeout=args.timeout):
            logger.info("\n✓ Scheduler stopped successfully")
        else:
            logger.error("\n✗ Failed to stop scheduler")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"✗ Failed to stop scheduler: {e}", exc_info=True)
        sys.exit(1)


def cmd_restart(args):
    """Restart the scheduler daemon"""
    log_section_separator(logger, "Restarting Scheduler")
    
    try:
        # Load configuration
        config = load_config()
        
        # Create daemon manager
        daemon = SchedulerDaemon(config)
        
        # Restart
        if daemon.restart():
            logger.info("\n✓ Scheduler restarted successfully")
            
            # Show status
            status = daemon.get_status()
            if status['running']:
                logger.info(f"  PID: {status['pid']}")
                logger.info(f"  Log file: {status['log_file']}")
        else:
            logger.error("\n✗ Failed to restart scheduler")
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"✗ Failed to restart scheduler: {e}", exc_info=True)
        sys.exit(1)


def cmd_status(args):
    """Show scheduler status"""
    log_section_separator(logger, "Scheduler Status")
    
    try:
        # Load configuration
        config = load_config()
        
        # Create daemon manager
        daemon = SchedulerDaemon(config)
        
        # Get status
        status = daemon.get_status()
        
        logger.info(f"\nRunning: {status['running']}")
        
        if status['running']:
            logger.info(f"PID: {status['pid']}")
            logger.info(f"Status: {status.get('status', 'unknown')}")
            logger.info(f"CPU: {status.get('cpu_percent', 0):.1f}%")
            logger.info(f"Memory: {status.get('memory_mb', 0):.1f} MB")
            
            if 'started_at' in status:
                logger.info(f"Started: {status['started_at']}")
            
            if 'uptime_seconds' in status:
                uptime = status['uptime_seconds']
                hours = int(uptime // 3600)
                minutes = int((uptime % 3600) // 60)
                logger.info(f"Uptime: {hours}h {minutes}m")
            
            logger.info(f"\nLog file: {status['log_file']}")
            logger.info(f"PID file: {status['pid_file']}")
            
            # Show last few log lines if verbose
            if args.verbose:
                logger.info("\nRecent log entries:")
                log_file = Path(status['log_file'])
                if log_file.exists():
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        for line in lines[-10:]:  # Last 10 lines
                            print(f"  {line.rstrip()}")
        else:
            logger.info("Scheduler is not running")
            logger.info("\nUse 'python main.py start' to start the scheduler")
    
    except Exception as e:
        logger.error(f"✗ Failed to get status: {e}", exc_info=True)
        sys.exit(1)


def cmd_list_jobs(args):
    """List scheduled jobs"""
    log_section_separator(logger, "Scheduled Jobs")
    
    try:
        # Load configuration
        config = load_config()
        daemon = SchedulerDaemon(config)
        
        # Check if running
        if not daemon.is_running():
            logger.warning("Scheduler is not running")
            logger.info("Use 'python main.py start' to start the scheduler")
            return
        
        # Note: This requires the scheduler to expose job information
        # For now, show configuration
        scheduler_config = config.get('scheduler', {})
        
        logger.info("\nScheduler Configuration:")
        
        interval_hours = scheduler_config.get('scrape_interval_hours')
        if interval_hours:
            logger.info(f"  Scrape Interval: Every {interval_hours} hours")
        
        cron_expr = scheduler_config.get('scrape_cron')
        if cron_expr:
            logger.info(f"  Cron Expression: {cron_expr}")
        
        # Show scraping configuration
        scraping_config = config.get('scraping', {})
        logger.info(f"\nScraping Settings:")
        logger.info(f"  Max Workers: {scraping_config.get('max_workers', 3)}")
        logger.info(f"  Timeout: {scraping_config.get('timeout', 30)}s")
        
        # Show products
        products = config.get('products', [])
        logger.info(f"\nProducts to Track: {len(products)}")
        for product in products:
            logger.info(f"  • {product.get('id')}: {product.get('name', 'N/A')}")
            sites = list(product.get('urls', {}).keys())
            logger.info(f"    Sites: {', '.join(sites)}")
    
    except Exception as e:
        logger.error(f"✗ Failed to list jobs: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Price Tracker - Monitor competitor prices automatically",
        epilog="Available commands: init, test-db, test-logging, scrape-now, scrape-site, start, stop, restart, status, list-jobs"
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
    
    # Scrape all command
    parser_scrape_now = subparsers.add_parser('scrape-now', help='Run all scrapers once')
    parser_scrape_now.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser_scrape_now.set_defaults(func=cmd_scrape_now)
    
    # Scrape site command
    parser_scrape_site = subparsers.add_parser('scrape-site', help='Run scraper for specific site')
    parser_scrape_site.add_argument('site', help='Site name (e.g., Amazon, eBay)')
    parser_scrape_site.set_defaults(func=cmd_scrape_site)
    
    # List sites command
    parser_list_sites = subparsers.add_parser('list-sites', help='List all supported sites')
    parser_list_sites.set_defaults(func=cmd_list_sites)
    
    # Start scheduler command
    parser_start = subparsers.add_parser('start', help='Start scheduler daemon')
    parser_start.add_argument('--foreground', action='store_true', help='Run in foreground (blocks until Ctrl+C)')
    parser_start.set_defaults(func=cmd_start)
    
    # Stop scheduler command
    parser_stop = subparsers.add_parser('stop', help='Stop scheduler daemon')
    parser_stop.add_argument('--timeout', type=int, default=10, help='Seconds to wait for graceful shutdown (default: 10)')
    parser_stop.set_defaults(func=cmd_stop)
    
    # Restart scheduler command
    parser_restart = subparsers.add_parser('restart', help='Restart scheduler daemon')
    parser_restart.set_defaults(func=cmd_restart)
    
    # Status command
    parser_status = subparsers.add_parser('status', help='Show scheduler status')
    parser_status.add_argument('--verbose', '-v', action='store_true', help='Show recent log entries')
    parser_status.set_defaults(func=cmd_status)
    
    # List jobs command
    parser_list_jobs = subparsers.add_parser('list-jobs', help='List scheduled jobs')
    parser_list_jobs.set_defaults(func=cmd_list_jobs)
    
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
