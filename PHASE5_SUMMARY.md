# Phase 5: Weekly Reports - Implementation Summary

**Status:** ✅ Complete  
**Date:** March 11, 2026  
**Version:** v0.5.0

## 📋 Overview

Phase 5 adds comprehensive weekly price reporting with data visualization. The system automatically generates beautiful HTML email reports every week, showing price trends, statistics, and savings opportunities.

### What Was Built

1. **Report Generator** (`reports/report_generator.py`)
   - Price statistics calculation (min/max/avg/trend)
   - Matplotlib chart generation (3 chart types)
   - HTML email reports with embedded charts
   - Weekly automated scheduling

2. **Chart Generation**
   - Price history line charts with annotations
   - Price comparison bar charts
   - Savings opportunities horizontal bars
   - Base64-encoded charts embedded in emails

3. **Statistics Engine**
   - Per-product price analysis
   - Trend detection (increasing/decreasing/stable)
   - Savings calculation (current vs max price)
   - Alert frequency tracking
   - Scraper performance metrics

4. **CLI Integration**
   - `generate-report` command for manual generation
   - `--no-email` flag to preview without sending

5. **Scheduler Integration**
   - Automatic weekly report generation
   - Configurable day/time scheduling
   - Runs independently from scraping jobs

---

## 🏗️ Architecture

### Report Generator Class

```python
from reports.report_generator import ReportGenerator
from database.connection import get_session
from utils.config import load_config

config = load_config()

with get_session() as session:
    generator = ReportGenerator(config, session)
    result = generator.generate_weekly_report(send_email=True)
    
    print(f"Products analyzed: {result['products_analyzed']}")
    print(f"Charts generated: {result['charts_generated']}")
    print(f"Email sent: {result['email_sent']}")
```

### Key Components

#### 1. Report Generation Flow

```
1. Load configuration (days_to_include, chart settings)
2. Calculate date range (default: last 7 days)
3. Query active products from database
4. For each product:
   - Get price history in date range
   - Calculate statistics (min/max/avg/trend)
   - Calculate savings opportunities
   - Count alerts sent
5. Get scraper performance metrics
6. Generate charts (price history, comparison, savings)
7. Create HTML email with embedded charts
8. Send via SMTP (if email enabled)
```

#### 2. Price Statistics

```python
# Calculated for each product:
{
    'current_price': 299.99,
    'min_price': 285.00,       # Lowest in period
    'max_price': 320.00,       # Highest in period
    'avg_price': 302.50,       # Average in period
    'price_change': -5.00,     # Change from start to end
    'price_change_pct': -1.64, # Percentage change
    'trend': 'decreasing',     # increasing/decreasing/stable
    'savings_amount': 20.01,   # Current vs max
    'savings_pct': 6.25,       # Savings percentage
    'alerts_count': 2,         # Alerts sent in period
    'data_points': 42          # Number of price checks
}
```

#### 3. Chart Types

**A. Price History Chart** (Individual Product)
- Line chart showing price over time
- Annotated min/max prices with colored boxes
- Average price as dashed line
- Date formatting on x-axis
- Embedded as base64 PNG in email

**B. Price Comparison Chart** (Multi-Product)
- Bar chart comparing all products
- Three bars per product: Current, Lowest, Highest
- Color-coded (Blue=Current, Green=Lowest, Red=Highest)
- Rotated labels for readability
- Generated when tracking 4+ products

**C. Savings Opportunities Chart**
- Horizontal bar chart showing top savings
- Sorted by savings amount (highest first)
- Color-coded by savings percentage:
  - Green: >15% savings
  - Orange: 5-15% savings
  - Blue: <5% savings
- Shows savings percentage as labels

#### 4. HTML Email Template

The report email includes:
- **Header**: Gradient purple header with date range
- **Summary Statistics**: Grid of key metrics
  - Products tracked
  - Potential savings
  - Price alerts sent
  - Scraper success rate
- **Best Deal Highlight**: Featured best savings opportunity
- **Charts Section**: Embedded chart images
- **Product Details**: Cards for each product with stats
- **Scraper Performance**: Run statistics and metrics
- **Footer**: Generation timestamp

Responsive design with:
- CSS Grid for layout
- Mobile-friendly styling
- Professional color scheme
- Hover effects on buttons
- Clean typography

