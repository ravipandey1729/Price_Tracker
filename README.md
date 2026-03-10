# Price Tracker - Phase 3 Complete! 🎉

A Python-based automated price tracking system that monitors competitor prices from multiple e-commerce sites, runs continuously in the background, stores historical data, and will send alerts and generate reports.

## 📋 Project Status

**✅ Phase 1: Foundation Complete** _(Database, Configuration, Logging)_  
**✅ Phase 2: Web Scraping Complete** _(Amazon, eBay scrapers, parallel execution)_  
**✅ Phase 3: Job Scheduling Complete** _(Automatic 4-hour intervals, background daemon)_  
**⏳ Phase 4: Alerts** _(Coming next - Email & Slack notifications)_

### What's Been Built

| Component            | Status      | Description                                            |
| -------------------- | ----------- | ------------------------------------------------------ |
| **Phase 1**          |             |                                                        |
| Project Structure    | ✅ Complete | All folders and Python packages created                |
| Dependencies         | ✅ Complete | requirements.txt with all necessary libraries          |
| Configuration        | ✅ Complete | config.yaml for settings, .env for secrets             |
| Database Models      | ✅ Complete | SQLAlchemy ORM models for all data structures          |
| Database Connection  | ✅ Complete | Session management and connection handling             |
| Logging System       | ✅ Complete | Rotating file handlers with color-coded console output |
| Testing Setup        | ✅ Complete | Pytest configuration with fixtures and sample tests    |
| CLI Entry Point      | ✅ Complete | main.py with init and test commands                    |
| **Phase 2**          |             |                                                        |
| Base Scraper         | ✅ Complete | Abstract class with HTTP, retries, rate limiting       |
| Price Normalizer     | ✅ Complete | Parses $19.99, €19,99, currency conversion             |
| Amazon Scraper       | ✅ Complete | Extracts prices from Amazon.com                        |
| eBay Scraper         | ✅ Complete | Extracts prices from eBay.com                          |
| Scraper Factory      | ✅ Complete | Creates scrapers by site name                          |
| Orchestrator         | ✅ Complete | Runs scrapers in parallel, stores in database          |
| Configuration Loader | ✅ Complete | Loads config.yaml and .env                             |
| Scraping CLI         | ✅ Complete | Commands: scrape-now, scrape-site, list-sites          |
| **Phase 3**          |             |                                                        |
| Job Scheduler        | ✅ Complete | APScheduler integration with interval/cron triggers    |
| Daemon Manager       | ✅ Complete | Background process control with PID file               |
| Scheduler CLI        | ✅ Complete | Commands: start, stop, restart, status, list-jobs      |
| Process Monitoring   | ✅ Complete | CPU, memory, uptime tracking with psutil               |
| Graceful Shutdown    | ✅ Complete | Signal handlers for SIGINT/SIGTERM                     |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** (Check: `python --version`)
- **pip** (Python package manager)
- **Virtual environment** (recommended)

### Installation

1. **Navigate to project directory:**

   ```powershell
   cd "c:\Users\pande\Desktop\Price Tracker"
   ```

2. **Create virtual environment:**

   ```powershell
   python -m venv venv
   ```

3. **Activate virtual environment:**

   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

   _If you get an execution policy error, run:_

   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

4. **Install dependencies:**

   ```powershell
   pip install -r requirements.txt
   ```

5. **Initialize database:**
   ```powershell
   python main.py init
   ```

---

## 🧪 Verify Phase 1 Installation

Run these commands to verify everything works:

### 1. Test Database Connection

```powershell
python main.py test-db
```

**Expected output:**

```
============================================================
 Testing Database Connection
============================================================
✓ Database connection test successful
Database path: C:\Users\pande\Desktop\Price Tracker\price_tracker.db

Table row counts:
  products       : 0 rows
  prices         : 0 rows
  scraper_runs   : 0 rows
  alerts_sent    : 0 rows
  thresholds     : 0 rows

✓ All database tests passed
```

### 2. Test Logging System

```powershell
python main.py test-logging
```

