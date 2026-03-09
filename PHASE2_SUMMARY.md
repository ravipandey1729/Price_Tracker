# Phase 2 Complete: Web Scraping Infrastructure

## 📋 Summary
Phase 2 adds complete web scraping capabilities to extract product prices from e-commerce sites. The system can scrape multiple sites in parallel, normalize price formats, handle errors gracefully, and store results in the database.

---

## ✅ What Was Built

### 1. **Base Scraper (Abstract Class)**
**File:** `scrapers/base_scraper.py` (10,936 bytes)

**Purpose:** Provides reusable HTTP fetching and HTML parsing logic for all site-specific scrapers.

**Key Features:**
- **HTTP Requests** with retry logic (exponential backoff)
- **Rate Limiting** with random delays to avoid detection
- **User-Agent Rotation** using fake-useragent library
- **Error Handling** with detailed logging
- **Response Caching** saves failed HTML for debugging
- **Context Manager** support for automatic cleanup
- **Abstract Methods** for site-specific parsing

**Example Usage:**
```python
from scrapers.base_scraper import BaseScraper

class MyScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            site_name="MyStore",
            min_delay=2.0,  # Minimum delay between requests
            max_delay=5.0,  # Maximum delay
            timeout=30,     # HTTP timeout
            max_retries=3   # Retry failed requests
        )
    
    def parse_html(self, html: str, url: str) -> ScrapedData:
        soup = self.get_soup(html)
        
        # Extract product name
        name = self.extract_text_with_fallback(soup, ['.product-title', 'h1'])
        
        # Extract price
        price_text = self.extract_text_with_fallback(soup, ['.price', '.cost'])
        price, currency = parse_price(price_text)
        
        return ScrapedData(
            product_name=name,
            price=price,
            currency=currency,
            raw_price_text=price_text,
            in_stock=True,
            source_url=url
        )

# Use it
scraper = MyScraper()
data = scraper.scrape("https://mystore.com/product/123")
print(f"{data.product_name}: ${data.price}")
```

**Retry Logic:**
- Attempt 1: Immediate
- Attempt 2: Wait 2 seconds
- Attempt 3: Wait 4 seconds  
- Attempt 4: Wait 8 seconds

**Why it matters:** When Amazon changes their HTML structure, you only need to update `amazon_scraper.py` selectors. The HTTP logic stays the same.

---

### 2. **Price Normalizer Utility**
**File:** `scrapers/price_normalizer.py` (9,286 bytes)

**Purpose:** Parse and normalize prices from various formats into standard `(float, currency_code)` tuples.

**Handles:**
- **Multiple Formats:**
  - `$19.99` → `(19.99, "USD")`
  - `€19,99` → `(19.99, "EUR")`
  - `1,299.99 USD` → `(1299.99, "USD")`
  - `₹1,99,999.00` → `(199999.0, "INR")`
  - `US$1,234.56` → `(1234.56, "USD")`

- **Currency Detection:**
  - Symbols: `$`, `€`, `£`, `¥`, `₹`, `₱`, `₽`, `₪`, `₿`
  - Codes: `USD`, `EUR`, `GBP`, `JPY`, `INR`, etc.

- **Special Cases:**
  - Range prices: "now $19.99 was $29.99" → Takes the **current** price ($19.99)
  - Crossed-out prices: Ignores old prices
  - Missing currency: Defaults to USD

- **Currency Conversion:**
  ```python
  from scrapers.price_normalizer import normalize_price
  
  # Convert EUR to USD
  usd_price = normalize_price(19.99, from_currency="EUR", to_currency="USD")
  # Result: ~21.59 (uses static exchange rates)
  ```

- **Outlier Detection:**
  ```python
  from scrapers.price_normalizer import detect_outlier
  
  historical_prices = [19.99, 20.49, 19.49, 20.99]
  is_outlier = detect_outlier(50.00, historical_prices)
  # True - price is >50% different from average
  ```