---

## ⚙️ Configuration

### config.yaml

Add this section to `config.yaml`:

```yaml
# ============================================================================
# WEEKLY REPORTS
# ============================================================================
reports:
  enabled: true              # Master switch for reports
  days_to_include: 7         # Include last N days of data
  top_deals_count: 5         # Number of top deals to highlight
  
  # Chart settings for email reports
  chart_width: 10            # Width in inches
  chart_height: 6            # Height in inches
  dpi: 100                   # Resolution for charts
  
  # Email delivery (uses same SMTP settings as alerts)
  send_email: true

# ============================================================================
# SCHEDULING
# ============================================================================
scheduling:
  # Scraping frequency
  scrape_interval_hours: 4
  
  # Weekly report schedule (cron-style)
  weekly_report:
    enabled: true
    day_of_week: "sun"       # mon, tue, wed, thu, fri, sat, sun
    hour: 20                 # 24-hour format (20 = 8 PM)
    minute: 0
```

### Report Settings Explained

| Setting | Description | Default | Notes |
|---------|-------------|---------|-------|
| `enabled` | Enable/disable reports | `true` | Master switch |
| `days_to_include` | Days of history in report | `7` | 1-30 days recommended |
| `top_deals_count` | Top N deals to highlight | `5` | Shown in savings chart |
| `chart_width` | Chart width in inches | `10` | Affects email size |
| `chart_height` | Chart height in inches | `6` | Affects email size |
| `dpi` | Chart resolution | `100` | Higher = better quality, larger size |
| `send_email` | Send reports via email | `true` | Requires email configured |

### Scheduling Options

The report day/time is configured in the `scheduling` section:

```yaml
weekly_report:
  enabled: true
  day_of_week: "sun"    # When to send
  hour: 20              # At what hour (24-hour format)
  minute: 0             # At what minute
```

**Day Options:** `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`

**Example Schedules:**
- Sunday at 8 PM: `day_of_week: "sun"`, `hour: 20`, `minute: 0`
- Monday at 9 AM: `day_of_week: "mon"`, `hour: 9`, `minute: 0`
- Friday at 5 PM: `day_of_week: "fri"`, `hour: 17`, `minute: 0`

---

## 🚀 Usage

### Manual Report Generation

Generate a report immediately and send via email:

```bash
python main.py generate-report
```

Generate report without sending email (preview mode):

```bash
python main.py generate-report --no-email
```

### Example Output

```
==================================================
      Generating Weekly Report
==================================================
2026-03-11 15:30:00 - INFO - Report Configuration:
2026-03-11 15:30:00 - INFO -   Days to include: 7
2026-03-11 15:30:00 - INFO -   Top deals count: 5
2026-03-11 15:30:00 - INFO -   Send email: True
2026-03-11 15:30:00 - INFO - 
2026-03-11 15:30:00 - INFO - Generating report...
2026-03-11 15:30:02 - INFO - Generated 3 charts
2026-03-11 15:30:02 - INFO - Connecting to SMTP server smtp.gmail.com:587
2026-03-11 15:30:03 - INFO - Report email sent to 1 recipients
2026-03-11 15:30:03 - INFO - 
2026-03-11 15:30:03 - INFO - ✓ Report generated successfully!
2026-03-11 15:30:03 - INFO -   Products analyzed: 5
2026-03-11 15:30:03 - INFO -   Charts generated: 3
2026-03-11 15:30:03 - INFO -   Period: 2026-03-04 to 2026-03-11
2026-03-11 15:30:03 - INFO -   ✓ Report email sent successfully
```

### Automatic Weekly Reports

Reports are automatically generated based on your schedule:

```bash
# Start the scheduler (runs in background)
python main.py start

# Check status to see next report time
python main.py status
```

Example status output:

```
Scheduler Status: RUNNING
PID: 12345
Uptime: 2 days, 5 hours, 23 minutes
Next scheduled jobs:
  - Automated Price Scraping: 2026-03-11 19:00:00
  - Weekly Price Report: 2026-03-14 20:00:00  ← Next Sunday at 8 PM
```

---

## 📊 Report Contents

### Email Report Sections

#### 1. **Header**
- Report title with gradient background
- Date range (e.g., "March 4, 2026 - March 11, 2026")

