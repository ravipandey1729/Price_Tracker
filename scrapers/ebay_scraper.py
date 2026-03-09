"""
eBay Scraper

Site-specific scraper for eBay.com
Extracts product information using eBay's HTML structure.

Note: For commercial use, consider eBay's official Finding API or Browse API.
This scraper is for educational and personal price tracking purposes.

Usage:
    from scrapers.ebay_scraper import EbayScraper
    
    scraper = EbayScraper()
    data = scraper.scrape("https://www.ebay.com/itm/1234567890")
    print(f"Product: {data.product_name}, Price: {data.price}")
"""

from datetime import datetime
from typing import Optional

from scrapers.base_scraper import BaseScraper, ScrapedData
from scrapers.price_normalizer import parse_price, is_valid_price
from utils.logging_config import get_logger


logger = get_logger(__name__)


class EbayScraper(BaseScraper):
    """
    Scraper for eBay.com product pages.
    
    Handles eBay listing pages with multiple price types:
    - Buy It Now prices
    - Auction starting prices
    - Best Offer prices
    """
    
    def __init__(self):
        """Initialize eBay scraper with site-specific settings."""
        super().__init__(
            site_name="eBay",
            min_delay=2.0,
            max_delay=4.0,
            timeout=30,
            max_retries=3
        )
        
        # CSS Selectors for eBay (with fallbacks)
        self.selectors = {
            'product_name': [
                'h1.x-item-title__mainTitle',
                'h1[class*="item-title"]',
                'h1.it-ttl',
            ],
            'price': [
                'div.x-price-primary span.ux-textspans',
                'span.ux-textspans.price',
                'span[itemprop="price"]',
                '.x-price-primary',
                '#prcIsum',
            ],
            'availability': [
                'div.d-quantity__availability',
                'span.qtyTxt',
                '.qty-test',
            ],
            'seller': [
                'div.x-sellercard-atf__info__about-seller a',
                'span.mbg-nw',
                'a.mbg-l-w',
            ],
            'image': [
                'img.ux-image-magnify__image--original',
                'img#icImg',
                'img[itemprop="image"]',
            ],
            'condition': [
                'div.x-item-condition-text span.ux-textspans',
                'div[itemprop="itemCondition"]',
            ]
        }
    
    
    def parse_html(self, html: str, url: str) -> ScrapedData:
        """
        Parse eBay product page HTML and extract data.
        
        Args:
            html: Raw HTML content from eBay
            url: Original product URL
        
        Returns:
            ScrapedData object with extracted information
        
        Raises:
            ValueError: If required data (name or price) cannot be extracted
        """
        soup = self.get_soup(html)
        
        # Extract product name
        product_name = self.extract_text_with_fallback(
            soup,
            self.selectors['product_name']
        )
        
        if not product_name:
            raise ValueError("Could not extract product name from eBay page")
        
        # Clean up product name
        product_name = ' '.join(product_name.split())
        
        # Extract price
        raw_price_text = self.extract_text_with_fallback(
            soup,
            self.selectors['price']
        )
        
        if not raw_price_text:
            raise ValueError("Could not extract price from eBay page")
        
        # Parse price
        price, currency = parse_price(raw_price_text)
        
        if price is None or not is_valid_price(price):
            raise ValueError(f"Invalid price extracted: {raw_price_text}")
        
        # Extract availability
        availability_text = self.extract_text_with_fallback(
            soup,
            self.selectors['availability'],
            default="Check listing"
        )
        
        # Determine if in stock
        in_stock = self._parse_availability(availability_text)
        
        # Optional: Extract seller name
        seller_name = self.extract_text_with_fallback(
            soup,
            self.selectors['seller'],
            default="eBay Seller"
        )
        
        # Optional: Extract image URL
        image_element = soup.select_one(self.selectors['image'][0])
        image_url = image_element.get('src') if image_element else None
        
        # Optional: Extract condition
        condition = self.extract_text_with_fallback(
            soup,
            self.selectors['condition'],
            default="Unknown"
        )
        
        # Create and return scraped data
        return ScrapedData(
            product_name=product_name,
            price=price,
            currency=currency,
            raw_price_text=raw_price_text,
            in_stock=in_stock,
            availability_text=f"{availability_text} - Condition: {condition}",
            source_url=url,
            scraped_at=datetime.utcnow(),
            product_image_url=image_url,
            seller_name=seller_name
        )
    
    
    def _parse_availability(self, availability_text: str) -> bool:
        """
        Determine if product is available from availability text.
        
        Args:
            availability_text: Text from availability section
        
        Returns:
            True if available, False otherwise
        """
        availability_lower = availability_text.lower()
        
        # Check for unavailable indicators
        unavailable_phrases = [
            'no longer available',
            'out of stock',
            'sold out',
            'ended',
        ]
        
        for phrase in unavailable_phrases:
            if phrase in availability_lower:
                return False
        
        # Check for available indicators
        available_phrases = [
            'available',
            'in stock',
            'ready to ship',
            'ships within',
            'last one',
            'limited quantity',
            'more than',
        ]
        
        for phrase in available_phrases:
            if phrase in availability_lower:
                return True
        
        # Default to True if unclear (eBay defaults to available)
        return True


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def scrape_ebay_product(url: str, product_id: Optional[str] = None) -> Optional[ScrapedData]:
    """
    Convenience function to scrape a single eBay product.
    
    Args:
        url: eBay product URL
        product_id: Optional product identifier for logging
    
    Returns:
        ScrapedData if successful, None if failed
    
    Example:
        >>> data = scrape_ebay_product("https://www.ebay.com/itm/1234567890")
        >>> if data:
        ...     print(f"{data.product_name}: ${data.price}")
    """
    with EbayScraper() as scraper:
        return scraper.scrape(url, product_id)


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test eBay scraper with example URL.
    Run: python -m scrapers.ebay_scraper
    """
    import sys
    
    print("=" * 70)
    print("eBay Scraper Test")
    print("=" * 70)
    
    # Example eBay product URL (replace with actual product)
    test_url = "https://www.ebay.com/itm/123456789"
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    print(f"\nScraping: {test_url}\n")
    
    try:
        data = scrape_ebay_product(test_url, "test_product")
        
        if data:
            print("✓ Successfully scraped eBay product")
            print(f"\nProduct Name: {data.product_name}")
            print(f"Price: {data.currency} {data.price}")
            print(f"Raw Price Text: {data.raw_price_text}")
            print(f"In Stock: {data.in_stock}")
            print(f"Availability: {data.availability_text}")
            print(f"Seller: {data.seller_name}")
            print(f"Scraped At: {data.scraped_at}")
        else:
            print("✗ Failed to scrape eBay product")
            sys.exit(1)
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✓ Test complete")
    print("=" * 70)
