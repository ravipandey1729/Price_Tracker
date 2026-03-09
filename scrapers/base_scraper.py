"""
Base Scraper Class

Abstract base class for all site-specific scrapers.
Provides common functionality:
- HTTP requests with retry logic
- User-Agent rotation
- Rate limiting / delays
- Error handling
- HTML storage on failures

All site-specific scrapers (Amazon, eBay, etc.) should inherit from this class.

Usage:
    class AmazonScraper(BaseScraper):
        def __init__(self):
            super().__init__(site_name="Amazon")
        
        def scrape(self, url: str) -> ScrapedData:
            html = self.fetch_html(url)
            return self.parse_html(html)
"""

import time
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from utils.logging_config import get_logger, save_failed_html


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ScrapedData:
    """
    Data structure for scraped product information.
    Returned by all scrapers for consistency.
    """
    product_name: str
    price: float
    currency: str
    raw_price_text: str
    in_stock: bool
    availability_text: str
    source_url: str
    scraped_at: datetime
    
    # Optional fields
    product_image_url: Optional[str] = None
    seller_name: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None


# ============================================================================
# BASE SCRAPER CLASS
# ============================================================================

class BaseScraper(ABC):
    """
    Abstract base class for all web scrapers.
    
    Handles common scraping tasks:
    - HTTP requests with error handling
    - User-Agent rotation to avoid detection
    - Rate limiting (delays between requests)
    - Retry logic with exponential backoff
    - HTML storage for debugging failed scrapes
    """
    
    def __init__(
        self,
        site_name: str,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize base scraper.
        
        Args:
            site_name: Name of the site (e.g., "Amazon", "eBay")
            min_delay: Minimum delay between requests (seconds)
            max_delay: Maximum delay between requests (seconds)
            timeout: HTTP request timeout (seconds)
            max_retries: Maximum number of retry attempts
        """
        self.site_name = site_name
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Setup logger for this scraper
        self.logger = get_logger(f"scrapers.{site_name.lower()}")
        
        # User-Agent rotation
        self.ua = UserAgent()
        
        # Session for connection pooling
        self.session = requests.Session()
        
        # Last request time (for rate limiting)
        self.last_request_time = 0
        
        self.logger.info(f"Initialized {site_name} scraper")
    
    
    # ========================================================================
    # ABSTRACT METHODS (must be implemented by subclasses)
    # ========================================================================
    
    @abstractmethod
    def parse_html(self, html: str, url: str) -> ScrapedData:
        """
        Parse HTML and extract product data.
        Must be implemented by each site-specific scraper.
        
        Args:
            html: Raw HTML content
            url: Original URL being scraped
        
        Returns:
            ScrapedData object with extracted information
        
        Raises:
            ValueError: If required data cannot be extracted
        """
        pass
    
    
    # ========================================================================
    # HTTP REQUEST METHODS
    # ========================================================================
    
    def fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL with retry logic.
        
        Args:
            url: URL to fetch
        
        Returns:
            Raw HTML content as string
        
        Raises:
            requests.RequestException: If all retry attempts fail
        """
        for attempt in range(self.max_retries):
            try:
                # Rate limiting: ensure minimum delay between requests
                self._enforce_rate_limit()
                
                # Make request
                self.logger.info(f"Fetching: {url} (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    timeout=self.timeout
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Success!
                self.logger.info(f"Successfully fetched {url} ({len(response.text)} bytes)")
                return response.text
                
            except requests.RequestException as e:
                self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                # If this was the last attempt, raise the error
                if attempt == self.max_retries - 1:
                    self.logger.error(f"All retry attempts failed for {url}")
                    raise
                
                # Exponential backoff: wait longer after each failure
                backoff_time = 2 ** attempt  # 1s, 2s, 4s, 8s...
                self.logger.info(f"Waiting {backoff_time}s before retry...")
                time.sleep(backoff_time)
        
        # Should never reach here due to raise in loop
        raise requests.RequestException("All retry attempts exhausted")
    
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Generate HTTP headers with rotating User-Agent.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    
    def _enforce_rate_limit(self):
        """
        Ensure minimum delay between requests.
        Sleeps if necessary to avoid overwhelming the server.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_delay:
            # Need to wait longer
            sleep_time = random.uniform(self.min_delay, self.max_delay)
            self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    
    # ========================================================================
    # SCRAPING METHODS
    # ========================================================================
    
    def scrape(self, url: str, product_id: Optional[str] = None) -> Optional[ScrapedData]:
        """
        Main scraping method. Fetches HTML and parses it.
        
        Args:
            url: URL to scrape
            product_id: Optional product identifier (for logging)
        
        Returns:
            ScrapedData object if successful, None if failed
        """
        try:
            # Fetch HTML
            html = self.fetch_html(url)
            
            # Parse HTML
            data = self.parse_html(html, url)
            
            self.logger.info(
                f"Successfully scraped {product_id or 'product'}: "
                f"{data.product_name} - {data.currency} {data.price}"
            )
            
            return data
            
        except requests.RequestException as e:
            self.logger.error(f"Network error scraping {url}: {e}")
            return None
            
        except ValueError as e:
            # Parsing error - save HTML for debugging
            self.logger.error(f"Parse error for {url}: {e}")
            
            try:
                html = self.fetch_html(url)
                save_failed_html(self.site_name, product_id or "unknown", html)
            except:
                pass  # Don't fail if we can't save debug HTML
            
            return None
            
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {url}: {e}", exc_info=True)
            return None
    
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_soup(self, html: str) -> BeautifulSoup:
        """
        Parse HTML into BeautifulSoup object.
        
        Args:
            html: Raw HTML string
        
        Returns:
            BeautifulSoup object for parsing
        """
        return BeautifulSoup(html, 'lxml')
    
    
    def extract_text(self, soup: BeautifulSoup, selector: str, default: str = "") -> str:
        """
        Extract text from HTML using CSS selector.
        
        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            default: Default value if not found
        
        Returns:
            Extracted text, stripped of whitespace
        """
        element = soup.select_one(selector)
        if element:
            return element.get_text(strip=True)
        return default
    
    
    def extract_text_with_fallback(
        self,
        soup: BeautifulSoup,
        selectors: list[str],
        default: str = ""
    ) -> str:
        """
        Try multiple selectors until one works.
        Useful when sites change their HTML structure.
        
        Args:
            soup: BeautifulSoup object
            selectors: List of CSS selectors to try in order
            default: Default value if none found
        
        Returns:
            Extracted text from first matching selector
        """
        for selector in selectors:
            text = self.extract_text(soup, selector)
            if text:
                return text
        
        self.logger.warning(f"No fallback selector matched: {selectors}")
        return default
    
    
    def close(self):
        """
        Close the HTTP session.
        Call this when done scraping to release resources.
        """
        self.session.close()
        self.logger.info(f"Closed {self.site_name} scraper session")
    
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically closes session."""
        self.close()
