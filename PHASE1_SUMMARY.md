# Phase 1 Complete - Summary & Explanations

## 🎉 What We've Accomplished

Phase 1 is the **foundation** of the Price Tracker project. We've built all the infrastructure needed before writing any scraping or alerting code.

---

## 📋 Step-by-Step Breakdown with Explanations

### **Step 1: Project Folder Structure** ✅

**What we created:**
```
Price Tracker/
├── scrapers/      # Will contain web scraping modules
├── database/      # Database models and connections
├── alerts/        # Email and Slack alert system
├── reports/       # Weekly report generation
├── scheduler/     # Job scheduling with APScheduler
├── tests/         # Automated tests
├── utils/         # Utility modules like logging
└── logs/          # Auto-generated log files
```

**Why this matters:**
- **Organization:** Each component has its own folder, making code easy to find
- **Modularity:** Changes to one module don't affect others
- **Scalability:** Easy to add new features without cluttering existing code
- **Python Packages:** `__init__.py` files make folders importable as Python modules

---

### **Step 2: requirements.txt** ✅

**What it contains:**
```
sqlalchemy>=2.0.0    # Database ORM
requests>=2.31.0     # HTTP library for web scraping
beautifulsoup4       # HTML parsing
apscheduler          # Job scheduling
pytest              # Testing framework
... and more
```

**Why this matters:**
- **Reproducibility:** Anyone can install exact same dependencies with `pip install -r requirements.txt`
- **Version Control:** Pins specific versions to avoid "it works on my machine" issues
- **Documentation:** Shows all libraries the project uses

**How it works:**
- Run: `pip install -r requirements.txt`
- pip reads the file and installs each library
- `>=` means "this version or newer"

---

### **Step 3: .gitignore** ✅

**What it does:**
Tells Git which files to **never** commit to version control.

**Key exclusions:**
```
.env                # Contains passwords - NEVER commit!
*.db                # Database files (should be backed up separately)
__pycache__/        # Python bytecode cache
logs/*.log          # Log files (too noisy for Git)
venv/               # Virtual environment folder
```

**Why this matters:**
- **Security:** Prevents accidentally committing passwords/API keys to GitHub
- **Cleanliness:** Keeps repository focused on code, not generated files
- **Performance:** Smaller repo size, faster clones

**Real-world example:**
Without `.gitignore`, you might commit `.env` with your email password, then push to GitHub. Now your credentials are public forever (even if you delete the file later, it stays in Git history).

---

### **Step 4: config.yaml** ✅

**What it contains:**
```yaml
database:
  path: "price_tracker.db"
  data_retention_days: 90

scraping:
  min_delay: 2  # seconds between requests
  max_retries: 3

sites:
  - name: "Amazon"
    selectors:
      price: "#priceblock_ourprice"
      product_name: "#productTitle"
```

**Why YAML instead of Python code:**
- **Non-programmers can edit:** Product manager can update URLs without touching code
- **Different environments:** Easy to have dev.yaml, prod.yaml with different settings
- **No code changes needed:** Modify thresholds, add new sites, change schedules without redeploying

**How it works:**
1. Python loads YAML with `pyyaml`
2. YAML becomes a Python dictionary
3. Access values like: `config['scraping']['min_delay']`

---

### **Step 5: .env and .env.example** ✅

**The Problem:**
You can't put passwords in `config.yaml` because that file is committed to Git!

**The Solution:**
- `.env`: Contains actual secrets (NOT in Git, in `.gitignore`)
- `.env.example`: Template showing what secrets are needed (safe to commit)

**Contents:**
```
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

**How it works:**
1. `python-dotenv` loads `.env` file
2. Values become environment variables
3. Access in Python: `os.getenv('EMAIL_USERNAME')`

**Best practice:**
- When a team member clones the repo, they copy `.env.example` to `.env` and fill in their credentials
- Each developer has their own `.env` (never shared)

---

### **Step 6: Database Models (database/models.py)** ✅

**What it does:**
Defines database structure using **SQLAlchemy ORM** (Object-Relational Mapping).

**Without ORM (raw SQL):**
```python
cursor.execute("INSERT INTO products (product_id, name) VALUES (?, ?)", 
               ("prod_001", "Sony Headphones"))