#### 2. **Summary Statistics**
Four key metrics in a grid:
- **Products Tracked**: Number of active products
- **Potential Savings**: Total savings if buying at current prices
- **Price Alerts**: Number of alerts sent during period
- **Scraper Success**: Success rate percentage

#### 3. **Best Deal Highlight** (if applicable)
Green highlight box featuring:
- Product name
- Savings amount and percentage
- Current price vs previous high
- "View Product" button linking to product page

#### 4. **Price Trends Charts**
Visual charts showing:
- Individual product price history (for 1-3 products)
- Price comparison across products (for 4+ products)
- Savings opportunities (top N deals)

#### 5. **Product Details**
Cards for each product showing:
- **Product name** and source (Amazon/eBay)
- **Current Price**: Latest scraped price
- **Week Low**: Lowest price in period (green)
- **Week High**: Highest price in period (red)
- **Average**: Mean price over period
- **Trend**: Badge indicating price direction
  - 🔴 Increasing (>2% rise)
  - 🟢 Decreasing (>2% drop)
  - ⚪ Stable (±2% change)
- **Potential Savings**: Savings vs week high
- **View on [Site]** button: Link to product page

#### 6. **Scraper Performance**
Statistics grid showing:
- **Total Runs**: Number of scraping jobs
- **Successful**: Completed runs
- **Failed**: Failed runs
- **Success Rate**: Percentage
- **Total Data Points**: Price records collected
- **Avg Duration**: Average scraping time

#### 7. **Footer**
- "Price Tracker" branding
- Report generation timestamp

---

## 🎨 Chart Details

### Price History Chart

**Generated for:** 1-3 products (individual charts)

**Features:**
- Line plot of price over time
- Blue line with circular markers
- **Min price annotation**: Green box with arrow pointing to lowest point
- **Max price annotation**: Red box with arrow pointing to highest point
- **Average line**: Orange dashed horizontal line
- Date formatting on x-axis (MM/DD)
- Grid lines for readability

**Code:**
```python
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(dates, prices, marker='o', linewidth=2, markersize=6, color='#2563eb')
ax.annotate('Low: $285.00', xy=(min_date, min_price), ...)
ax.annotate('High: $320.00', xy=(max_date, max_price), ...)
ax.axhline(y=avg_price, color='#f59e0b', linestyle='--', ...)
```

### Price Comparison Chart

**Generated for:** 4+ products

**Features:**
- Grouped bar chart
- Three bars per product:
  - **Current** (blue)
  - **Lowest** (green)
  - **Highest** (red)
- Product names on x-axis (rotated 45°, truncated to 30 chars)
- Legend in upper right
- Grid lines on y-axis only

### Savings Opportunities Chart

**Generated when:** Any product has savings > $0

**Features:**
- Horizontal bars showing top N deals
- Sorted by savings amount (descending)
- Color-coded by savings percentage:
  - Green (>15%): Great deal
  - Orange (5-15%): Good deal
  - Blue (<5%): Modest savings
- Percentage labels to right of each bar
- Product names on y-axis (truncated to 40 chars)

---

## 🛠️ Implementation Details

### ReportGenerator Class Methods

#### Public Methods

**`generate_weekly_report(send_email: bool = True) -> Dict[str, Any]`**

Main entry point. Generates complete report and optionally sends email.

Returns:
```python
{
    'success': True,
    'products_analyzed': 5,
    'period_start': '2026-03-04T00:00:00',
    'period_end': '2026-03-11T23:59:59',
    'charts_generated': 3,
    'html_size': 48576,
    'email_sent': True
}
```

#### Private Methods

**`_generate_product_report(product, start_date, end_date) -> Dict`**
- Queries prices for product in date range
- Calculates statistics (min/max/avg/trend)
- Computes savings opportunities
- Counts alerts sent
- Returns report dictionary

**`_get_scraper_statistics(start_date, end_date) -> Dict`**
- Queries scraper runs in period
- Calculates success/failure counts
- Computes success rate and average duration
- Returns statistics dictionary

**`_generate_charts(product_reports) -> Dict[str, str]`**
- Decides which charts to generate based on data
- Creates price history charts (1-3 products individual)
- Creates comparison chart (4+ products)
- Creates savings chart (if savings exist)
- Returns dict mapping chart names to base64 PNG strings