**Example Test Cases:**
```python
# US Format
parse_price("$19.99")  # (19.99, "USD")
parse_price("$1,299.99")  # (1299.99, "USD")

# European Format
parse_price("19,99 €")  # (19.99, "EUR")
parse_price("1.299,99 EUR")  # (1299.99, "EUR")

# Indian Format
parse_price("₹1,99,999")  # (199999.0, "INR")

# Range Prices
parse_price("was $29.99 now $19.99")  # (19.99, "USD") - takes last price

# Invalid
parse_price("Free")  # (None, "USD")
parse_price("Contact for price")  # (None, "USD")
```

**Why it matters:** Each site formats prices differently. This utility standardizes them into a consistent format for database storage and comparisons.

---

### 3. **Amazon Scraper**
**File:** `scrapers/amazon_scraper.py` (8,764 bytes)

**Purpose:** Extract product information from Amazon.com product pages.

**CSS Selectors (with fallbacks):**
```python
selectors = {
    'product_name': [
        '#productTitle',
        'h1.product-title',
        'h1#title'
    ],
    'price': [
        'span.a-price.a-text-price.a-size-medium.apexPriceToPay span.a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        'span.a-price span.a-offscreen'
    ],
    'availability': [
        '#availability span',
        '#availability',
        'div#availability'
    ]
}
```

**Why Multiple Selectors?**  
Amazon frequently changes HTML structure. The scraper tries each selector in order until one succeeds.

**Additional Data Extracted:**
- Product images
- Product ratings (e.g., "4.5 out of 5 stars")
- Review counts (e.g., "1,234 ratings")
- Seller name
- Stock status

**Usage:**
```python
from scrapers.amazon_scraper import scrape_amazon_product

data = scrape_amazon_product("https://www.amazon.com/dp/B08N5XSG8Z")

if data:
    print(f"Product: {data.product_name}")
    print(f"Price: ${data.price} {data.currency}")
    print(f"In Stock: {data.in_stock}")
    print(f"Rating: {data.product_rating}/5")
    print(f"Reviews: {data.review_count}")
```

**Special Configuration:**
```python
AmazonScraper(
    site_name="Amazon",
    min_delay=3.0,  # Amazon is strict - wait longer
    max_delay=6.0,  # between requests
)
```

**Availability Parser:**
- "In Stock" → `in_stock=True`
- "Temporarily out of stock" → `in_stock=False`
- "Only 3 left" → `in_stock=True`

**Why it matters:**Amazon is the most complex site to scrape. This implementation handles their dynamic pricing, multiple price display formats, and frequent HTML changes.

---

### 4. **eBay Scraper**
**File:** `scrapers/ebay_scraper.py` (8,900 bytes)

**Purpose:** Extract product information from eBay.com listing pages.

**CSS Selectors:**
```python
selectors = {
    'product_name': [
        'h1.x-item-title__mainTitle',
        'h1[class*="item-title"]',
        'h1.it-ttl'
    ],
    'price': [
        'div.x-price-primary span.ux-textspans',
        'span.ux-textspans.price',
        'span[itemprop="price"]',
        '.x-price-primary',
        '#prcIsum'
    ],
    'condition': [
        'div.x-item-condition-text span.ux-textspans',
        'div[itemprop="itemCondition"]'
    ]
}
```

**Handles Multiple Price Types:**
- **Buy It Now** prices
- **Auction** starting prices  
- **Best Offer** prices

**Additional Data:**
- Item condition (New/Used/Refurbished)
- Seller name
- Availability status

**Usage:**
```python
from scrapers.ebay_scraper import scrape_ebay_product

data = scrape_ebay_product("https://www.ebay.com/itm/123456789")

if data:
    print(f"Product: {data.product_name}")
    print(f"Price: ${data.price}")
    print(f"Condition: {data.availability_text}")  # Includes condition
    print(f"Seller: {data.seller_name}")
```

**Availability Parser:**
- "Available" → `in_stock=True`
- "No longer available" → `in_stock=False`
- "Last one" → `in_stock=True`

**Why it matters:** eBay has different HTML structure than Amazon. This shows how easily you can add new site scrapers by inheriting from `BaseScraper`.

---

### 5. **Scraper Factory**
**File:** `scrapers/scraper_factory.py` (5,200 bytes)