```

**With ORM (SQLAlchemy):**
```python
product = Product(product_id="prod_001", name="Sony Headphones")
session.add(product)
session.commit()
```

**Models we created:**

1. **Product** - Master list of products being tracked
   ```python
   product_id, name, sku, category, created_at, updated_at
   ```

2. **Price** - Historical price data (time-series)
   ```python
   product_id, price, currency, source_site, scraped_at, in_stock
   ```

3. **ScraperRun** - Metadata about scraping jobs
   ```python
   site_name, status, products_succeeded, errors, start_time, end_time
   ```

4. **AlertSent** - Tracks sent alerts (prevents duplicates)
   ```python
   product_id, alert_type, old_price, new_price, sent_at
   ```

5. **Threshold** - Per-product alert settings
   ```python
   product_id, target_price, percentage_drop, enabled
   ```

**Why this matters:**
- **Type Safety:** Python checks types at code time, not runtime errors
- **Relationships:** Easy to query "all prices for this product"
- **Automatic Schema:** SQLAlchemy creates tables from models
- **Database Agnostic:** Same code works with SQLite, PostgreSQL, MySQL

**Example relationship:**
```python
product = session.query(Product).first()
print(product.prices)  # Automatically fetches all related prices!
```

---

### **Step 7: Database Connection (database/connection.py)** ✅

**What it does:**
Manages database connections and sessions.

**Key Concepts:**

**Engine:**
- The "connector" to the database file
- Created once, reused for all operations
- Configuration: timeouts, connection pooling, etc.

**Session:**
- A "transaction" or "unit of work"
- Groups multiple operations (add, update, delete)
- Automatically commits on success, rolls back on error

**Context Manager Pattern:**
```python
with get_session() as session:
    product = Product(name="Example")
    session.add(product)
    session.commit()
# Session automatically closed here
```

**Why context managers:**
- **Automatic cleanup:** Session closes even if error occurs
- **No forgotten closes:** Can't forget to call `session.close()`
- **Rollback on error:** If exception happens, changes are rolled back

**SQLite specific settings:**
```python
"check_same_thread": False  # Allow multi-threaded access
"timeout": 30              # Wait 30sec if database is locked
PRAGMA journal_mode=WAL    # Write-Ahead Logging (better concurrency)
```

---

### **Step 8: Logging Configuration (utils/logging_config.py)** ✅

**What it does:**
Sets up centralized logging with file rotation and console output.

**Log Levels:**
- **DEBUG:** Detailed diagnostic info (only in development)
- **INFO:** General informational messages
- **WARNING:** Something unexpected but not critical
- **ERROR:** An error occurred but app continues
- **CRITICAL:** Severe error, app might crash

**Features:**

1. **Rotating File Handlers**
   ```
   logs/price_tracker.log      (10 MB max, keeps 5 old files)
   logs/scraper_errors.log     (scraper-specific errors)
   logs/alerts.log             (alert history)
   ```

2. **Color-Coded Console**
   - Red = Errors
   - Yellow = Warnings
   - Cyan = Info
   - Gray = Debug

3. **Structured Format**
   ```
   2026-03-09 10:34:10 | scrapers.amazon | ERROR | Failed to parse price
   [timestamp]         | [module]        | [level] | [message]
   ```

**Why logging matters:**

**Debugging:**
```
Without logs: "The scraper failed yesterday but I don't know why"
With logs: "Looking at logs, Amazon returned 503 at 2AM, retried 3 times, then gave up"
```

**Monitoring:**
```
Grep error count: cat logs/scraper_errors.log | grep ERROR | wc -l
Answer: "47 errors today, unusual, let's investigate"
```

**Auditing:**
```
"When was the last alert sent for Product X?"
Check logs/alerts.log: "2026-03-08 14:32:12 | Alert sent: Price dropped 15%"
```

---

### **Step 9: Pytest Configuration (pytest.ini + tests/)** ✅

**What it does:**
Sets up automated testing framework.

**Test Types:**

1. **Unit Tests** - Test individual functions
   ```python
   def test_price_parsing():
       assert parse_price("$19.99") == 19.99
       assert parse_price("€19,99") == 19.99
   ```

2. **Integration Tests** - Test components working together
   ```python
   def test_scrape_and_store(db_session):
       scraper.scrape_product("https://example.com")
       prices = db_session.query(Price).all()
       assert len(prices) == 1
   ```

**Fixtures (conftest.py):**
Reusable test components:
```python
@pytest.fixture
def db_session():
    # Create in-memory test database
    # Runs before each test
    yield session
    # Cleanup after test
```

**Coverage:**
Shows which lines of code are tested:
```bash
pytest --cov=. --cov-report=html
# Opens htmlcov/index.html showing 82% coverage
```

**Why testing matters:**

**Catch bugs early:**
```
Without tests: Deploy to production → users find bugs → hotfix panic
With tests: Write test → test fails → fix bug → test passes → deploy confidently
```

**Refactoring safety:**
```
"I want to rewrite the price parser for better performance"
Run tests → all pass → safe to deploy
```

**Documentation:**
```
Tests show how code should be used:
def test_add_product(db_session):
    product = Product(product_id="prod_001", name="Test")
    db_session.add(product)
    db_session.commit()