**Expected output:** Color-coded log messages in console + log files created in `logs/` folder

### 3. Run Database Tests

```powershell
pytest tests/test_database.py -v
```

**Expected output:** All tests should pass with green checkmarks

### 4. Test Direct Database Module

```powershell
python -m database.connection
```

---

## 🌐 Phase 2: Web Scraping Quick Start

### Setup Products in config.yaml

Edit `config.yaml` and add your products:

```yaml
products:
  - id: prod_001
    name: "Sony WH-1000XM5 Headphones"
    sku: "SONY-WH1000XM5"
    category: "Electronics"
    urls:
      Amazon: "https://www.amazon.com/Sony-WH-1000XM5-Cancelling-Headphones/dp/B0BZ1TY57M"
      eBay: "https://www.ebay.com/itm/..."
```

### Run Scrapers

#### 1. Test Site Support

```powershell
python main.py list-sites
```

**Output:**

```
Supported sites: 2

  1. Amazon
  2. eBay
```

#### 2. Scrape All Products

```powershell
python main.py scrape-now
```

**Output:**

```
Starting scraping run for all sites
Found 2 products to scrape
✓ Successfully scraped prod_001 from Amazon ($19.99)
✓ Successfully scraped prod_001 from eBay ($18.50)

========================================
SCRAPING COMPLETE
========================================
Total products: 2
Successful: 2
Failed: 0
Duration: 8.34 seconds
========================================
```

#### 3. Scrape Only One Site

```powershell
python main.py scrape-site Amazon
```

### View Scraped Data

```powershell
# Open database
sqlite3 price_tracker.db

# Query latest prices
sqlite> SELECT product_id, price, currency, source_site, scraped_at
        FROM prices
        ORDER BY scraped_at DESC
        LIMIT 5;

# View scraper runs
sqlite> SELECT site_name, status, products_succeeded, products_failed, duration_seconds
        FROM scraper_runs
        ORDER BY started_at DESC
        LIMIT 5;
```

### Customize Scraping

**Parallel Workers:**

```powershell
# Use 5 parallel workers (faster for many products)
python main.py scrape-now --workers 5
```

**Add New Site:**

1. Create `scrapers/walmart_scraper.py` (copy from `amazon_scraper.py`)
2. Update CSS selectors for Walmart
3. Register in `scrapers/scraper_factory.py`:
   ```python
   from scrapers.walmart_scraper import WalmartScraper
   SCRAPER_REGISTRY["Walmart"] = WalmartScraper
   ```
4. Add URLs to `config.yaml`

**Troubleshooting:**

- Check `logs/scraper_errors.log` for failures
- Failed HTML saved to `logs/failed_scrapes/` for debugging
- Use `--workers 1` to debug one at a time

**📖 Detailed Guide:** See `PHASE2_SUMMARY.md` for complete architecture explanation

---

## ⏰ Phase 3: Job Scheduling Quick Start

### Start the Scheduler (Background Mode)

```powershell
python main.py start
```

**Output:**

```
✓ Scheduler started successfully
PID: 12345
Log file: logs/scheduler.log

The scheduler is now running in the background every 4 hours.
Use 'python main.py status' to check status.
```

**What it does:**
- Spawns background daemon process
- Runs scraping automatically every 4 hours (configurable)
- Writes to `logs/scheduler.log`
- Stores PID in `scheduler.pid`

### Check Scheduler Status

```powershell
python main.py status
```

**Output:**

```
========================================
SCHEDULER STATUS
========================================
Running         : True
PID             : 12345
CPU Usage       : 0.5%
Memory          : 45.2 MB
Uptime          : 2h 34m 12s
Started At      : 2024-03-10 14:23:45
========================================
```

**With verbose logs:**

```powershell
python main.py status --verbose
```

### Stop the Scheduler

```powershell
python main.py stop
```

**Output:**

```
Stopping scheduler (PID: 12345)...
✓ Scheduler stopped successfully
```

**With custom timeout:**

```powershell
python main.py stop --timeout 30  # Wait 30 seconds before force kill
```