**Purpose:** Create scraper instances by site name. Makes adding new scrapers easy without changing orchestrator code.

**Pattern:**
```python
# Registry maps site names to scraper classes
SCRAPER_REGISTRY = {
    "Amazon": AmazonScraper,
    "eBay": EbayScraper,
    # Add new scrapers here:
    # "Walmart": WalmartScraper,
}

# Get scraper by name
scraper = get_scraper("Amazon")
if scraper:
    data = scraper.scrape(url)
```

**Functions:**
- `get_scraper(site_name)` - Get scraper instance
- `get_available_sites()` - List all supported sites
- `is_site_supported(site_name)` - Check if site has scraper
- `register_scraper(site_name, scraper_class)` - Dynamically add scraper

**Example:**
```python
from scrapers.scraper_factory import get_scraper, get_available_sites

# List all sites
sites = get_available_sites()  # ['Amazon', 'eBay']

# Get scraper for specific site
for site in sites:
    scraper = get_scraper(site)
    print(f"{site} scraper: {scraper.__class__.__name__}")
```

**Adding a New Site:**
1. Create `my_site_scraper.py` inheriting from `BaseScraper`
2. Add to registry:
   ```python
   from scrapers.my_site_scraper import MySiteScraper
   SCRAPER_REGISTRY["MySite"] = MySiteScraper
   ```
3. Add product URLs to `config.yaml`:
   ```yaml
   products:
     - id: prod_001
       urls:
         MySite: https://mysite.com/product/123
   ```

**Why it matters:** Decouples scraper creation from usage. The orchestrator doesn't need to know which scrapers exist - it asks the factory.

---

### 6. **Orchestrator (Brain of the System)**
**File:** `scrapers/orchestrator.py` (12,600 bytes)

**Purpose:** Coordinates scraping across multiple sites and products. Runs scrapers in parallel, stores results in database, tracks success/failures.

**Key Responsibilities:**
1. **Load products** from `config.yaml`
2. **Create scrapers** using factory
3. **Run in parallel** using `ThreadPoolExecutor`
4. **Store results** in database (Price + ScraperRun tables)
5. **Handle errors** and log failures

**Architecture:**
```
config.yaml → Orchestrator → Factory → Scrapers → BeautifulSoup
                    ↓
              ThreadPoolExecutor (3 workers)
                    ↓
              Database (Price + ScraperRun)
```

**Usage Example:**
```python
from scrapers.orchestrator import ScraperOrchestrator
from database.connection import get_session
from utils.config import load_config

config = load_config()

with get_session() as session:
    orchestrator = ScraperOrchestrator(
        db_session=session,
        config=config,
        max_workers=3  # 3 parallel scrapers
    )
    
    # Run all scrapers
    results = orchestrator.run_all_scrapers()
    
    print(f"Total: {results['total_products']}")
    print(f"Success: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Duration: {results['duration']:.2f}s")
```

**How It Works:**

**Step 1: Build Tasks**
```python
config.yaml has:
products:
  - id: prod_001
    name: "Sony Headphones"
    urls:
      Amazon: https://amazon.com/...
      eBay: https://ebay.com/...

Orchestrator creates 2 tasks:
  Task 1: Scrape prod_001 from Amazon
  Task 2: Scrape prod_001 from eBay
```

**Step 2: Execute in Parallel**
```python
ThreadPoolExecutor with 3 workers:

Worker 1: Task 1 (Amazon)  →  fetch HTML → parse → result
Worker 2: Task 2 (eBay)    →  fetch HTML → parse → result
Worker 3: (waiting)

Results collected as they complete
```

**Step 3: Save to Database**
```python
For each successful scrape:
  1. Ensure Product exists (create if not)
  2. Create Price record:
     - product_id
     - price
     - currency  
     - source_site
     - scraped_at
  3. Create ScraperRun record:
     - site_name
     - status (SUCCESS/FAILED/PARTIAL_SUCCESS)
     - products_attempted/succeeded/failed
     - error_details
     - duration
```

**Result Summary:**
```python
{
    'total_products': 10,
    'successful': 8,
    'failed': 2,
    'duration': 45.3,
    'results': [
        ScrapeResult(task=..., success=True, data=...),
        ScrapeResult(task=..., success=False, error="Timeout"),
        ...
    ]
}
```