```

---

## 🔍 How Everything Works Together

**Scenario: Program Startup**

1. **Import modules** → `utils/logging_config.py` runs automatically
2. **Setup logging** → Creates `logs/` folder, initializes handlers
3. **Main.py runs** → Parses CLI arguments (`init`, `test-db`, etc.)
4. **Database needed** → `database/connection.py` creates engine
5. **SQLAlchemy reads** → `database/models.py` to know table structure
6. **Create tables** → SQLAlchemy executes CREATE TABLE statements
7. **Ready!** → Database exists, logging works, CLI responds

**Scenario: Running Tests**

1. **pytest discovers** → Finds `tests/test_*.py` files
2. **conftest.py loads** → Sets up fixtures (db_session, mock_config)
3. **For each test:**
   - Create in-memory SQLite database
   - Run test function
   - Rollback all changes
   - Close database
4. **Report results** → Green checkmarks or red failures

---

## 💾 Database Schema Visualization

```
┌─────────────┐
│  products   │
│─────────────│
│ id          │──┐
│ product_id  │  │
│ name        │  │
│ sku         │  │
│ category    │  │
└─────────────┘  │
                 │
                 │ (one-to-many)
                 │
                 ├─→ ┌─────────────┐
                 │   │   prices    │
                 │   │─────────────│
                 │   │ id          │
                 │   │ product_id  │ (foreign key)
                 │   │ price       │
                 │   │ source_site │
                 │   │ scraped_at  │
                 │   └─────────────┘
                 │
                 ├─→ ┌──────────────┐
                 │   │  thresholds  │
                 │   │──────────────│
                 │   │ product_id   │ (foreign key)
                 │   │ target_price │
                 │   │ percentage_  │
                 │   │   drop       │
                 │   └──────────────┘
                 │
                 └─→ ┌──────────────┐
                     │ alerts_sent  │
                     │──────────────│
                     │ product_id   │ (foreign key)
                     │ alert_type   │
                     │ new_price    │
                     │ sent_at      │
                     └──────────────┘
```

---

## 🎓 Key Concepts Explained

### **What is ORM (Object-Relational Mapping)?**

Bridges the gap between **objects** (Python classes) and **relational data** (SQL tables).

```python
# Without ORM (raw SQL):
cursor.execute("SELECT * FROM products WHERE category = ?", ("Electronics",))
rows = cursor.fetchall()
for row in rows:
    print(row[2])  # What is column 2? Have to remember!

# With ORM (SQLAlchemy):
products = session.query(Product).filter(Product.category == "Electronics")
for product in products:
    print(product.name)  # Clear, type-checked, auto-complete in IDE!
```

### **What are Context Managers?**

Python's `with` statement for automatic resource cleanup:

```python
# Without context manager:
file = open("data.txt")
data = file.read()
file.close()  # Easy to forget!

# With context manager:
with open("data.txt") as file:
    data = file.read()
# File automatically closed, even if error occurs
```

### **What is a Virtual Environment?**

Isolated Python environment for each project:

```
System Python:  Django 3.0, requests 2.20
Project 1 venv: Django 4.0, requests 2.31  ← Our Project
Project 2 venv: Flask 2.0, requests 2.28
```

**Why:** Prevents version conflicts between projects.

---

## ✅ Verification Checklist

Run these commands to verify Phase 1:

```powershell
# 1. Check Python version
python --version  # Should be 3.9+

# 2. Initialize database
python main.py init

# 3. Test database connection
python main.py test-db

# 4. Test logging
python main.py test-logging

# 5. Check files exist
ls logs/price_tracker.log
ls price_tracker.db

# 6. Run tests (if pytest installed)
pytest tests/test_database.py -v
```

---

## 🚀 What's Next: Phase 2 Preview

Now that foundation is ready, Phase 2 will add:

1. **Base Scraper Class** - Common scraping logic
2. **Site-Specific Scrapers** - Amazon, eBay implementations
3. **Price Normalizer** - Handle "$19.99", "19,99€", "USD 19.99"
4. **Scraper Orchestrator** - Run scrapers in parallel
5. **Error Handling** - Retry logic, rate limiting, anti-scraping measures

**End Goal:** Automated price scraping that stores data in our database.

---

## 📚 Learning Resources

**SQLAlchemy ORM:**
- Tutorial: https://docs.sqlalchemy.org/en/20/tutorial/
- Relationships: https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html

**Pytest:**
- Getting Started: https://docs.pytest.org/en/stable/getting-started.html
- Fixtures: https://docs.pytest.org/en/stable/fixture.html

**Python Logging:**
- HOWTO: https://docs.python.org/3/howto/logging.html
- Cookbook: https://docs.python.org/3/howto/logging-cookbook.html

**Environment Variables:**
- python-dotenv: https://pypi.org/project/python-dotenv/

---

**Phase 1 Complete! Foundation is solid and ready for building scrapers.**
