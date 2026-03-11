# Phase 4: Email and Slack Alerts - Complete Implementation Guide

**Status:** ✅ Complete  
**Date:** March 11, 2026  
**Version:** v0.4.0

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features Implemented](#features-implemented)
3. [Architecture](#architecture)
4. [Alert Manager Deep Dive](#alert-manager-deep-dive)
5. [Configuration](#configuration)
6. [CLI Commands](#cli-commands)
7. [Email Setup](#email-setup)
8. [Slack Setup](#slack-setup)
9. [Usage Examples](#usage-examples)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Phase 4 adds automated price drop alerts to the Price Tracker. When prices fall below configured thresholds, the system automatically sends notifications via email and/or Slack. Alerts are integrated with the scheduler from Phase 3, so they run automatically after each scraping job.

### What Was Built

- **Alert Manager** (`alerts/alert_manager.py`): Core alert detection and notification system
- **Email Integration**: HTML and plain text email notifications via SMTP
- **Slack Integration**: Rich formatted messages via incoming webhooks
- **Threshold Management**: CLI commands to add, list, and remove price thresholds
- **Scheduler Integration**: Automatic alert checking after each scrape
- **Cooldown System**: Prevents alert spam with configurable cooldown periods
- **Alert History**: Tracks all sent alerts in database

---

## Features Implemented

### ✅ Alert Manager Module

**File:** `alerts/alert_manager.py` (780+ lines)

**Key Classes:**
- `AlertManager`: Main class for alert detection and notification

**Key Methods:**
- `check_and_send_alerts()`: Main entry point, checks all thresholds
- `_check_threshold()`: Checks individual threshold against latest price
- `_send_email_alert()`: Sends HTML email via SMTP
- `_send_slack_alert()`: Sends formatted message to Slack webhook
- `_is_cooldown_expired()`: Prevents duplicate alerts within cooldown period
- `_record_alert()`: Saves sent alert to database

### ✅ Email Notifications

**Features:**
- HTML emails with formatted price information
- Plain text fallback for email clients that don't support HTML
- Shows old price, new price, and discount percentage
- Includes direct links to product on all configured sites
- Professional styling with colors and formatting

**Email Content:**
- Subject: "🔔 Price Drop Alert: [Product Name]"
- Product name and source site
- Old price (strikethrough) and new price (highlighted)
- Discount percentage if old price available
- Threshold that was triggered
- Clickable links to view product

### ✅ Slack Notifications

**Features:**
- Rich Block Kit formatting with sections and buttons
- Color-coded messages based on alert type
- Direct "View on [Site]" buttons for each URL
- Compact layout optimized for mobile

**Slack Content:**
- Header: "🔔 Price Drop Alert!"
- Product name and source
- Price comparison with formatting
- Action buttons to view product

### ✅ Scheduler Integration

**File:** `scheduler/job_scheduler.py` (updated)

**Integration Points:**
- Import: `from alerts.alert_manager import AlertManager`
- After successful scraping, calls `alert_manager.check_and_send_alerts()`
- Logs alert statistics: alerts sent, errors

**Workflow:**
1. Scheduler runs scraping job
2. Orchestrator scrapes all sites and saves prices
3. Alert manager checks all thresholds
4. Sends email/Slack notifications for triggered thresholds
5. Records alerts in database

### ✅ CLI Commands

**File:** `main.py` (updated with 4 new commands)

| Command | Description | Example |
|---------|-------------|---------|
| `add-threshold` | Add price threshold | `python main.py add-threshold prod_001 299.99` |
| `list-thresholds` | List all thresholds | `python main.py list-thresholds` |
| `remove-threshold` | Remove threshold | `python main.py remove-threshold --id 1` |
| `test-alerts` | Test alert system | `python main.py test-alerts` |

### ✅ Configuration Updates

**Files Updated:**
- `config.yaml`: Added alerts section with email/Slack settings
- `utils/config.py`: Updated to inject EMAIL_* and SLACK_* environment variables
- `.env.example`: Already had email and Slack placeholders

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     SCHEDULED SCRAPING JOB                       │
│                                                                   │
│  1. APScheduler triggers job every 4 hours                       │
│  2. ScraperOrchestrator runs all scrapers                        │
│  3. Prices saved to database                                     │
└───────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ALERT CHECKING PHASE                          │
│                                                                   │
│  AlertManager.check_and_send_alerts()                            │
│  ├─ Query all thresholds from database                           │
│  ├─ For each threshold:                                          │
│  │   ├─ Get latest price for product                             │
│  │   ├─ Compare price to threshold                               │
│  │   ├─ Check cooldown period                                    │
│  │   └─ If triggered:                                            │
│  │       ├─ Send email (if enabled)                              │
│  │       ├─ Send Slack (if enabled)                              │
│  │       └─ Record alert in database                             │
│  └─ Return statistics (total sent, errors)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Database Tables Used

**thresholds:**
- Stores price thresholds configured by user
- Fields: product_id, threshold_price, alert_type (email/slack/all)

**alerts_sent:**
- Records all sent alerts for history and cooldown
- Fields: product_id, old_price, new_price, threshold_price, alert_type, sent_at

**prices:**
- Queried for latest price data
- Used to compare against thresholds

**products:**
- Accessed for product name and URLs

### Alert Manager Components

```python
AlertManager
├── __init__()                    # Load config, setup email/Slack
├── check_and_send_alerts()       # Main entry point
│   └── _check_threshold()        # Check individual threshold
│       ├── _is_cooldown_expired() # Prevent spam
│       ├── _send_alert()          # Send to configured channels
│       │   ├── _send_email_alert()
│       │   │   ├── _create_email_html()
│       │   │   └── _create_email_text()
│       │   └── _send_slack_alert()
│       │       └── _create_slack_message()
│       └── _record_alert()        # Save to database
└── _calculate_discount()          # Calculate % discount
```

---

## Alert Manager Deep Dive

### Initialization

```python
alert_manager = AlertManager(config, db_session)
```

**What it does:**
1. Loads alert configuration from `config['alerts']`
2. Checks if email/Slack are enabled
3. Sets cooldown period (default: 24 hours)
4. Logs initialization status

**Configuration structure:**
```python
config['alerts'] = {
    'enabled': True,                    # Master switch
    'cooldown_hours': 24,               # Cooldown period
    'email': {
        'enabled': True,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_username': '...',         # From .env
        'smtp_password': '...',         # From .env
        'from_email': '...',            # From .env
        'to_emails': ['user@example.com']
    },
    'slack': {
        'enabled': False,
        'webhook_url': '...'            # From .env
    }
}
```

### Alert Detection Logic

**Step 1: Query Thresholds**
```python
thresholds = db_session.query(Threshold).all()
```

**Step 2: For Each Threshold**
```python
latest_price = db_session.query(Price)\
    .filter(Price.product_id == product.id)\
    .order_by(Price.scraped_at.desc())\
    .first()

if latest_price.price >= threshold.threshold_price:
    # Price is above threshold, no alert
    return False
```

**Step 3: Check Cooldown**
```python
cooldown_time = datetime.now() - timedelta(hours=cooldown_hours)
recent_alert = db_session.query(AlertSent)\
    .filter(AlertSent.product_id == product_id)\
    .filter(AlertSent.sent_at > cooldown_time)\
    .first()

if recent_alert:
    # Alert recently sent, skip
    return False
```

**Step 4: Send Notifications**
```python
# Email
if alert_type in ['email', 'all'] and email_enabled:
    _send_email_alert(message_data)

# Slack
if alert_type in ['slack', 'all'] and slack_enabled:
    _send_slack_alert(message_data)
```

**Step 5: Record Alert**
```python
alert = AlertSent(
    product_id=product.id,
    old_price=previous_price,
    new_price=current_price,
    threshold_price=threshold_price,
    alert_type=alert_type,
    sent_at=datetime.now()
)
db_session.add(alert)
db_session.commit()
```

### Email Implementation

**SMTP Configuration:**
```python
server = smtplib.SMTP(smtp_server, smtp_port)
server.starttls()  # Enable TLS encryption
server.login(smtp_username, smtp_password)
server.send_message(msg)
```

**Message Structure:**
```python
msg = MIMEMultipart('alternative')
msg['Subject'] = f"🔔 Price Drop Alert: {product_name}"
msg['From'] = from_email
msg['To'] = ', '.join(to_emails)

# Attach plain text version
msg.attach(MIMEText(text_body, 'plain'))

# Attach HTML version
msg.attach(MIMEText(html_body, 'html'))
```

**HTML Email Template:**
- Bootstrap-style responsive container
- Green header with alert icon
- Price comparison box with strikethrough old price
- Highlighted new price in large font
- Discount percentage in red
- Bulleted list of product URLs
- Footer with timestamp

### Slack Implementation

**Webhook POST:**
```python
response = requests.post(
    webhook_url,
    json=slack_message,
    timeout=10
)
```

**Block Kit Message:**
```json
{
  "blocks": [
    {
      "type": "header",
      "text": {"type": "plain_text", "text": "🔔 Price Drop Alert!"}
    },
    {
      "type": "section",
      "fields": [
        {"type": "mrkdwn", "text": "*Product:*\nPlayStation 5"},
        {"type": "mrkdwn", "text": "*Old Price:*\n~$499.99~"},
        {"type": "mrkdwn", "text": "*New Price:*\n:moneybag: $449.99"}
      ]
    },
    {
      "type": "actions",
      "elements": [
        {
          "type": "button",
          "text": {"type": "plain_text", "text": "View on Amazon"},
          "url": "https://amazon.com/..."
        }
      ]
    }
  ]
}
```

### Cooldown System

**Purpose:** Prevent sending duplicate alerts for the same product within a short time period.

**Implementation:**
```python
cooldown_time = datetime.now() - timedelta(hours=24)
recent_alert = db_session.query(AlertSent)\
    .filter(AlertSent.product_id == product_id)\
    .filter(AlertSent.alert_type == alert_type)\
    .filter(AlertSent.sent_at > cooldown_time)\
    .first()

return recent_alert is None  # True if cooldown expired
```

**Configurable:** Set `cooldown_hours` in config.yaml (default: 24 hours)

**Per Alert Type:** Separate cooldowns for email vs Slack alerts

---

## Configuration

### config.yaml

```yaml
# ============================================================================
# ALERTING
# ============================================================================
alerts:
  enabled: true # Master switch for all alerts
  cooldown_hours: 24 # Prevent duplicate alerts for same product within 24 hours
  
  # Email settings
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    # Credentials loaded from .env: EMAIL_USERNAME, EMAIL_PASSWORD
    # from_email: defaults to EMAIL_FROM from .env
    to_emails:
      - "your-email@example.com" # Replace with your actual email
    # Add multiple recipients:
    # - "person1@example.com"
    # - "person2@example.com"

  # Slack settings
  slack:
    enabled: false # Set to true when Slack webhook is configured
    # webhook_url loaded from .env: SLACK_WEBHOOK_URL
    channel: "#price-alerts"
    username: "Price Tracker Bot"
```

### .env File

```bash
# Email Configuration
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password-here
EMAIL_FROM=your-email@gmail.com

# Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Important:** Never commit `.env` to Git! It's in `.gitignore`.

---

## CLI Commands

### 1. Add Threshold

```bash
python main.py add-threshold <product_id> <price> [--type <email|slack|all>]
```

**Examples:**
```bash
# Add threshold for all alert types (email + Slack)
python main.py add-threshold prod_001 299.99

# Add email-only threshold
python main.py add-threshold prod_001 299.99 --type email

# Add Slack-only threshold
python main.py add-threshold prod_002 149.99 --type slack
```

**Output:**
```
============================================================
 Adding Price Threshold
============================================================
======================================================================
✓ Threshold added successfully
======================================================================
Product: PlayStation 5 Console
Threshold Price: $299.99
Alert Type: all
======================================================================

You will receive alerts when the price drops below this threshold.
```

### 2. List Thresholds

```bash
python main.py list-thresholds
```

**Output:**
```
============================================================
 Price Thresholds
============================================================

Found 2 threshold(s):

======================================================================
Threshold ID: 1
Product: PlayStation 5 Console (prod_001)
Threshold Price: $299.99
Alert Type: all
Created: 2026-03-11 10:30:45
Current Price: $449.99 (Amazon)
Above threshold by $150.00
======================================================================
Threshold ID: 2
Product: AirPods Pro (prod_002)
Threshold Price: $199.99
Alert Type: email
Created: 2026-03-11 11:15:22
Current Price: $179.99 (eBay)
⚠️  BELOW THRESHOLD - Alert should be sent!
======================================================================
```

### 3. Remove Threshold

**Option A: Remove by threshold ID**
```bash
python main.py remove-threshold --id <threshold_id>
```

**Option B: Remove by product ID and alert type**
```bash
python main.py remove-threshold --product <product_id> --type <email|slack|all>
```

**Examples:**
```bash
# Remove by ID
python main.py remove-threshold --id 1

# Remove by product and type
python main.py remove-threshold --product prod_001 --type email
```

**Output:**
```
============================================================
 Removing Price Threshold
============================================================
✓ Threshold removed successfully
Product: PlayStation 5 Console
Threshold: $299.99
Alert Type: all
```

### 4. Test Alerts

```bash
python main.py test-alerts
```

**What it does:**
1. Loads alert configuration
2. Checks if email/Slack are enabled
3. Runs alert checking manually
4. Reports results

**Output:**
```
============================================================
 Testing Alert System
============================================================
Alert Configuration:
  Email: Enabled
  Slack: Disabled
  Cooldown: 24 hours

[Alert Manager runs...]

Test Results:
  Alerts Sent: 1
  Errors: 0
```

---

## Email Setup

### Gmail Configuration

**Step 1: Enable 2-Factor Authentication**
1. Go to https://myaccount.google.com/security
2. Turn on "2-Step Verification"

**Step 2: Create App Password**
1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and your device
3. Click "Generate"
4. Copy the 16-character password

**Step 3: Update .env**
```bash
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=abcd efgh ijkl mnop  # App password from step 2
EMAIL_FROM=your-email@gmail.com
```

**Step 4: Update config.yaml**
```yaml
alerts:
  email:
    enabled: true
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    to_emails:
      - "your-email@gmail.com"
```

### Other Email Providers

**Outlook/Hotmail:**
```yaml
smtp_server: "smtp-mail.outlook.com"
smtp_port: 587
```
```bash
EMAIL_USERNAME=your-email@outlook.com
EMAIL_PASSWORD=your-password
```

**Yahoo:**
```yaml
smtp_server: "smtp.mail.yahoo.com"
smtp_port: 587
```
Requires app password: https://help.yahoo.com/kb/generate-third-party-passwords-sln15241.html

**Custom SMTP:**
```yaml
smtp_server: "mail.yourdomain.com"
smtp_port: 587  # or 465 for SSL
```

---

## Slack Setup

### Create Incoming Webhook

**Step 1: Create Slack App**
1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Name: "Price Tracker", select workspace

**Step 2: Enable Incoming Webhooks**
1. In app settings, click "Incoming Webhooks"
2. Toggle "Activate Incoming Webhooks" to ON
3. Click "Add New Webhook to Workspace"
4. Select channel (e.g., #price-alerts)
5. Click "Allow"

**Step 3: Copy Webhook URL**
```
https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

**Step 4: Update .env**
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

**Step 5: Update config.yaml**
```yaml
alerts:
  slack:
    enabled: true
    channel: "#price-alerts"
    username: "Price Tracker Bot"
```

### Test Slack Integration

```bash
# Test with curl (Windows PowerShell)
$body = @{
    text = "Test message from Price Tracker"
} | ConvertTo-Json

Invoke-RestMethod -Uri "YOUR_WEBHOOK_URL" -Method Post -Body $body -ContentType 'application/json'
```

Response should be: `ok`

---

## Usage Examples

### Complete Workflow

**1. Initialize Database**
```bash
python main.py init
```

**2. Add Thresholds**
```bash
python main.py add-threshold prod_001 299.99
python main.py add-threshold prod_002 149.99 --type email
```

**3. Start Scheduler**
```bash
python main.py start
```

**4. Monitor Alerts**
```bash
# Check scheduler status
python main.py status

# View thresholds and current prices
python main.py list-thresholds

# View recent logs
python main.py status --verbose
```

**5. Test Manually**
```bash
# Run one scrape + alert check
python main.py scrape-now

# Test alert system
python main.py test-alerts
```

### Advanced: Multiple Alert Types

**Scenario:** You want email for critical items, Slack for everything else.

```bash
# Critical item: email only
python main.py add-threshold prod_gpu 499.99 --type email

# Regular items: Slack only
python main.py add-threshold prod_mouse 29.99 --type slack

# Important item: both
python main.py add-threshold prod_laptop 999.99 --type all
```

**Configure recipients:**
```yaml
alerts:
  email:
    to_emails:
      - "personal@gmail.com"
      - "work@company.com"  # Critical alerts to multiple emails
```

---

## Testing

### Manual Testing

**Test Email (without scraping):**
```python
# Create test script: test_email.py
from alerts.alert_manager import AlertManager
from utils.config import load_config
from database.connection import get_session
from database.models import Product, Price, Threshold
from datetime import datetime

config = load_config()

with get_session() as session:
    # Create test product
    product = Product(id="test_001", name="Test Product", urls={"Amazon": "https://amazon.com"})
    session.add(product)
    session.commit()
    
    # Create test price below threshold
    price = Price(product_id="test_001", price=99.99, currency="USD", source_site="Amazon", scraped_at=datetime.now())
    session.add(price)
    
    # Create threshold
    threshold = Threshold(product_id="test_001", threshold_price=149.99, alert_type="all")
    session.add(threshold)
    session.commit()
    
    # Test alert
    alert_manager = AlertManager(config, session)
    results = alert_manager.check_and_send_alerts()
    
    print(f"Results: {results}")
```

Run: `python test_email.py`

### Integration Testing

**End-to-End Test:**
```bash
# 1. Add threshold
python main.py add-threshold prod_001 999.99

# 2. Simulate price drop (manually edit database)
sqlite3 price_tracker.db
UPDATE prices SET price = 899.99 WHERE product_id = 'prod_001' ORDER BY scraped_at DESC LIMIT 1;
.quit

# 3. Test alerts
python main.py test-alerts

# Expected: Email/Slack notification received
```

### Verifying Alerts in Database

```bash
sqlite3 price_tracker.db

# View sent alerts
SELECT * FROM alerts_sent ORDER BY sent_at DESC LIMIT 5;

# Count alerts by product
SELECT product_id, COUNT(*) as alert_count 
FROM alerts_sent 
GROUP BY product_id;

# View alerts with product names
SELECT p.name, a.old_price, a.new_price, a.threshold_price, a.sent_at
FROM alerts_sent a
JOIN products p ON a.product_id = p.id
ORDER BY a.sent_at DESC;
```

---

## Troubleshooting

### Email Not Sending

**Problem:** `Failed to send email alert: Authentication failed`

**Solutions:**
1. **Gmail:** Enable 2FA and create App Password (see Email Setup)
2. **Check credentials:** Verify `EMAIL_USERNAME` and `EMAIL_PASSWORD` in `.env`
3. **Check SMTP settings:** Confirm `smtp_server` and `smtp_port` in `config.yaml`
4. **Test manually:**
   ```python
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('your-email@gmail.com', 'app-password')
   print("Success!")
   ```

**Problem:** Email sent but not received

**Solutions:**
1. Check spam folder
2. Verify `to_emails` in `config.yaml`
3. Check email logs: `logs/price_tracker.log`

### Slack Not Posting

**Problem:** `Slack webhook failed: 404`

**Solutions:**
1. Verify webhook URL in `.env`
2. Test webhook manually:
   ```powershell
   Invoke-RestMethod -Uri "YOUR_WEBHOOK_URL" -Method Post -Body '{"text":"test"}' -ContentType 'application/json'
   ```
3. Check webhook is still active in Slack app settings

**Problem:** Message posted but not formatted

**Solutions:**
1. Slack Block Kit has size limits. Product names or URLs might be too long.
2. Check logs for JSON errors
3. Test with simpler product names

### No Alerts Triggered

**Problem:** `Alerts Sent: 0` but prices are below threshold

**Possible Causes:**
1. **Cooldown active:** Check `alerts_sent` table for recent alerts
   ```sql
   SELECT * FROM alerts_sent WHERE product_id = 'prod_001' ORDER BY sent_at DESC LIMIT 1;
   ```
2. **No prices scraped:** Check `prices` table
   ```sql
   SELECT * FROM prices WHERE product_id = 'prod_001' ORDER BY scraped_at DESC LIMIT 1;
   ```
3. **Threshold misconfigured:** Run `python main.py list-thresholds`
4. **Alerts disabled:** Check `config.yaml` → `alerts.enabled: true`

### Scheduler Not Checking Alerts

**Problem:** Scraping works but no alerts checked

**Solutions:**
1. Check `job_scheduler.py` has AlertManager import
2. View scheduler logs: `logs/scheduler.log`
3. Look for "Checking for price drop alerts..." message
4. Restart scheduler: `python main.py restart`

### Database Errors

**Problem:** `IntegrityError: NOT NULL constraint failed`

**Solutions:**
1. Make sure product exists before adding threshold
2. Check product ID matches exactly (case-sensitive)
3. Re-initialize database if corrupted: `python main.py init --force`

---

## Summary

Phase 4 is now **complete**! The Price Tracker now has:

✅ **Alert Manager** with email and Slack support  
✅ **Scheduler Integration** for automatic alert checking  
✅ **CLI Commands** for threshold management  
✅ **HTML Email** notifications with professional formatting  
✅ **Slack Webhooks** with Block Kit messages  
✅ **Cooldown System** to prevent spam  
✅ **Alert History** tracking in database  

**What's Next: Phase 5 - Weekly Reports**

The system is now fully automated and monitors prices 24/7 with instant notifications. Phase 5 will add weekly summary reports via email.

---

**Questions or Issues?**

Check the logs:
- `logs/price_tracker.log` - General logging
- `logs/scheduler.log` - Scheduler-specific logs
- `logs/scraper_errors.log` - Scraping failures

Run diagnostics:
```bash
python main.py test-db          # Test database
python main.py test-alerts      # Test alert system
python main.py list-thresholds  # View configuration
python main.py status --verbose # View recent activity
```
