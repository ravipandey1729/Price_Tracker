"""
Logging Configuration for Price Tracker

This module sets up centralized logging with:
- Console output (color-coded by severity)
- Rotating file handlers (automatically creates new files when full)
- Separate log files for different components
- Structured log format with timestamps

Usage:
    from utils.logging_config import get_logger
    
    logger = get_logger(__name__)
    logger.info("Starting scraper...")
    logger.error("Failed to connect", exc_info=True)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s | %(name)-25s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log file settings
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5  # Keep 5 old log files

# Log files for different components
LOG_FILES = {
    "main": "price_tracker.log",
    "scraper": "scraper_errors.log",
    "alerts": "alerts.log",
    "scheduler": "scheduler.log",
}

# Default log level
DEFAULT_LEVEL = logging.INFO


# ============================================================================
# COLOR CODES (for console output)
# ============================================================================

class LogColors:
    """ANSI color codes for console output"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


# ============================================================================
# CUSTOM FORMATTER
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to console output based on log level.
    """
    
    COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.CYAN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.MAGENTA,
    }
    
    def format(self, record):
        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.COLORS:
            color = self.COLORS[record.levelno]
            record.levelname = f"{color}{levelname}{LogColors.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Reset levelname (so it doesn't affect other handlers)
        record.levelname = levelname
        
        return result


# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

def ensure_log_directory():
    """
    Create the logs directory if it doesn't exist.
    """
    Path(LOG_DIR).mkdir(exist_ok=True)
    
    # Also create subdirectory for failed scrapes
    Path(os.path.join(LOG_DIR, "failed_scrapes")).mkdir(exist_ok=True)


def setup_logging(
    level: int = DEFAULT_LEVEL,
    console_output: bool = True,
    file_output: bool = True,
    log_file: str = "price_tracker.log"
) -> logging.Logger:
    """
    Setup logging configuration for the entire application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Whether to output logs to console
        file_output: Whether to output logs to file
        log_file: Name of the main log file
    
    Returns:
        Root logger instance
    """
    # Ensure log directory exists
    ensure_log_directory()
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Console handler (with colors)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = ColoredFormatter(LOG_FORMAT, DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler (with rotation)
    if file_output:
        log_path = os.path.join(LOG_DIR, log_file)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_FILE_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    
    return root_logger


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        log_file: Optional separate log file for this logger
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Add separate file handler if specified
    if log_file:
        ensure_log_directory()
        log_path = os.path.join(LOG_DIR, log_file)
        
        # Check if handler already exists
        for handler in logger.handlers:
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == os.path.abspath(log_path):
                return logger
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_FILE_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def setup_component_loggers():
    """
    Setup separate loggers for different components with their own log files.
    """
    ensure_log_directory()
    
    # Scraper logger
    scraper_logger = get_logger("scrapers", LOG_FILES["scraper"])
    
    # Alerts logger
    alerts_logger = get_logger("alerts", LOG_FILES["alerts"])
    
    # Scheduler logger
    scheduler_logger = get_logger("scheduler", LOG_FILES["scheduler"])
    
    return {
        "scraper": scraper_logger,
        "alerts": alerts_logger,
        "scheduler": scheduler_logger,
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_exception(logger: logging.Logger, message: str, exception: Exception):
    """
    Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        message: Custom error message
        exception: Exception object
    """
    logger.error(f"{message}: {str(exception)}", exc_info=True)


def log_section_separator(logger: logging.Logger, title: str, char: str = "="):
    """
    Log a visual section separator for better readability.
    
    Args:
        logger: Logger instance
        title: Section title
        char: Character to use for separator line
    """
    separator = char * 60
    logger.info(separator)
    logger.info(f" {title}")
    logger.info(separator)


def save_failed_html(site_name: str, product_id: str, html_content: str):
    """
    Save failed HTML content to a file for debugging.
    
    Args:
        site_name: Name of the site that failed
        product_id: Product ID
        html_content: Raw HTML content
    """
    from datetime import datetime
    
    ensure_log_directory()
    failed_dir = os.path.join(LOG_DIR, "failed_scrapes")
    Path(failed_dir).mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{site_name}_{product_id}_{timestamp}.html"
    filepath = os.path.join(failed_dir, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger = get_logger(__name__)
        logger.info(f"Saved failed HTML to: {filepath}")
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to save HTML: {e}")


# ============================================================================
# INITIALIZATION
# ============================================================================

# Setup logging when module is imported
# This ensures logging is ready before any other code runs
setup_logging()


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test the logging configuration.
    Run: python -m utils.logging_config
    """
    print("Testing logging configuration...\n")
    
    # Get a logger
    logger = get_logger(__name__)
    
    # Test different log levels
    log_section_separator(logger, "Testing Log Levels")
    logger.debug("This is a DEBUG message (gray)")
    logger.info("This is an INFO message (cyan)")
    logger.warning("This is a WARNING message (yellow)")
    logger.error("This is an ERROR message (red)")
    logger.critical("This is a CRITICAL message (magenta)")
    
    # Test exception logging
    log_section_separator(logger, "Testing Exception Logging")
    try:
        result = 1 / 0
    except Exception as e:
        log_exception(logger, "Division by zero error", e)
    
    # Test component loggers
    log_section_separator(logger, "Testing Component Loggers")
    loggers = setup_component_loggers()
    loggers["scraper"].info("Scraper log message")
    loggers["alerts"].info("Alert log message")
    loggers["scheduler"].info("Scheduler log message")
    
    print("\n✓ Check the logs/ folder for output files")
    print(f"✓ Main log: {os.path.join(LOG_DIR, LOG_FILES['main'])}")
    print(f"✓ Scraper log: {os.path.join(LOG_DIR, LOG_FILES['scraper'])}")
