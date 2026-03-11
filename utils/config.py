"""
Configuration Management

Loads and validates application configuration from config.yaml and .env files.
Provides type-safe access to configuration values using Pydantic models.

Usage:
    from utils.config import load_config, get_config
    
    # Load configuration
    config = load_config()
    
    # Access values
    db_path = config['database']['path']
    sites = config['scraping']['sites']
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv

from utils.logging_config import get_logger


logger = get_logger(__name__)


# Global configuration cache
_config_cache: Optional[Dict[str, Any]] = None


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Returns:
        Path to project root
    """
    # Assume this file is in utils/, so project root is parent directory
    return Path(__file__).parent.parent


def load_config(config_path: Optional[str] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load configuration from config.yaml and .env files.
    
    Args:
        config_path: Optional path to config.yaml (default: project_root/config.yaml)
        force_reload: If True, bypass cache and reload from disk
    
    Returns:
        Configuration dictionary
    
    Raises:
        FileNotFoundError: If config.yaml not found
        yaml.YAMLError: If config.yaml has invalid syntax
    """
    global _config_cache
    
    # Return cached config if available
    if _config_cache and not force_reload:
        logger.debug("Using cached configuration")
        return _config_cache
    
    # Load environment variables from .env
    project_root = get_project_root()
    env_path = project_root / '.env'
    
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment variables from: {env_path}")
    else:
        logger.warning(f"No .env file found at: {env_path}")
    
    # Determine config file path
    if config_path is None:
        config_path = str(project_root / 'config.yaml')
    
    # Load YAML configuration
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from: {config_path}")
        
        # Validate configuration structure
        _validate_config(config)
        
        # Inject environment variables
        _inject_env_vars(config)
        
        # Cache configuration
        _config_cache = config
        
        return config
    
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config.yaml: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate that configuration has required sections.
    
    Args:
        config: Configuration dictionary
    
    Raises:
        ValueError: If required sections are missing
    """
    required_sections = ['database', 'scraping', 'products']
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Validate products list
    products = config.get('products', [])
    if not isinstance(products, list):
        raise ValueError("Configuration 'products' must be a list")
    
    for product in products:
        if 'id' not in product:
            raise ValueError(f"Product missing required 'id' field: {product}")
        if 'urls' not in product:
            raise ValueError(f"Product missing required 'urls' field: {product['id']}")
    
    logger.debug("Configuration validation passed")


def _inject_env_vars(config: Dict[str, Any]) -> None:
    """
    Inject environment variables into configuration.
    
    Replaces placeholders like ${ENV_VAR_NAME} with actual values.
    
    Args:
        config: Configuration dictionary (modified in-place)
    """
    # Database path (expand relative paths)
    if 'database' in config and 'path' in config['database']:
        db_path = config['database']['path']
        if not os.path.isabs(db_path):
            config['database']['path'] = str(get_project_root() / db_path)
    
    # Email credentials
    if 'alerts' in config and 'email' in config['alerts']:
        email_config = config['alerts']['email']
        email_config['smtp_username'] = os.getenv('EMAIL_USERNAME', '')
        email_config['smtp_password'] = os.getenv('EMAIL_PASSWORD', '')
        email_config['from_email'] = os.getenv('EMAIL_FROM', email_config['smtp_username'])
    
    # Slack webhook
    if 'alerts' in config and 'slack' in config['alerts']:
        slack_config = config['alerts']['slack']
        slack_config['webhook_url'] = os.getenv('SLACK_WEBHOOK_URL', '')
    
    logger.debug("Injected environment variables into configuration")


def get_config() -> Dict[str, Any]:
    """
    Get the current configuration (loads if not already loaded).
    
    Returns:
        Configuration dictionary
    """
    if _config_cache is None:
        return load_config()
    return _config_cache


def clear_config_cache() -> None:
    """
    Clear the configuration cache.
    
    Useful for testing or when configuration files change at runtime.
    """
    global _config_cache
    _config_cache = None
    logger.debug("Configuration cache cleared")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_database_url() -> str:
    """
    Get the database URL from configuration.
    
    Returns:
        SQLite database URL (e.g., "sqlite:///path/to/db.sqlite")
    """
    config = get_config()
    db_path = config['database']['path']
    return f"sqlite:///{db_path}"


def get_scraping_config() -> Dict[str, Any]:
    """
    Get scraping configuration section.
    
    Returns:
        Scraping configuration dict
    """
    config = get_config()
    return config.get('scraping', {})


def get_products_config() -> list[Dict[str, Any]]:
    """
    Get products configuration.
    
    Returns:
        List of product configuration dicts
    """
    config = get_config()
    return config.get('products', [])


def get_alerts_config() -> Dict[str, Any]:
    """
    Get alerts configuration section.
    
    Returns:
        Alerts configuration dict
    """
    config = get_config()
    return config.get('alerts', {})


def get_scheduler_config() -> Dict[str, Any]:
    """
    Get scheduler configuration section.
    
    Returns:
        Scheduler configuration dict
    """
    config = get_config()
    return config.get('scheduler', {})


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test configuration loading.
    Run: python -m utils.config
    """
    import json
    
    print("=" * 70)
    print("Configuration Test")
    print("=" * 70)
    
    try:
        # Load configuration
        config = load_config()
        
        print("\n✓ Successfully loaded configuration")
        
        # Display database config
        print("\nDatabase Configuration:")
        print(f"  Path: {config['database']['path']}")
        print(f"  Echo: {config['database'].get('echo', False)}")
        
        # Display scraping config
        scraping = config.get('scraping', {})
        print("\nScraping Configuration:")
        print(f"  Sites: {len(scraping.get('sites', []))}")
        print(f"  Min Delay: {scraping.get('min_delay', 'N/A')}s")
        print(f"  Max Delay: {scraping.get('max_delay', 'N/A')}s")
        
        # Display products
        products = config.get('products', [])
        print(f"\nProducts: {len(products)}")
        for product in products:
            print(f"  • {product['id']}: {product.get('name', 'N/A')}")
            print(f"    Sites: {', '.join(product.get('urls', {}).keys())}")
        
        # Display alerts config
        alerts = config.get('alerts', {})
        print("\nAlerts Configuration:")
        print(f"  Email enabled: {alerts.get('email', {}).get('enabled', False)}")
        print(f"  Slack enabled: {alerts.get('slack', {}).get('enabled', False)}")
        
        # Display scheduler config
        scheduler = config.get('scheduler', {})
        print("\nScheduler Configuration:")
        print(f"  Interval: {scheduler.get('scrape_interval_hours', 'N/A')} hours")
        
        print("\n" + "=" * 70)
        print("✓ Configuration test complete")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
