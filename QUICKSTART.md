# Phase 2 Quick Reference Card

## 🎯 What You Can Do Now

### 1️⃣ List Supported Sites

```bash
python main.py list-sites
```

**Shows:** Amazon, eBay (+ any you add)

---

### 2️⃣ Scrape All Products

```bash
python main.py scrape-now
```

**What happens:**

- Reads products from `config.yaml`
- Scrapes each site in parallel (3 workers)
- Stores prices in database
- Shows success/failure summary

**Options:**

```bash
python main.py scrape-now --workers 5  # Use 5 parallel workers
```

---

### 3️⃣ Scrape One Site

```bash
python main.py scrape-site Amazon
```

**What happens:**

- Only scrapes Amazon products
- Useful for testing or debugging

---

### 4️⃣ View Results

```bash
sqlite3 price_tracker.db

# Latest prices
sqlite> SELECT * FROM prices ORDER BY scraped_at DESC LIMIT 5;

# Price history for one product
sqlite> SELECT price, source_site, scraped_at
        FROM prices
        WHERE product_id = 'prod_001'
        ORDER BY scraped_at DESC;

# Scraper performance
sqlite> SELECT site_name, products_succeeded, products_failed, duration_seconds
        FROM scraper_runs
        ORDER BY started_at DESC LIMIT 5;
```

---

## 🛠️ Adding Your Products

### Step 1: Edit config.yaml

```yaml
products:
  - id: prod_001
    name: "Sony WH-1000XM5 Headphones"
    sku: "SONY-WH1000XM5"
    category: "Electronics"
    urls:
      Amazon: "https://www.amazon.com/dp/B0BZ1TY57M"
      eBay: "https://www.ebay.com/itm/..."

  - id: prod_002
    name: "iPhone 15 Pro"
    sku: "IPHONE-15-PRO"
    category: "Electronics"
    urls:
      Amazon: "https://www.amazon.com/Apple-iPhone-15-Pro-256GB/dp/..."
      eBay: "https://www.ebay.com/itm/..."
```

### Step 2: Run Scraper

```bash
python main.py scrape-now
```

---

## 🧩 Architecture Overview

```
You run command:
  python main.py scrape-now

        ↓

config.yaml → Orchestrator
              - Reads products
              - Creates 3 workers

        ↓

Worker 1: Amazon Scraper  ──┐
Worker 2: eBay Scraper    ──┼──→ Parallel Execution
Worker 3: (waiting)       ──┘

        ↓

Each scraper:
  1. Fetch HTML (with retries)
  2. Parse with BeautifulSoup
  3. Extract price → Normalize
  4. Return ScrapedData

        ↓

Orchestrator:
  - Collects results
  - Saves to database:
    * Price records
    * ScraperRun records

        ↓

You see results:
  Total: 10 | Success: 8 | Failed: 2
```

---

## 🔍 Troubleshooting

### Scraping Failed?

**Check logs:**

```bash
# Detailed error logs
cat logs/scraper_errors.log

# Failed HTML snippets
ls logs/failed_scrapes/
```

**Common issues:**

- **Timeout:** Site too slow → Increase timeout in scraper
- **Parse error:** Site changed HTML → Update CSS selectors
- **Rate limit:** Too fast → Increase min_delay in scraper
- **403 Forbidden:** Blocked → User-Agent rotation (already implemented)

### Update CSS Selectors

If Amazon changes their HTML, update `scrapers/amazon_scraper.py`:

```python
self.selectors = {
    'price': [
        'NEW-SELECTOR-HERE',  # Add new selector first
        'span.a-price span.a-offscreen',  # Old selectors as fallback
        '#priceblock_ourprice',
    ]
}
```

---

## 📊 Database Schema

### prices table

```sql
product_id      TEXT      -- Foreign key to products
price           REAL      -- Decimal price (19.99)
currency        TEXT      -- Currency code (USD, EUR)
raw_price_text  TEXT      -- Original text ("$19.99")
source_site     TEXT      -- Site name (Amazon, eBay)
source_url      TEXT      -- Full product URL
in_stock        BOOLEAN   -- Availability
scraped_at      DATETIME  -- Timestamp
```

### scraper_runs table

```sql
site_name           TEXT      -- Site scraped
status              TEXT      -- SUCCESS/FAILED/PARTIAL_SUCCESS
products_attempted  INTEGER   -- Total products
products_succeeded  INTEGER   -- Successful
products_failed     INTEGER   -- Failed
error_details       TEXT      -- Error messages
started_at          DATETIME  -- Start time
completed_at        DATETIME  -- End time
duration_seconds    REAL      -- Execution time
```

---

## 🚀 What's Next: Phase 3

**Current:** You must run `python main.py scrape-now` manually

**Phase 3:** Automatic scheduling every 4 hours

```bash
# Start scheduler (runs in background)
python main.py start

# Scraping happens automatically:
# 10:00 AM → Scrape
# 2:00 PM  → Scrape
# 6:00 PM  → Scrape
# 10:00 PM → Scrape

# Stop scheduler
python main.py stop
```

**Implementation:**

- APScheduler with IntervalTrigger (4 hours)
- Windows service or background daemon
- Logging to scheduler.log
- Graceful start/stop

---

## 📚 Files to Read

| File                       | What's Inside                             |
| -------------------------- | ----------------------------------------- |
| `PHASE2_SUMMARY.md`        | Complete architecture details (20+ pages) |
| `README.md`                | Quick start guide                         |
| `config.yaml`              | Your product URLs + settings              |
| `scrapers/base_scraper.py` | HTTP logic, retries, rate limiting        |
| `scrapers/orchestrator.py` | Parallel execution coordinator            |
| `logs/scraper_errors.log`  | Scraping errors for debugging             |

---

## ✅ Phase 2 Complete Checklist

- [x] Base scraper with HTTP logic
- [x] Price normalizer ($19.99, €19,99, etc.)
- [x] Amazon scraper
- [x] eBay scraper
- [x] Scraper factory pattern
- [x] Orchestrator (parallel execution)
- [x] Configuration loader
- [x] CLI commands (scrape-now, scrape-site, list-sites)
- [x] Database integration
- [x] Error handling and logging
- [ ] Unit tests for scrapers (optional, can add later)
- [ ] More site scrapers (Walmart, BestBuy, etc.) - add as needed

---

## 🎓 Key Concepts Learned

1. **Abstract Base Class:** `BaseScraper` provides reusable HTTP logic
2. **Factory Pattern:** `ScraperFactory` creates scrapers by name
3. **Parallel Execution:** `ThreadPoolExecutor` runs 3 scrapers at once
4. **Fallback Selectors:** Multiple CSS selectors for resilience
5. **Price Normalization:** Handle various formats consistently
6. **Separation of Concerns:** Each module has one clear purpose

---

**🎉 Congratulations! You can now scrape prices from multiple sites and store them in your database!**