**`_generate_price_chart(report) -> str`**
- Creates matplotlib figure for single product
- Plots price line with markers
- Annotates min/max prices with arrows and boxes
- Adds average dashed line
- Formats dates on x-axis
- Converts to base64 PNG and returns

**`_generate_price_comparison_chart(product_reports) -> str`**
- Creates grouped bar chart
- Takes top 10 products if more than 10
- Creates three bars per product (current/min/max)
- Formats with rotated labels and legend
- Converts to base64 PNG and returns

**`_generate_savings_chart(product_reports) -> str`**
- Filters products with savings > 0
- Sorts by savings amount (descending)
- Takes top N deals (configurable)
- Creates horizontal bar chart with color coding
- Adds percentage labels
- Converts to base64 PNG and returns

**`_create_html_report(product_reports, scraper_stats, charts, start_date, end_date) -> str`**
- Calculates overall statistics
- Identifies best deal
- Generates HTML with embedded CSS
- Inserts chart images as base64 data URIs
- Creates product cards with stats
- Returns complete HTML string

**`_send_report_email(html_content, start_date, end_date) -> Dict`**
- Loads SMTP configuration
- Creates MIME multipart message
- Attaches plain text and HTML versions
- Sends via SMTP with TLS
- Returns send result dictionary

### Chart Generation Technical Details

**Matplotlib Configuration:**
```python
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for servers
```

**Base64 Encoding:**
```python
buffer = io.BytesIO()
plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
buffer.seek(0)
image_base64 = base64.b64encode(buffer.read()).decode()
plt.close(fig)
```

**HTML Embedding:**
```html
<img src="data:image/png;base64,{image_base64}" alt="Price Chart">
```

### Email Delivery

**Uses same SMTP settings as alerts:**
- SMTP server and port from `alerts.email`
- Credentials from `.env` file
- TLS encryption
- Multiple recipients supported

**Message Structure:**
```
MIMEMultipart('alternative')
├── Part 1: text/plain (fallback)
└── Part 2: text/html (main content with charts)
```

---

## 🧪 Testing

### Manual Testing

**1. Generate Test Report:**
```bash
python main.py generate-report --no-email
```

This generates the report without sending email, useful for:
- Verifying chart generation works
- Checking statistics calculations
- Testing with different data volumes

**2. Send Test Report:**
```bash
python main.py generate-report
```

Generates and sends report via email. Check:
- Email received in inbox
- Charts display correctly
- Links work properly
- Responsive design on mobile

**3. Test from Python:**
```python
from reports.report_generator import ReportGenerator
from database.connection import get_session
from utils.config import load_config

config = load_config()

with get_session() as session:
    generator = ReportGenerator(config, session)
    
    # Generate without sending
    result = generator.generate_weekly_report(send_email=False)
    print(result)
    
    # Check HTML output
    html = generator._create_html_report([], {}, {}, datetime.now(), datetime.now())
    with open('test_report.html', 'w', encoding='utf-8') as f:
        f.write(html)
```

### Integration Testing

**Test Scheduler Integration:**
```bash
# Start scheduler
python main.py start --foreground

# In logs, you should see:
# "Added weekly report job: SUN at 20:00 (next run: 2026-03-14 20:00:00)"
```

**Verify Next Run Time:**
```bash
python main.py list-jobs
```

Expected output:
```
Scheduled Jobs (2):

Job: Automated Price Scraping
  ID: scraping_job
  Next Run: 2026-03-11 19:00:00
  Trigger: interval[0:04:00:00]

Job: Weekly Price Report
  ID: weekly_report_job
  Next Run: 2026-03-14 20:00:00
  Trigger: cron[day_of_week='6', hour='20', minute='0']
```

### Data Scenarios

**Test with Different Data Volumes:**

1. **No Data**: Should return error message
2. **1-3 Products**: Individual price charts
3. **4+ Products**: Comparison chart instead
4. **No Savings**: Savings chart should be omitted
5. **No Alerts**: Alert count should be 0
6. **Failed Scrapes**: Scraper stats should show failures

---

## 📝 Logs

### Report Generation Logs

**Location:** `logs/price_tracker.log`