**Database Records Created:**
- **Price records:** One per successful scrape
- **ScraperRun records:** One per site (aggregated stats)

**Example ScraperRun:**
```
site_name: "Amazon"
status: SUCCESS
products_attempted: 5
products_succeeded: 5
products_failed: 0
error_details: null
started_at: 2024-01-15 10:00:00
completed_at: 2024-01-15 10:00:23
duration_seconds: 23.5
```

**Why it matters:** This is the "brain" that brings everything together. It handles the complexity of parallel execution, error handling, and data persistence.

---

### 7. **Configuration Loader**
**File:** `utils/config.py` (8,500 bytes)

**Purpose:** Load and validate configuration from `config.yaml` and `.env` files.

**Features:**
- **YAML Loading** with validation
- **Environment Variable Injection** from `.env`
- **Configuration Caching** for performance
- **Path Normalization** (relative → absolute)
- **Type-Safe Access** with helper functions

**Configuration Structure:**
```yaml
database:
  path: price_tracker.db
  echo: false

scraping:
  min_delay: 2
  max_delay: 5
  timeout: 30
  max_retries: 3

products:
  - id: prod_001
    name: "Sony WH-1000XM5"
    sku: "SONY-WH1000XM5"
    category: "Electronics"
    urls:
      Amazon: https://amazon.com/...
      eBay: https://ebay.com/...

alerts:
  email:
    enabled: true
    username: ${EMAIL_USERNAME}  # Injected from .env
    password: ${EMAIL_PASSWORD}

scheduler:
  scrape_interval_hours: 4
```

**Helper Functions:**
```python
from utils.config import (
    load_config,
    get_database_url,
    get_products_config,
    get_scraping_config,
    get_alerts_config
)

# Load full config
config = load_config()

# Or use helpers
db_url = get_database_url()  # "sqlite:///C:/path/to/price_tracker.db"
products = get_products_config()  # List of product dicts
scraping = get_scraping_config()  # Scraping settings
```

**Environment Variable Injection:**
```yaml
# config.yaml
alerts:
  email:
    username: ${EMAIL_USERNAME}
    password: ${EMAIL_PASSWORD}

# .env
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Result after loading
alerts:
  email:
    username: "your-email@gmail.com"
    password: "your-app-password"
```

**Validation:**
- Ensures required sections exist (database, scraping, products)
- Validates products have `id` and `urls` fields
- Converts relative paths to absolute paths
- Loads .env if it exists

**Why it matters:** Centralizes all configuration logic. Scrapers, orchestrator, and CLI all use the same configuration source.

---

### 8. **CLI Commands**
**File:** `main.py` (updated, now ~270 lines)

**New Commands Added:**

#### **`python main.py scrape-now`**
Run all configured scrapers once.

**Options:**
- `--workers N` - Number of parallel scrapers (default: 3)

**Example:**
```bash
$ python main.py scrape-now --workers 5

2024-01-15 10:00:00 | INFO | Starting scraping run for all sites
2024-01-15 10:00:00 | INFO | Found 10 products to scrape
2024-01-15 10:00:05 | INFO | ✓ Successfully scraped prod_001 from Amazon ($19.99)
2024-01-15 10:00:07 | INFO | ✓ Successfully scraped prod_001 from eBay ($18.50)
...
2024-01-15 10:00:23 | INFO | Scraping run complete: 8 successful, 2 failed (23.5s)

===============================================================
SCRAPING COMPLETE
===============================================================
Total products: 10
Successful: 8
Failed: 2
Duration: 23.47 seconds
===============================================================
```

#### **`python main.py scrape-site <name>`**
Run scraper for a single site only.

**Example:**
```bash
$ python main.py scrape-site Amazon

2024-01-15 10:00:00 | INFO | Starting scraping run for: Amazon
2024-01-15 10:00:00 | INFO | Found 5 products for Amazon
2024-01-15 10:00:15 | INFO | Scraping run complete

===============================================================
SCRAPING COMPLETE: Amazon
===============================================================
Total products: 5
Successful: 5
Failed: 0
Duration: 15.23 seconds
===============================================================
```