### Restart the Scheduler

```powershell
python main.py restart
```

### View Scheduled Jobs

```powershell
python main.py list-jobs
```

**Output:**

```
========================================
SCHEDULED JOBS
========================================
✗ Scheduler is not running

Schedule Configuration:
  Interval: Every 4 hours
  Sites: Amazon, eBay
  Max Workers: 3
  Timeout: 30 seconds

Products to scrape:
  1. prod_001 - PlayStation 5 Console
     Amazon: https://www.amazon.com/dp/B0CL5KNB9M
     eBay: https://www.ebay.com/itm/123456789

Use 'python main.py start' to begin automatic scraping.
========================================
```

### Run in Foreground (for debugging)

```powershell
python main.py start --foreground
```

**What it does:**
- Runs scheduler in current terminal (blocks)
- Shows all logs immediately
- Press Ctrl+C to stop
- Useful for debugging

### Customize Schedule

**Edit `config.yaml`:**

```yaml
# Option 1: Interval-based (every N hours)
scrape_interval_hours: 4

# Option 2: Cron-based (specific times)
scrape_cron: "0 9,15,21 * * *"  # 9 AM, 3 PM, 9 PM daily
```

**Monitoring:**

```powershell
# View logs in real-time
Get-Content logs\scheduler.log -Wait -Tail 20

# Check database for new prices
python main.py test-db
```

**Troubleshooting:**

- Scheduler won't start: Check `logs/scheduler.log` for errors
- Already running: Use `python main.py stop` first
- Permission denied: Delete `scheduler.pid` manually
- Process stuck: Use `python main.py stop --timeout 5` then force kill PID

**📖 Detailed Guide:** See `PHASE3_SUMMARY.md` for complete architecture explanation

---

## 🧪 Testing

### Run All Tests

```powershell
pytest tests/ -v
```

### Run with Coverage

```powershell
pytest tests/ --cov=. --cov-report=html
```

**View coverage report:** Open `htmlcov/index.html` in browser

---

## 📋 Available CLI Commands

### Phase 1 Commands

| Command        | Description                               |
| -------------- | ----------------------------------------- |
| `init`         | Initialize database                       |
| `init --force` | Recreate database (deletes existing data) |
| `test-db`      | Test database connection                  |
| `test-logging` | Test logging system                       |
| `version`      | Show version information                  |

### Phase 2 Commands

| Command                  | Description                         |
| ------------------------ | ----------------------------------- |
| `scrape-now`             | Run all scrapers once               |
| `scrape-now --workers N` | Use N parallel workers (default: 3) |
| `scrape-site <name>`     | Run scraper for specific site       |
| `list-sites`             | List all supported sites            |

### Phase 3 Commands

| Command                  | Description                              |
| ------------------------ | ---------------------------------------- |
| `start`                  | Start scheduler daemon                   |
| `start --foreground`     | Start in foreground (blocking mode)      |
| `stop`                   | Stop scheduler daemon                    |
| `stop --timeout N`       | Stop with N second timeout (default: 10) |
| `restart`                | Restart scheduler daemon                 |
| `status`                 | Show scheduler status (PID, CPU, memory) |
| `status --verbose`       | Show status + recent logs                |
| `list-jobs`              | Show scheduled jobs and configuration    |

### Coming in Phase 4

| Command | Description                   |
| ------- | ----------------------------- |
| `alert` | Configure price drop alerts   |
| `stop`      | Stop scheduler         |
| `list-jobs` | Show scheduled jobs    |

---

## 📁 Project Structure