**Successful Generation:**
```
2026-03-11 20:00:00 - INFO - ================================================
2026-03-11 20:00:00 - INFO - WEEKLY REPORT JOB STARTED
2026-03-11 20:00:00 - INFO - ================================================
2026-03-11 20:00:00 - INFO - Generating weekly price report...
2026-03-11 20:00:01 - INFO - Report period: 2026-03-04 to 2026-03-11
2026-03-11 20:00:01 - INFO - Analyzing 5 active products
2026-03-11 20:00:01 - INFO - Generated 3 charts
2026-03-11 20:00:02 - INFO - Connecting to SMTP server smtp.gmail.com:587
2026-03-11 20:00:03 - INFO - Report email sent to 1 recipients
2026-03-11 20:00:03 - INFO - Report generated: 5 products, 3 charts
2026-03-11 20:00:03 - INFO - Report email sent successfully
2026-03-11 20:00:03 - INFO - ================================================
2026-03-11 20:00:03 - INFO - WEEKLY REPORT JOB COMPLETED
2026-03-11 20:00:03 - INFO - Duration: 3.45 seconds
2026-03-11 20:00:03 - INFO - ================================================
2026-03-11 20:00:03 - INFO - Next scheduled report: 2026-03-18 20:00:00
```

**Error Scenarios:**
```
# No products to report on
- WARNING - No active products found

# Email not configured
- WARNING - Email not enabled in configuration

# SMTP authentication failure
- ERROR - SMTP authentication failed: (535, 'Username and Password not accepted')

# Chart generation error
- ERROR - Error generating price chart: ...
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. **Charts Not Displaying in Email**

**Problem:** Email shows broken image icons instead of charts.

**Solutions:**
- Gmail may block base64 images. Try another client (Outlook, Apple Mail).
- Check chart generation succeeded in logs.
- Verify DPI and size settings aren't too large.
- Test with `--no-email` flag and inspect HTML.

**Workaround:**
```python
# In report_generator.py, reduce chart DPI
self.dpi = self.report_config.get('dpi', 80)  # Lower DPI
```

#### 2. **Report Not Being Sent**

**Problem:** Report generates but email not received.

**Checks:**
- Is `reports.enabled: true` in config.yaml?
- Is `reports.send_email: true`?
- Is `alerts.email.enabled: true`?
- Are SMTP credentials correct in `.env`?
- Check spam folder

**Debug:**
```bash
# Test email configuration
python main.py test-alerts

# Generate without email
python main.py generate-report --no-email
```

#### 3. **Matplotlib Errors**

**Problem:** ImportError or display errors.

**Solution:**
```bash
# Ensure matplotlib installed
pip install matplotlib

# If display errors on server:
export MPLBACKEND=Agg
python main.py generate-report
```

Or verify in code:
```python
import matplotlib
matplotlib.use('Agg')  # Must be before importing pyplot
import matplotlib.pyplot as plt
```

#### 4. **Memory Issues with Large Charts**

**Problem:** Report generation slow or crashes with many products.

**Solutions:**
- Reduce `chart_width` and `chart_height` in config
- Lower `dpi` setting (e.g., from 100 to 80)
- Reduce `days_to_include` (e.g., from 7 to 5)

```yaml
reports:
  chart_width: 8     # Smaller charts
  chart_height: 5
  dpi: 80            # Lower resolution
```

#### 5. **Scheduler Not Running Weekly Jobs**

**Problem:** Scraping works but reports not generated.

**Checks:**
```bash
# Check if weekly report job is added
python main.py list-jobs

# Should show:
# Job: Weekly Price Report
#   ID: weekly_report_job
#   Next Run: [future date]
```

**Verify Configuration:**
```yaml
scheduling:
  weekly_report:
    enabled: true    # Must be true
```

**Check Logs:**
```bash
# Look for scheduler errors
cat logs/scheduler.log | grep -i "report"
```

#### 6. **Incorrect Statistics**

**Problem:** Charts or stats don't match expectations.

**Debugging:**
```python
# Run standalone report generator
python -c "from reports.report_generator import main; main()"

