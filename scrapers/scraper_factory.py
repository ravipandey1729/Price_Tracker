"""
Scraper Factory

Factory pattern for creating scraper instances.
Maps site names to their corresponding scraper classes.

This makes it easy to add new scrapers without modifying orchestration code:
1. Create new scraper class (inherit from BaseScraper)
2. Register it in SCRAPER_REGISTRY below
3. Add site configuration to config.yaml

Usage:
    from scrapers.scraper_factory import get_scraper
    
    scraper = get_scraper("Amazon")
    data = scraper.scrape(url="https://amazon.com/...")
"""

from typing import Dict, Type, Optional

from scrapers.base_scraper import BaseScraper
from scrapers.amazon_scraper import AmazonScraper
from scrapers.ebay_scraper import EbayScraper
from utils.logging_config import get_logger


logger = get_logger(__name__)


# ============================================================================
# SCRAPER REGISTRY
# ============================================================================

# Map site names (from config) to scraper classes
SCRAPER_REGISTRY: Dict[str, Type[BaseScraper]] = {
    "Amazon": AmazonScraper,
    "eBay": EbayScraper,
    # Add more scrapers here as you create them:
    # "Walmart": WalmartScraper,
    # "BestBuy": BestBuyScraper,
}


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def get_scraper(site_name: str) -> Optional[BaseScraper]:
    """
    Get a scraper instance for the specified site.
    
    Args:
        site_name: Name of the site (must match config.yaml)
    
    Returns:
        Scraper instance, or None if site not supported
    
    Example:
        >>> scraper = get_scraper("Amazon")
        >>> if scraper:
        ...     data = scraper.scrape("https://amazon.com/...") 
    """
    scraper_class = SCRAPER_REGISTRY.get(site_name)
    
    if not scraper_class:
        logger.warning(
            f"No scraper found for site: {site_name}. "
            f"Available sites: {list(SCRAPER_REGISTRY.keys())}"
        )
        return None
    
    try:
        return scraper_class()
    except Exception as e:
        logger.error(f"Failed to instantiate {site_name} scraper: {e}")
        return None


def get_available_sites() -> list[str]:
    """
    Get list of all supported site names.
    
    Returns:
        List of site names that have scrapers
    
    Example:
        >>> sites = get_available_sites()
        >>> print(f"Supported sites: {', '.join(sites)}")
    """
    return list(SCRAPER_REGISTRY.keys())


def is_site_supported(site_name: str) -> bool:
    """
    Check if a site has a scraper available.
    
    Args:
        site_name: Name of the site to check
    
    Returns:
        True if scraper exists, False otherwise
    
    Example:
        >>> if is_site_supported("Amazon"):
        ...     scraper = get_scraper("Amazon")
    """
    return site_name in SCRAPER_REGISTRY


def register_scraper(site_name: str, scraper_class: Type[BaseScraper]) -> None:
    """
    Dynamically register a new scraper.
    
    Useful for plugins or dynamically loaded scrapers.
    
    Args:
        site_name: Name to register the scraper under
        scraper_class: Scraper class (must inherit from BaseScraper)
    
    Raises:
        ValueError: If scraper_class doesn't inherit from BaseScraper
    
    Example:
        >>> class MyCustomScraper(BaseScraper):
        ...     pass
        >>> register_scraper("MyStore", MyCustomScraper)
    """
    if not issubclass(scraper_class, BaseScraper):
        raise ValueError(
            f"{scraper_class.__name__} must inherit from BaseScraper"
        )
    
    SCRAPER_REGISTRY[site_name] = scraper_class
    logger.info(f"Registered scraper for: {site_name}")


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test scraper factory.
    Run: python -m scrapers.scraper_factory
    """
    print("=" * 70)
    print("Scraper Factory Test")
    print("=" * 70)
    
    # List available scrapers
    sites = get_available_sites()
    print(f"\nSupported sites ({len(sites)}):")
    for site in sites:
        print(f"  • {site}")
    
    print("\nTesting scraper instantiation:")
    
    # Test each scraper
    for site_name in sites:
        print(f"\n  {site_name}:")
        print(f"    - Supported: {is_site_supported(site_name)}")
        
        scraper = get_scraper(site_name)
        if scraper:
            print(f"    - Instance: {scraper.__class__.__name__}")
            print(f"    - Min delay: {scraper.min_delay}s")
            print(f"    - Max delay: {scraper.max_delay}s")
            print("    - Status: ✓ OK")
        else:
            print("    - Status: ✗ FAILED")
    
    # Test unsupported site
    print("\n  Testing unsupported site:")
    unsupported = get_scraper("NonExistentStore")
    print(f"    - Result: {'✗ Correctly returned None' if unsupported is None else '✓ Unexpected result'}")
    
    print("\n" + "=" * 70)
    print("✓ Factory test complete")
    print("=" * 70)