```
Price Tracker/
├── scrapers/              # ✅ Web scraping modules (Phase 2)
│   ├── __init__.py
│   ├── base_scraper.py          # Abstract base class with HTTP logic
│   ├── price_normalizer.py      # Parse $19.99, €19,99, etc.
│   ├── amazon_scraper.py        # Amazon.com scraper
│   ├── ebay_scraper.py          # eBay.com scraper
│   ├── scraper_factory.py       # Factory pattern for creating scrapers
│   └── orchestrator.py          # Parallel execution coordinator
├── database/              # ✅ Database models and connection
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy ORM models
│   └── connection.py      # Database session management
├── alerts/                # Email/Slack alerts (Phase 4)
│   └── __init__.py
├── reports/               # Weekly report generation (Phase 5)
│   └── __init__.py
├── scheduler/             # ✅ APScheduler jobs (Phase 3)
│   ├── __init__.py
│   ├── job_scheduler.py   # APScheduler integration
│   └── daemon_manager.py  # Background daemon control
├── tests/                 # ✅ Pytest tests
│   ├── __init__.py
│   ├── conftest.py        # Shared fixtures
│   └── test_database.py  # Database model tests
├── utils/                 # ✅ Utility modules
│   ├── __init__.py
│   ├── logging_config.py  # Logging configuration
│   └── config.py          # ✅ Configuration loader (Phase 2)
├── logs/                  # ✅ Log files (auto-generated)
│   ├── .gitkeep
│   ├── price_tracker.log
│   ├── scraper_errors.log
│   └── failed_scrapes/    # Failed HTML dumps for debugging
├── config.yaml            # ✅ Application configuration
├── .env                   # ✅ Secret credentials (NOT in Git)
├── .env.example           # ✅ Template for .env
├── .gitignore             # ✅ Git ignore rules
├── requirements.txt       # ✅ Python dependencies
├── pytest.ini             # ✅ Pytest configuration
├── main.py                # ✅ CLI entry point with scraping commands
├── README.md              # ✅ This file
├── PHASE1_SUMMARY.md      # ✅ Detailed Phase 1 documentation
├── PHASE2_SUMMARY.md      # ✅ Detailed Phase 2 documentation
└── PHASE3_SUMMARY.md      # ✅ Detailed Phase 3 documentation
```

---

## ⚙️ Configuration

### config.yaml

Main configuration file for non-sensitive settings:

- Database path
- Scraping delays and retries
- Site URLs and CSS selectors (Phase 2)
- Product list (Phase 2)
- Scheduling intervals
- Alert thresholds
- Report settings

**📍 Location:** `c:\Users\pande\Desktop\Price Tracker\config.yaml`

### .env

Secret credentials (never commit to Git!):

- Email SMTP credentials
- Slack webhook URL
- API keys for scraping services

**📍 Location:** `c:\Users\pande\Desktop\Price Tracker\.env`

**⚠️ Important:** Update `.env` with your actual credentials before Phase 4 (Alerts)

---

## 🗄️ Database Schema

The SQLite database (`price_tracker.db`) contains 5 tables:

### 1. **products**

Master list of products being tracked

- `id`, `product_id`, `name`, `sku`, `category`, `created_at`, `updated_at`

### 2. **prices**

Historical price data (time-series)

- `id`, `product_id`, `price`, `currency`, `source_site`, `scraped_at`, etc.

### 3. **scraper_runs**

Metadata about scraping jobs

- `id`, `site_name`, `status`, `products_succeeded`, `errors`, `start_time`, etc.

### 4. **alerts_sent**

History of sent alerts (prevents duplicates)

- `id`, `product_id`, `alert_type`, `old_price`, `new_price`, `sent_at`, etc.

### 5. **thresholds**

Per-product alert thresholds

- `id`, `product_id`, `target_price`, `percentage_drop`, `enabled`, etc.

---

## 📝 Available CLI Commands (Phase 1)

```powershell
# Initialize database (creates tables)
python main.py init

# Force recreate database (deletes existing data)
python main.py init --force

# Test database connection
python main.py test-db

# Test logging system
python main.py test-logging

# Show version
python main.py version

# Show help
python main.py --help
```

---

## 🧪 Testing

### Run All Tests

```powershell
pytest tests/ -v
```

### Run Specific Test File

```powershell
pytest tests/test_database.py -v
```

### Run With Coverage Report

```powershell
pytest tests/ --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in your browser to see detailed coverage.

### Run Tests by Marker

```powershell
# Run only unit tests (once defined)
pytest -m unit