# Check price data in database
python main.py test-db
```

**Verify price data exists:**
```bash
# Check database has recent prices
sqlite3 price_tracker.db "SELECT COUNT(*) FROM prices WHERE scraped_at > datetime('now', '-7 days')"
```

---

## 🔄 Customization

### Changing Report Schedule

Edit `config.yaml`:

```yaml
scheduling:
  weekly_report:
    enabled: true
    day_of_week: "fri"   # Change to Friday
    hour: 17             # Change to 5 PM
    minute: 30           # Change to 5:30 PM
```

Restart scheduler:
```bash
python main.py restart
```

### Customizing Report Content

**Change Number of Days:**
```yaml
reports:
  days_to_include: 14  # Change from 7 to 14 days
```

**Change Top Deals Count:**
```yaml
reports:
  top_deals_count: 10  # Show top 10 instead of 5
```

**Disable Email Sending:**
```yaml
reports:
  send_email: false    # Generate but don't send
```

### Modifying HTML Template

Edit `reports/report_generator.py`, method `_create_html_report()`:

**Change Colors:**
```python
# Find gradient background
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

# Change to blue:
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
```

**Add Custom Section:**
```python
html += """
    <div class="section">
        <h2 class="section-title">🎯 Custom Section</h2>
        <p>Your custom content here</p>
    </div>
"""
```

### Adding New Charts

1. **Create Chart Method:**
```python
def _generate_custom_chart(self, data):
    """Generate custom chart"""
    fig, ax = plt.subplots(figsize=(10, 6))
    # Your chart code here
    ax.plot(data)
    
    # Convert to base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode()
```

2. **Call in _generate_charts():**
```python
def _generate_charts(self, product_reports):
    charts = {}
    # ... existing charts ...
    charts['custom'] = self._generate_custom_chart(data)
    return charts
```

3. **Add to HTML:**
```python
if 'custom' in charts and charts['custom']:
    html += f"""
        <div class="chart">
            <img src="data:image/png;base64,{charts['custom']}" alt="Custom Chart">
        </div>
    """
```

---

## 📦 Dependencies

Phase 5 adds these new dependencies (already in `requirements.txt`):

```txt
matplotlib>=3.7.0      # Chart generation
```

All other dependencies from previous phases:
- SQLAlchemy (database)
- APScheduler (scheduling)
- requests (HTTP)
- beautifulsoup4 (parsing)
- smtplib (email, built-in)

---

## 🎓 Learning Resources

### Matplotlib Documentation
- Official docs: https://matplotlib.org/stable/index.html
- Gallery: https://matplotlib.org/stable/gallery/index.html
- Tutorials: https://matplotlib.org/stable/tutorials/index.html

### HTML Email Best Practices
- Inline CSS (all styles in `style` tags)
- Responsive design with media queries
- Base64 image embedding for compatibility
- Plain text alternative for accessibility

### APScheduler Cron
- Cron trigger docs: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
- Day of week: 0=Monday, 6=Sunday
- Use timezone-aware scheduling

---

## ✅ Phase 5 Checklist

- [x] Create ReportGenerator class
- [x] Implement price statistics calculation
- [x] Add chart generation (3 types)
- [x] Create HTML email template
- [x] Add base64 image embedding
- [x] Implement SMTP email sending
- [x] Add generate-report CLI command
- [x] Integrate with scheduler
- [x] Add weekly scheduling
- [x] Update configuration
- [x] Add comprehensive documentation
- [x] Test report generation
- [x] Test email delivery
- [x] Test chart rendering
- [x] Verify scheduler integration

---

## 🚀 Next Steps

**Phase 6: Refinements & Polish** (Coming Next)

Focus areas:
1. Error handling improvements
2. Performance optimizations
3. Additional chart types
4. PDF report generation (optional)
5. Report customization options
6. Dashboard/web interface (stretch goal)
7. Code cleanup and documentation
8. Final testing and bug fixes

---

## 📞 Support

For issues or questions about Phase 5:

1. Check logs in `logs/price_tracker.log`
2. Verify configuration in `config.yaml`
3. Test email with `python main.py test-alerts`
4. Generate report manually: `python main.py generate-report`
5. Check this documentation's Troubleshooting section

---

**Phase 5 Complete!** 🎉

The Price Tracker now has comprehensive weekly reporting with beautiful charts and statistics. Progress: **5/6 phases complete (83%)**.
