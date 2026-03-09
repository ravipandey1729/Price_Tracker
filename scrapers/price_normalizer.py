"""
Price Normalizer Utility

Parses and normalizes prices from different formats.
Handles various price representations like:
- "$19.99", "$1,299.99"
- "€19,99", "19,99 EUR"
- "USD 19.99", "19.99 USD"
- "£19.99", "¥1999"

Usage:
    from scrapers.price_normalizer import parse_price, normalize_price
    
    price, currency = parse_price("$1,299.99")
    # price = 1299.99, currency = "USD"
    
    usd_price = normalize_price(19.99, "EUR")
    # Converts EUR to USD (if exchange rates available)
"""

import re
from typing import Tuple, Optional
from decimal import Decimal, InvalidOperation

from utils.logging_config import get_logger


logger = get_logger(__name__)


# ============================================================================
# CURRENCY SYMBOLS AND CODES
# ============================================================================

CURRENCY_SYMBOLS = {
    '$': 'USD',
    '€': 'EUR',
    '£': 'GBP',
    '¥': 'JPY',
    '₹': 'INR',
    '₽': 'RUB',
    'C$': 'CAD',
    'A$': 'AUD',
    'R$': 'BRL',
    '₪': 'ILS',
    '₩': 'KRW',
    '฿': 'THB',
    '₱': 'PHP',
    'zł': 'PLN',
    'kr': 'SEK',  # Could also be NOK or DKK
    'CHF': 'CHF',
}

# Common currency codes
CURRENCY_CODES = [
    'USD', 'EUR', 'GBP', 'JPY', 'INR', 'CNY', 'CAD', 'AUD',
    'CHF', 'SEK', 'NOK', 'DKK', 'NZD', 'SGD', 'HKD', 'KRW',
    'MXN', 'BRL', 'ZAR', 'RUB', 'TRY', 'THB', 'IDR', 'MYR',
    'PHP', 'PLN', 'CZK', 'HUF', 'ILS', 'CLP', 'AED'
]

# Default currency if none detected
DEFAULT_CURRENCY = 'USD'


# ============================================================================
# PRICE PARSING FUNCTIONS
# ============================================================================

def parse_price(price_text: str) ->Tuple[Optional[float], str]:
    """
    Parse price text and extract numeric value and currency.
    
    Handles various formats:
    - "$19.99" → (19.99, "USD")
    - "1,299.99 USD" → (1299.99, "USD")
    - "€19,99" → (19.99, "EUR")
    - "Price: $1,299.99" → (1299.99, "USD")
    
    Args:
        price_text: Raw price string from website
    
    Returns:
        Tuple of (price_float, currency_code)
        Returns (None, DEFAULT_CURRENCY) if parsing fails
    
    Examples:
        >>> parse_price("$19.99")
        (19.99, 'USD')
        >>> parse_price("€1.299,99")
        (1299.99, 'EUR')
        >>> parse_price("Price: USD 1,299.99")
        (1299.99, 'USD')
    """
    if not price_text or not isinstance(price_text, str):
        logger.warning(f"Invalid price text: {price_text}")
        return None, DEFAULT_CURRENCY
    
    # Clean the input
    price_text = price_text.strip()
    original_text = price_text
    
    # Extract currency
    currency = extract_currency(price_text)
    
    try:
        # Extract numeric value
        price = extract_price_value(price_text)
        
        if price is not None:
            logger.debug(f"Parsed '{original_text}' → {price} {currency}")
            return price, currency
        else:
            logger.warning(f"Could not extract price from: {original_text}")
            return None, currency
            
    except Exception as e:
        logger.error(f"Error parsing price '{original_text}': {e}")
        return None, currency


def extract_currency(text: str) -> str:
    """
    Extract currency code from price text.
    
    Args:
        text: Price text possibly containing currency symbol or code
    
    Returns:
        Currency code (e.g., "USD", "EUR")
    """
    text = text.upper()
    
    # Check for currency codes (USD, EUR, etc.)
    for code in CURRENCY_CODES:
        if code in text:
            return code
    
    # Check for currency symbols
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    
    # Default to USD
    logger.debug(f"No currency found in '{text}', defaulting to {DEFAULT_CURRENCY}")
    return DEFAULT_CURRENCY