# Run only database tests
pytest -m database
```

---

## 📊 What Each Component Does

### **Database Models (database/models.py)**

Defines the structure of our database using SQLAlchemy ORM. Instead of writing raw SQL, we work with Python classes that represent tables. Each class (Product, Price, Threshold, etc.) becomes a table, and each instance becomes a row.

**Key Concepts:**

- **ORM (Object-Relational Mapping):** Use Python objects instead of SQL queries
- **Relationships:** Products have many prices, prices belong to products
- **Indexes:** Speed up queries on frequently-searched columns
- **Enums:** Type-safe status values (SUCCESS, FAILED, etc.)

### **Database Connection (database/connection.py)**

Manages SQLAlchemy engine and sessions. Think of:

- **Engine:** The connection to the database file
- **Session:** A "transaction" that groups related operations
- **Context Manager:** Automatically commits on success, rolls back on error

**Usage Pattern:**

```python
with get_session() as session:
    product = Product(product_id="prod_001", name="Example")
    session.add(product)
    session.commit()  # Saves to database
# Session automatically closed here
```

### **Logging (utils/logging_config.py)**

Centralized logging system that records everything happening in the app.

**Features:**

- **Rotating File Handlers:** Creates new log files when old ones get too big
- **Color-Coded Console:** Red for errors, yellow for warnings, cyan for info
- **Separate Log Files:** Different components can have their own logs
- **Structured Format:** Timestamp | Module Name | Level | Message

**Why Logging Matters:**

- Debug issues without re-running code
- Track scraping success rates
- Monitor errors in production
- Audit alert history

### **Configuration (config.yaml + .env)**

Separates code from configuration:

- **config.yaml:** Non-sensitive settings (URLs, thresholds, schedules)
- **.env:** Secret credentials (passwords, API keys)

**Benefits:**

- Change settings without editing code
- Different configs for dev/production
- Keep secrets out of version control

### **Testing (pytest)**

Automated tests verify code works correctly:

- **Unit Tests:** Test individual functions in isolation
- **Integration Tests:** Test multiple components working together
- **Fixtures:** Reusable test components (sample data, mock configs)

**Why Test:**

- Catch bugs before they reach production
- Safe refactoring (tests ensure nothing broke)
- Documentation (tests show how code should work)

---

## 🔍 Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'sqlalchemy'`  
**Solution:** Ensure virtual environment is activated and dependencies installed:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Database Locked

**Problem:** `database is locked`  
**Solution:** Close any programs accessing the database file, or run:

```powershell
python main.py init --force
```

### pytest Not Found

**Problem:** `'pytest' is not recognized`  
**Solution:** Install pytest in virtual environment:

```powershell
pip install pytest pytest-cov
```

### Permission Denied (Logs)

**Problem:** Can't create log files  
**Solution:** Run terminal as Administrator, or check folder permissions

---

## 📚 Next Steps: Phase 4

Phase 3 is complete! Next up:

1. **Alert Manager** - Detect price drops below thresholds
2. **Email Notifications** - Send alerts via SMTP
3. **Slack Integration** - Post alerts to Slack webhook
4. **Alert History** - Track sent alerts in database
5. **Alert Configuration** - CLI commands for threshold management

**Phase 4 will make the system truly useful** by notifying you automatically when prices drop!

---

## 🤝 Contributing

This is a personal project, but follow these practices:

- Write tests for new features
- Use type hints for function parameters
- Follow PEP 8 style guide (or use `black` formatter)
- Update this README when adding features

---

## 📄 License

Personal project - all rights reserved.

---

## 🎓 Learning Resources

- **SQLAlchemy:** https://docs.sqlalchemy.org/
- **Pytest:** https://docs.pytest.org/
- **Python Logging:** https://docs.python.org/3/howto/logging.html
- **YAML:** https://pyyaml.org/wiki/PyYAMLDocumentation

---

**Phase 1 ✅ Phase 2 ✅ Phase 3 Complete! 🚀**  
_Automated price tracking system with background scheduling ready for Phase 4 (Alerts)_