#### **`python main.py list-sites`**
List all supported sites with scrapers.

**Example:**
```bash
$ python main.py list-sites

===============================================================
Supported Sites
===============================================================
Total supported sites: 2

  1. Amazon
  2. eBay

Use 'python main.py scrape-site <name>' to scrape a specific site
```

**Why it matters:** Gives you manual control over scraping. Useful for testing, debugging, or on-demand price checks.

---

## 🗂️ File Structure
```
Price Tracker/
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py           # Abstract base class (10,936 bytes)
│   ├── price_normalizer.py       # Price parsing utility (9,286 bytes)
│   ├── amazon_scraper.py         # Amazon implementation (8,764 bytes)
│   ├── ebay_scraper.py            # eBay implementation (8,900 bytes)
│   ├── scraper_factory.py         # Factory pattern (5,200 bytes)
│   └── orchestrator.py            # Parallel execution (12,600 bytes)
├── utils/
│   ├── __init__.py
│   ├── logging_config.py          # From Phase 1
│   └── config.py                  # Configuration loader (8,500 bytes) ← NEW
└── main.py                        # CLI with scraping commands (270 lines) ← UPDATED
```

**Total New Code:** ~55,000 bytes across 7 files

---

## 🧪 Testing
```bash
# Test scraper factory
$ python -m scrapers.scraper_factory
✓ Factory test complete

# Test configuration loading
$ python -m utils.config
✓ Configuration test complete

# Test CLI
$ python main.py list-sites
✓ Amazon, eBay available

# Test scraping (requires real URLs in config.yaml)
$ python main.py scrape-site Amazon
# Attempts to scrape actual Amazon products
```

---

## 💡 How the Pieces Fit Together

```
┌─────────────────┐
│   config.yaml   │  ← Product URLs, site settings
└────────┬────────┘
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌────────────────────┐                 ┌──────────────┐
│  Orchestrator      │◄────────────────│  CLI Command │
│  (Brain)           │                 │  scrape-now  │
└─────────┬──────────┘                 └──────────────┘
          │
          │ Reads products
          │ Creates tasks
          │
          ▼
┌──────────────────────┐
│ ThreadPoolExecutor   │  ← 3 parallel workers
│ (Max 3 workers)      │
└──────────┬───────────┘
           │
           │ For each task:
           │
           ▼
┌────────────────────┐
│ Scraper Factory    │  ← get_scraper("Amazon")
└─────────┬──────────┘
          │
          ├─────────────────┬────────────────┐
          │                 │                │
          ▼                 ▼                ▼
┌────────────────┐  ┌──────────────┐  ┌─────────────┐
│ AmazonScraper  │  │ EbayScraper  │  │ (More...)   │
└────────┬───────┘  └──────┬───────┘  └─────────────┘
         │                 │
         │ Inherits        │ Inherits
         │                 │
         ▼                 ▼
┌────────────────────────────┐
│ BaseScraper                │  ← HTTP, retries, rate limiting
│ - fetch_html()             │
│ - _enforce_rate_limit()    │
│ - _get_headers()           │
└────────────┬───────────────┘
             │
             │ Uses
             │
             ▼
┌─────────────────────────────┐
│ BeautifulSoup + lxml        │  ← Parse HTML
└─────────────┬───────────────┘
              │
              │ Extract price text
              │
              ▼
┌─────────────────────────────┐
│ price_normalizer.py         │  ← "$19.99" → (19.99, "USD")
└─────────────┬───────────────┘
              │
              │ Return ScrapedData
              │
              ▼
┌─────────────────────────────┐
│ Orchestrator                │
│ - Collects all results      │
│ - Saves to database:        │
│   * Price records           │
│   * ScraperRun records      │
└─────────────────────────────┘
```

---

## 📊 Database Impact

**New Records Created Per Scrape:**

For `config.yaml` with 1 product on 2 sites (Amazon + eBay):