def extract_price_value(text: str) -> Optional[float]:
    """
    Extract numeric price value from text.
    
    Handles:
    - Thousands separators: 1,299.99 or 1.299,99
    - Decimal points: 19.99 or 19,99
    - Multiple numbers: "Was $29.99, now $19.99" → takes last one
    - Extra text: "Price: $19.99 each" → 19.99
    
    Args:
        text: Text containing price
    
    Returns:
        Float price value, or None if not found
    """
    # Remove currency symbols and codes
    for symbol in CURRENCY_SYMBOLS.keys():
        text = text.replace(symbol, '')
    for code in CURRENCY_CODES:
        text = text.replace(code, '')
    
    # Remove common words
    text = re.sub(r'\b(price|was|now|from|to|each|only|just|save)\b', '', text, flags=re.IGNORECASE)
    
    # Find all number-like patterns
    # Matches: "1,299.99" or "1.299,99" or "19.99" or "1999"
    pattern = r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?|\d+(?:[,\.]\d{2})?)'
    matches = re.findall(pattern, text)
    
    if not matches:
        return None
    
    # Take the last match (often "was $X, now $Y" → we want Y)
    price_str = matches[-1]
    
    # Normalize decimal separator
    # European format: 1.299,99 → dots are thousands, comma is decimal
    # US format: 1,299.99 → commas are thousands, dot is decimal
    
    if ',' in price_str and '.' in price_str:
        # Has both separators
        comma_pos = price_str.rfind(',')
        dot_pos = price_str.rfind('.')
        
        if dot_pos > comma_pos:
            # US format: 1,299.99
            price_str = price_str.replace(',', '')
        else:
            # European format: 1.299,99
            price_str = price_str.replace('.', '').replace(',', '.')
    
    elif ',' in price_str:
        # Only comma - could be thousands or decimal
        parts = price_str.split(',')
        if len(parts[-1]) == 2:
            # Last part has 2 digits → decimal (19,99)
            price_str = price_str.replace(',', '.')
        else:
            # Thousands separator (1,299)
            price_str = price_str.replace(',', '')
    
    # Remove any remaining non-numeric characters except decimal point
    price_str = re.sub(r'[^\d.]', '', price_str)
    
    # Convert to float
    try:
        price = float(price_str)
        return price
    except (ValueError, InvalidOperation):
        logger.warning(f"Could not convert to float: {price_str}")
        return None


# ============================================================================
# CURRENCY CONVERSION
# ============================================================================

# Static exchange rates (for demo - in production, fetch from API)
EXCHANGE_RATES = {
    'USD': 1.0,
    'EUR': 0.92,
    'GBP': 0.79,
    'JPY': 149.50,
    'INR': 83.12,
    'CAD': 1.36,
    'AUD': 1.53,
    'CHF': 0.88,
}


def normalize_price(price: float, from_currency: str, to_currency: str = 'USD') -> float:
    """
    Convert price from one currency to another.
    
    Args:
        price: Price amount
        from_currency: Source currency code
        to_currency: Target currency code (default: USD)
    
    Returns:
        Converted price
    
    Examples:
        >>> normalize_price(100, 'EUR', 'USD')
        108.70  # Approximate
    """
    if from_currency == to_currency:
        return price
    
    # Get exchange rates
    from_rate = EXCHANGE_RATES.get(from_currency)
    to_rate = EXCHANGE_RATES.get(to_currency)
    
    if from_rate is None or to_rate is None:
        logger.warning(
            f"Exchange rate not available for {from_currency} or {to_currency}, "
            f"returning original price"
        )
        return price
    
    # Convert to USD first, then to target currency
    usd_price = price / from_rate
    converted_price = usd_price * to_rate
    
    return round(converted_price, 2)


# ============================================================================
# VALIDATION
# ============================================================================

def is_valid_price(price: Optional[float], min_price: float = 0.01, max_price: float = 1000000) -> bool:
    """
    Validate that price is reasonable.
    
    Args:
        price: Price to validate
        min_price: Minimum acceptable price
        max_price: Maximum acceptable price
    
    Returns:
        True if price is valid, False otherwise
    """
    if price is None:
        return False
    
    if not isinstance(price, (int, float)):
        return False
    
    if price < min_price or price > max_price:
        logger.warning(f"Price {price} outside valid range [{min_price}, {max_price}]")
        return False
    
    return True


def detect_outlier(price: float, historical_prices: list[float], threshold: float = 0.5) -> bool:
    """
    Detect if price is an outlier compared to historical data.
    
    Args:
        price: Current price
        historical_prices: List of previous prices
        threshold: Percentage threshold (0.5 = 50% difference)
    
    Returns:
        True if price is likely an outlier (parsing error)
    """
    if not historical_prices:
        return False
    
    avg_price = sum(historical_prices) / len(historical_prices)
    
    if avg_price == 0:
        return False
    
    percentage_diff = abs(price - avg_price) / avg_price
    
    if percentage_diff > threshold:
        logger.warning(
            f"Potential outlier: {price} vs avg {avg_price:.2f} "
            f"({percentage_diff*100:.1f}% difference)"
        )
        return True
    
    return False


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test price parsing with various formats.
    Run: python -m scrapers.price_normalizer
    """
    test_cases = [
        "$19.99",
        "€19,99",
        "£1,299.99",
        "USD 1,299.99",
        "Price: $19.99",
        "Was $29.99, now $19.99",
        "1.299,99 EUR",
        "¥1999",
        "₹1,299.00",
        "$1,299",
        "19.99",
        "Invalid text",
    ]
    
    print("Testing Price Parser")
    print("=" * 60)
    
    for test in test_cases:
        price, currency = parse_price(test)
        print(f"{test:25s} → {price:10} {currency}")
    
    print("\n" + "=" * 60)
    print("✓ Price parser test complete")
