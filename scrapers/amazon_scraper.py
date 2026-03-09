"""
Amazon Scraper

Site-specific scraper for Amazon.com
Extracts product information using Amazon's HTML structure.

Note: Amazon actively works to prevent scraping. This is for educational purposes
and personal price tracking only. For production use, consider Amazon's official
Product Advertising API.

Usage:
    from scrapers.amazon_scraper import AmazonScraper
    
    scraper = AmazonScraper()
    data = scraper.scrape("https://www.amazon.com/dp/B09XS7JWHH")
    print(f"Product: {data.product_name}, Price: {data.price}")
"""

from datetime import datetime
from typing import Optional

from scrapers.base_scraper import BaseScraper, ScrapedData
from scrapers.price_normalizer import parse_price, is_valid_price
from utils.logging_config import get_logger


logger = get_logger(__name__)


class AmazonScraper(BaseScraper):
    """
    Scraper for Amazon.com product pages.
    
    Handles various Amazon page layouts and price locations.
    Uses multiple selector fallbacks since Amazon frequently changes their HTML.
    """
    
    def __init__(self):
        """Initialize Amazon scraper with site-specific settings."""
        super().__init__(
            site_name="Amazon",
            min_delay=3.0,  # Amazon is strict about rate limiting
            max_delay=6.0,
            timeout=30,
            max_retries=3
        )
        
        # CSS Selectors for Amazon (with fallbacks)
        self.selectors = {
            'product_name': [
                '#productTitle',
                'h1.product-title',
                'h1#title',
            ],
            'price': [
                'span.a-price.a-text-price.a-size-medium.apexPriceToPay span.a-offscreen',
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                'span.a-price span.a-offscreen',
                '.a-price .a-offscreen',
                'span.priceToPay span.a-offscreen',
            ],
            'availability': [
                '#availability span',
                '#availability',
                'div#availability',
            ],
            'image': [
                '#landingImage',
                '#imgBlkFront',
                'img.a-dynamic-image',
            ],
            'rating': [
                'span.a-icon-alt',
                '#acrPopover',
            ],
            'review_count': [
                '#acrCustomerReviewText',
                'span#acrCustomerReviewText',
            ]
        }
    
    
    def parse_html(self, html: str, url: str) -> ScrapedData:
        """
        Parse Amazon product page HTML and extract data.
        
        Args:
            html: Raw HTML content from Amazon
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
            raise ValueError("Could not extract product name from Amazon page")
        
        # Clean up product name (Amazon adds extra spaces)
        product_name = ' '.join(product_name.split())
        
        # Extract price
        raw_price_text = self.extract_text_with_fallback(
            soup,
            self.selectors['price']
        )
        
        if not raw_price_text:
            raise ValueError("Could not extract price from Amazon page")
        
        # Parse price
        price, currency = parse_price(raw_price_text)
        
        if price is None or not is_valid_price(price):
            raise ValueError(f"Invalid price extracted: {raw_price_text}")
        
        # Extract availability
        availability_text = self.extract_text_with_fallback(
            soup,
            self.selectors['availability'],
            default="Unknown"
        )
        
        # Determine if in stock
        in_stock = self._parse_availability(availability_text)
        
        # Optional: Extract image URL
        image_element = soup.select_one(self.selectors['image'][0])
        image_url = image_element.get('src') if image_element else None
        
        # Optional: Extract rating
        rating = self._extract_rating(soup)
        
        # Optional: Extract review count
        review_count = self._extract_review_count(soup)
        
        # Create and return scraped data
        return ScrapedData(
            product_name=product_name,
            price=price,
            currency=currency,
            raw_price_text=raw_price_text,
            in_stock=in_stock,
            availability_text=availability_text,
            source_url=url,
            scraped_at=datetime.utcnow(),
            product_image_url=image_url,
            seller_name="Amazon",
            rating=rating,
            review_count=review_count
        )
    
    
    def _parse_availability(self, availability_text: str) -> bool:
        """
        Determine if product is in stock from availability text.
        
        Args:
            availability_text: Text from availability section
        
        Returns:
            True if in stock, False otherwise
        """
        availability_lower = availability_text.lower()
        
        # Check for out of stock indicators
        out_of_stock_phrases = [
            'out of stock',
            'unavailable',
            'currently unavailable',
            'not available',
            'temporarily out of stock'
        ]
        
        for phrase in out_of_stock_phrases:
            if phrase in availability_lower:
                return False
        
        # Check for in stock indicators
        in_stock_phrases = [
            'in stock',
            'available',
            'only',
            'left in stock'
        ]
        
        for phrase in in_stock_phrases:
            if phrase in availability_lower:
                return True
        
        # Default to True if unclear
        return True
    
    
    def _extract_rating(self, soup) -> Optional[float]:
        """
        Extract product rating (e.g., 4.5 out of 5 stars).
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Rating as float, or None if not found
        """
        rating_text = self.extract_text_with_fallback(
            soup,
            self.selectors['rating']
        )
        
        if not rating_text:
            return None
        
        # Extract number from text like "4.5 out of 5 stars"
        import re
        match = re.search(r'(\d+\.?\d*)\s*out of', rating_text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        
        return None
    
    
    def _extract_review_count(self, soup) -> Optional[int]:
        """
        Extract number of customer reviews.
        
        Args:
            soup: BeautifulSoup object
        
        Returns:
            Review count as integer, or None if not found
        """
        review_text = self.extract_text_with_fallback(
            soup,
            self.selectors['review_count']
        )
        
        if not review_text:
            return None
        
        # Extract number from text like "1,234 ratings"
        import re
        # Remove commas and extract digits
        numbers = re.findall(r'[\d,]+', review_text)
        if numbers:
            try:
                return int(numbers[0].replace(',', ''))
            except ValueError:
                return None
        
        return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def scrape_amazon_product(url: str, product_id: Optional[str] = None) -> Optional[ScrapedData]:
    """
    Convenience function to scrape a single Amazon product.
    
    Args:
        url: Amazon product URL
        product_id: Optional product identifier for logging
    
    Returns:
        ScrapedData if successful, None if failed
    
    Example:
        >>> data = scrape_amazon_product("https://www.amazon.com/dp/B09XS7JWHH")
        >>> if data:
        ...     print(f"{data.product_name}: ${data.price}")
    """
    with AmazonScraper() as scraper:
        return scraper.scrape(url, product_id)


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test Amazon scraper with example URL.
    Run: python -m scrapers.amazon_scraper
    """
    import sys
    
    print("=" * 70)
    print("Amazon Scraper Test")
    print("=" * 70)
    
    # Example Amazon product URL (replace with actual product)
    test_url = "https://www.amazon.com/dp/B09XS7JWHH"
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    
    print(f"\nScraping: {test_url}\n")
    
    try:
        data = scrape_amazon_product(test_url, "test_product")
        
        if data:
            print("✓ Successfully scraped Amazon product")
            print(f"\nProduct Name: {data.product_name}")
            print(f"Price: {data.currency} {data.price}")
            print(f"Raw Price Text: {data.raw_price_text}")
            print(f"In Stock: {data.in_stock}")
            print(f"Availability: {data.availability_text}")
            if data.rating:
                print(f"Rating: {data.rating}/5")
            if data.review_count:
                print(f"Reviews: {data.review_count:,}")
            print(f"Scraped At: {data.scraped_at}")
        else:
            print("✗ Failed to scrape Amazon product")
            sys.exit(1)
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✓ Test complete")
    print("=" * 70)