```sql
-- Price records (1 per successful scrape)
INSERT INTO prices (product_id, price, currency, source_site, scraped_at, ...)
VALUES 
  ('prod_001', 19.99, 'USD', 'Amazon', '2024-01-15 10:00:05', ...),
  ('prod_001', 18.50, 'USD', 'eBay', '2024-01-15 10:00:07', ...);

-- ScraperRun records (1 per site)
INSERT INTO scraper_runs (site_name, status, products_attempted, started_at, ...)
VALUES
  ('Amazon', 'SUCCESS', 1, '2024-01-15 10:00:00', ...),
  ('eBay', 'SUCCESS', 1, '2024-01-15 10:00:00', ...);
```

**Query Historical Prices:**
```sql
-- Get price history for a product
SELECT 
    source_site,
    price,
    currency,
    scraped_at
FROM prices
WHERE product_id = 'prod_001'
ORDER BY scraped_at DESC
LIMIT 10;
```

**View Scraper Performance:**
```sql
-- See recent scraper runs
SELECT 
    site_name,
    status,
    products_succeeded,
    products_failed,
    duration_seconds,
    started_at
FROM scraper_runs
ORDER BY started_at DESC
LIMIT 5;
```

---

## 🚀 Next Steps: Phase 3 (Job Scheduling)

**What's Missing:** Right now, scraping is manual (`python main.py scrape-now`). Phase 3 will add automatic scheduling:

**Goals:**
- ✅ Run scrapers every 4 hours automatically
- ✅ Background service that runs continuously
- ✅ Configurable schedule (cron-like syntax)
- ✅ Graceful start/stop

**Implementation Plan:**
1. **APScheduler Integration**
   - Create `scheduler/job_scheduler.py`
   - Add `IntervalTrigger` for 4-hour intervals
   - Add `CronTrigger` for specific times

2. **CLI Commands**
   - `python main.py start` - Start scheduler daemon
   - `python main.py stop` - Stop scheduler
   - `python main.py list-jobs` - Show scheduled jobs

3. **Background Execution**
   - Runs as Windows service or background process
   - Logs to `logs/scheduler.log`
   - Handles crashes/restarts

**Example:**
```bash
$ python main.py start

2024-01-15 10:00:00 | INFO | Scheduler started
2024-01-15 10:00:00 | INFO | Next scrape: 2024-01-15 14:00:00 (4 hours)

# Scheduler runs automatically every 4 hours
# You can close the terminal - it runs in background
```

---

## 📖 Key Concepts

### **1. Abstract Base Class Pattern**
`BaseScraper` defines common behavior (HTTP, retries, rate limiting).  
Site-specific scrapers (Amazon, eBay) only implement `parse_html()`.

**Benefit:** Add 20 new sites without rewriting HTTP logic 20 times.

### **2. Factory Pattern**
`ScraperFactory` creates scrapers by name from a registry.

**Benefit:** Orchestrator doesn't need to know which scrapers exist. Easy to add new sites.

### **3. Parallel Execution**
`ThreadPoolExecutor` runs multiple scrapers at once.

**Benefit:** Scraping 10 products from 3 sites takes ~20 seconds instead of ~60 seconds.

### **4. Fallback Selectors**
Each site has multiple CSS selectors for the same data.

**Benefit:** If Amazon changes `#productTitle` to `.product-title-new`, the second selector kicks in.

### **5. Separation of Concerns**
- `BaseScraper` → HTTP logic
- `price_normalizer` → Price parsing
- `amazon_scraper` → Amazon-specific HTML
- `orchestrator` → Coordination
- `config.py` → Settings
- `database` → Storage

**Benefit:** Change one part without breaking others. Easy to test and maintain.

---

## 🎯 Phase 2 Complete!

**What You Can Do Now:**
```bash
# 1. List supported sites
$ python main.py list-sites

# 2. Scrape all products once
$ python main.py scrape-now

# 3. Scrape only Amazon
$ python main.py scrape-site Amazon

# 4. View results in database
$ sqlite3 price_tracker.db
sqlite> SELECT * FROM prices ORDER BY scraped_at DESC LIMIT 5;
```

**Next:** Phase 3 will add automatic scheduling so scraping happens every 4 hours without manual intervention!
