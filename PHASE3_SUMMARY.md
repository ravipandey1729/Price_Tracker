# Phase 3 Complete: Automatic Job Scheduling

## 📋 Summary
Phase 3 adds automatic scheduling capabilities so your price tracker runs continuously in the background, scraping prices at configured intervals without manual intervention.

---

## ✅ What Was Built

### 1. **Job Scheduler (APScheduler Integration)**
**File:** `scheduler/job_scheduler.py` (15,200 bytes)

**Purpose:** Manages automated scraping jobs using APScheduler with interval-based or cron-based scheduling.

**Key Features:**
- **Interval Scheduling:** Run every N hours (e.g., every 4 hours)
- **Cron Scheduling:** Specific times (e.g., "0 9 * * *" = daily at 9 AM)
- **Blocking & Background Modes:** Run in foreground or as daemon
- **Job Persistence:** Survives crashes with misfire handling
- **Event Listeners:** Tracks job execution and failures
- **Graceful Shutdown:** Handles Ctrl+C and SIGTERM

**How It Works:**
```python
from scheduler.job_scheduler import PriceTrackerScheduler
from utils.config import load_config

config = load_config()

# Create scheduler
scheduler = PriceTrackerScheduler(config, blocking=True)

# Start (blocks until stopped)
scheduler.start()
```

**Configuration (config.yaml):**
```yaml
scheduler:
  scrape_interval_hours: 4  # Run every 4 hours
  # OR use cron:
  # scrape_cron: "0 9,21 * * *"  # Daily at 9 AM and 9 PM
```

**Job Execution Flow:**
```
Scheduler starts → Add scraping job → Set trigger (interval/cron)
         ↓
  Wait for trigger time
         ↓
Execute _run_scraping_job()
  - Load database session
  - Create orchestrator
  - Run all scrapers in parallel
  - Save results to database
  - Log summary
         ↓
  Calculate next run time
         ↓
  Wait again...
```

**misfire Handling:**
- If scheduler is down when job should run:
  - `coalesce=True`: Combine missed runs into one
  - `misfire_grace_time=300`: 5-minute grace period

**Example Output:**
```
2024-01-15 10:00:00 | INFO | ======================================
2024-01-15 10:00:00 | INFO | SCHEDULED SCRAPING JOB STARTED
2024-01-15 10:00:00 | INFO | ======================================
2024-01-15 10:00:23 | INFO | ✓ Successfully scraped prod_001 from Amazon ($19.99)
2024-01-15 10:00:25 | INFO | ✓ Successfully scraped prod_001 from eBay ($18.50)
...
2024-01-15 10:01:15 | INFO | SCHEDULED SCRAPING JOB COMPLETED
2024-01-15 10:01:15 | INFO | Total products: 10
2024-01-15 10:01:15 | INFO | Successful: 8, Failed: 2
2024-01-15 10:01:15 | INFO | Duration: 75.3 seconds
2024-01-15 10:01:15 | INFO | Next scheduled run: 2024-01-15 14:00:00
```

**Why it matters:** This is the automation engine. Once started, it runs 24/7 checking prices at configured intervals.

---

### 2. **Daemon Manager (Background Process Control)**
**File:** `scheduler/daemon_manager.py` (12,800 bytes)

**Purpose:** Manages the scheduler as a background daemon process with PID file handling and process supervision.

**Key Features:**
- **Start in Background:** Spawn detached process that runs after terminal closes
- **PID File Management:** Track running process
- **Process Monitoring:** Check if scheduler is running, get CPU/memory usage
- **Graceful Stop:** Terminate gracefully, force kill if needed
- **Restart:** Stop and start in one command
- **Status Reporting:** Detailed process information

**Architecture:**
```
Your Terminal
      │
      │ python main.py start
      │
      ▼
SchedulerDaemon.start(background=True)
      │
      ├─ Write PID file (scheduler.pid)
      │
      ├─ Create _daemon_runner.py script
      │
      ├─ Spawn subprocess (DETACHED_PROCESS on Windows)
      │    └─ Runs: python _daemon_runner.py
      │         └─ Loads config → Creates PriceTrackerScheduler → scheduler.start()
      │
      └─ Return to terminal (process runs in background)

Background Process (PID stored in scheduler.pid)
      │
      ├─ Logs to logs/scheduler.log
      │
      ├─ Runs scraping jobs at intervals
      │
      └─ Continues running even if you close terminal
```

**Usage:**
```python
from scheduler.daemon_manager import SchedulerDaemon
from utils.config import load_config

config = load_config()
daemon = SchedulerDaemon(config)

# Start in background
daemon.start(foreground=False)  # Returns immediately

# Check if running
if daemon.is_running():
    print(f"Scheduler is running (PID: {daemon.get_pid()})")

# Get detailed status
status = daemon.get_status()
print(f"CPU: {status['cpu_percent']}%")
print(f"Memory: {status['memory_mb']} MB")
print(f"Uptime: {status['uptime_seconds']} seconds")

# Stop
daemon.stop(timeout=10)  # Wait up to 10 seconds for graceful shutdown
```

**PID File (scheduler.pid):**
```
12345
```
Simple text file storing just the process ID. Used to track the running daemon.

**Process Lifecycle:**
```
Start:
  1. Check if already running (read PID file)
  2. If running, refuse to start
  3. Create daemon runner script
  4. Spawn detached subprocess
  5. Write PID to file
  6. Return to user

Stop:
  1. Read PID from file
  2. Check if process exists
  3. Send SIGTERM (graceful termination)
  4. Wait up to timeout seconds
  5. If still running, send SIGKILL (force)
  6. Remove PID file

Status:
  1. Read PID from file
  2. Query process using psutil
  3. Return: CPU, memory, uptime, status
```

**Windows-Specific Details:**
- Uses `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags
- Process runs independently of parent terminal
- Survives terminal closure

**Unix-like Systems:**
- Uses `start_new_session=True`
- Similar detached behavior

**Why it matters:** This lets you start the scheduler and forget about it. It runs 24/7 monitoring prices, even when you're not logged in.

---

### 3. **CLI Commands (Scheduler Management)**
**File:** `main.py` (updated, now ~450 lines)

**New Commands Added:**

#### **`python main.py start`**
Start the scheduler daemon in background.

**Options:**
- `--foreground` - Run in foreground (blocks until Ctrl+C)

**Examples:**
```bash
# Start in background (recommended)
$ python main.py start

Starting Scheduler
==================
2024-01-15 10:00:00 | INFO | Starting scheduler...
✓ Scheduler started successfully in background
  PID: 12345
  Log file: C:\...\logs\scheduler.log

Scheduler will run scrapers at configured intervals.
Use 'python main.py status' to check status
Use 'python main.py stop' to stop the scheduler

# Start in foreground (for testing/debugging)
$ python main.py start --foreground

Starting scheduler in foreground mode...
Press Ctrl+C to stop

2024-01-15 10:00:00 | Scheduler started
2024-01-15 10:00:00 | Next scrape: 2024-01-15 14:00:00
```

#### **`python main.py stop`**
Stop the running scheduler daemon.

**Options:**
- `--timeout N` - Wait up to N seconds for graceful shutdown (default: 10)

**Example:**
```bash
$ python main.py stop

Stopping Scheduler
==================
2024-01-15 10:05:00 | INFO | Stopping scheduler (PID: 12345)...
✓ Scheduler stopped successfully
```

#### **`python main.py restart`**
Restart the scheduler (stop + start).

**Example:**
```bash
$ python main.py restart

Restarting Scheduler
====================
2024-01-15 10:10:00 | INFO | Restarting scheduler...
✓ Scheduler restarted successfully
  PID: 12350
  Log file: C:\...\logs\scheduler.log
```

#### **`python main.py status`**
Show detailed scheduler status.

**Options:**
- `--verbose` or `-v` - Show recent log entries

**Examples:**
```bash
# Basic status
$ python main.py status

Scheduler Status
================

Running: True
PID: 12345
Status: running
CPU: 0.5%
Memory: 45.3 MB
Started: 2024-01-15T10:00:00
Uptime: 2h 15m

Log file: C:\...\logs\scheduler.log
PID file: C:\...\scheduler.pid

# Verbose (shows last 10 log lines)
$ python main.py status --verbose

[... status ...]

Recent log entries:
  2024-01-15 12:00:00 | INFO | SCHEDULED SCRAPING JOB STARTED
  2024-01-15 12:00:23 | INFO | ✓ Successfully scraped prod_001 from Amazon
  2024-01-15 12:00:25 | INFO | ✓ Successfully scraped prod_001 from eBay
  ...
```

#### **`python main.py list-jobs`**
List scheduled jobs and configuration.

**Example:**
```bash
$ python main.py list-jobs

Scheduled Jobs
==============

Scheduler Configuration:
  Scrape Interval: Every 4 hours

Scraping Settings:
  Max Workers: 3
  Timeout: 30s

Products to Track: 2
  • prod_001: Sony WH-1000XM5 Headphones
    Sites: Amazon, eBay
  • prod_002: iPhone 15 Pro
    Sites: Amazon, eBay
```

**Why it matters:** Simple CLI gives you full control over the background scheduler.

---

### 4. **Updated Dependencies**
**File:** `requirements.txt` (updated)

**Added:**
```python
pytz>=2023.3              # Timezone support for APScheduler
psutil>=5.9.0             # Process and system utilities for daemon management
```

**Why needed:**
- `pytz`: APScheduler requires timezone-aware scheduling
- `psutil`: Cross-platform process management (CPU, memory, process control)

**Installation:**
```bash
pip install pytz psutil
# OR
pip install -r requirements.txt
```

---

### 5. **Updated .gitignore**
**File:** `.gitignore` (updated)

**Added:**
```
# Scheduler
scheduler.pid
scheduler/_daemon_runner.py
```

**Why:**
- `scheduler.pid`: Runtime file, don't commit
- `_daemon_runner.py`: Auto-generated script, don't commit

---

## 🗂️ File Structure
```
Price Tracker/
├── scheduler/                      # ← NEW Phase 3
│   ├── __init__.py
│   ├── job_scheduler.py            # APScheduler integration (15,200 bytes)
│   ├── daemon_manager.py           # Background process control (12,800 bytes)
│   └── _daemon_runner.py           # Auto-generated runner script (created on first start)
├── main.py                         # ← UPDATED CLI with start/stop/status/restart/list-jobs
├── requirements.txt                # ← UPDATED Added pytz, psutil
├── .gitignore                      # ← UPDATED Added scheduler.pid
├── scheduler.pid                   # Runtime PID file (created when scheduler runs)
└── logs/
    └── scheduler.log               # Scheduler output (created automatically)
```

**Total New Code:** ~28,000 bytes across 2 files + CLI updates

---

## 🚀 How to Use Phase 3

### **Setup**

1. **Install new dependencies:**
   ```bash
   pip install pytz psutil
   ```

2. **Configure schedule (config.yaml):**
   ```yaml
   scheduler:
     scrape_interval_hours: 4  # Every 4 hours
     # OR use cron for specific times:
     # scrape_cron: "0 */6 * * *"  # Every 6 hours
     # scrape_cron: "0 9,21 * * *"  # Daily at 9 AM and 9 PM
   ```

3. **Add products to track (config.yaml):**
   ```yaml
   products:
     - id: prod_001
       name: "Sony WH-1000XM5"
       urls:
         Amazon: "https://amazon.com/..."
         eBay: "https://ebay.com/..."
   ```

### **Start Tracking Prices Automatically**

```bash
# 1. Start scheduler
$ python main.py start

✓ Scheduler started in background
  PID: 12345
  Log file: logs/scheduler.log

# 2. Check it's running
$ python main.py status

Running: True
PID: 12345
CPU: 0.5%, Memory: 45 MB
Uptime: 5m

# 3. Watch the logs (optional)
$ tail -f logs/scheduler.log

# Or on Windows PowerShell:
$ Get-Content logs/scheduler.log -Wait

# You'll see:
# 2024-01-15 10:00:00 | SCHEDULED SCRAPING JOB STARTED
# 2024-01-15 10:00:23 | ✓ Successfully scraped prod_001 from Amazon ($19.99)
# ...

# 4. Stop when needed
$ python main.py stop

✓ Scheduler stopped successfully
```

### **Typical Workflow**

```bash
# Morning: Start scheduler before work
$ python main.py start

# Evening: Check results in database
$ sqlite3 price_tracker.db
sqlite> SELECT product_id, price, source_site, scraped_at 
        FROM prices 
        ORDER BY scraped_at DESC 
        LIMIT 10;

# See scraper performance
sqlite> SELECT site_name, products_succeeded, products_failed, duration_seconds
        FROM scraper_runs
        ORDER BY started_at DESC
        LIMIT 5;

# When done: Stop scheduler
$ python main.py stop
```

---

## 📊 Scheduling Options

### **Option 1: Interval-Based (Simple)**
Run every N hours.

```yaml
scheduler:
  scrape_interval_hours: 4  # Every 4 hours
```

**Examples:**
- `1`: Every hour
- `4`: Every 4 hours (recommended for price tracking)
- `6`: Every 6 hours
- `24`: Once per day
- `0.5`: Every 30 minutes (for testing)

**When to use:** Most price tracking scenarios. Simple and reliable.

### **Option 2: Cron-Based (Specific Times)**
Run at specific times using cron syntax.

```yaml
scheduler:
  scrape_cron: "0 9,21 * * *"  # Daily at 9 AM and 9 PM
```

**Cron Syntax:**
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6, 0=Sunday)
│ │ │ │ │
* * * * *
```

**Common Examples:**
```yaml
# Every 6 hours
scrape_cron: "0 */6 * * *"

# Daily at 9 AM
scrape_cron: "0 9 * * *"

# Every weekday at 9 AM and 5 PM
scrape_cron: "0 9,17 * * 1-5"

# Every Monday at 10 AM
scrape_cron: "0 10 * * 1"
```

**When to use:** Need specific times (e.g., business hours only, avoid peak times).

---

## 🔍 Monitoring & Troubleshooting

### **Check Scheduler Status**
```bash
$ python main.py status

Running: True
PID: 12345
Status: running
CPU: 0.5%
Memory: 45.3 MB
Started: 2024-01-15T10:00:00
Uptime: 2h 15m
```

### **View Logs**
```bash
# Real-time log monitoring (PowerShell)
$ Get-Content logs/scheduler.log -Wait -Tail 20

# View last 50 lines
$ Get-Content logs/scheduler.log -Tail 50

# Search for errors
$ Select-String -Path logs/scheduler.log -Pattern "ERROR"
```

### **Common Issues**

#### **Scheduler won't start - already running**
```bash
$ python main.py start
WARNING | Scheduler is already running (PID: 12345)

# Solution: Stop first
$ python main.py stop
$ python main.py start
```

#### **Scheduler shows running but not scraping**
```bash
# Check status
$ python main.py status --verbose

# Check configuration
$ python main.py list-jobs

# Check logs for errors
$ Get-Content logs/scheduler.log -Tail 50
```

#### **Scheduler stopped unexpectedly**
```bash
# Check logs for crash reason
$ Get-Content logs/scheduler.log -Tail 100 | Select-String "ERROR"

# Restart
$ python main.py restart
```

#### **High CPU/Memory usage**
```bash
# Check status
$ python main.py status

CPU: 25.0%  # Too high!
Memory: 500 MB  # Too high!

# Reduce parallel workers in config.yaml
scraping:
  max_workers: 1  # Instead of 3

# Restart
$ python main.py restart
```

---

## 💡 How the Pieces Fit Together

```
┌──────────────────────────────────────────────────────────────┐
│  User Command: python main.py start                          │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  main.py: cmd_start()                                        │
│  - Load config                                               │
│  - Create SchedulerDaemon                                    │
│  - Call daemon.start(foreground=False)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SchedulerDaemon.start(background=True)                      │
│  - Check not already running                                 │
│  - Create _daemon_runner.py script                           │
│  - Spawn subprocess: python _daemon_runner.py                │
│  - Write PID to scheduler.pid                                │
│  - Return (user gets terminal back)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         └─── Background Process Spawned ────┐
                                                              │
                                                              ▼
┌──────────────────────────────────────────────────────────────┐
│  _daemon_runner.py (Subprocess PID: 12345)                   │
│  - Load config.yaml                                          │
│  - Create PriceTrackerScheduler(blocking=True)               │
│  - Call scheduler.start() → BLOCKS                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  PriceTrackerScheduler                                       │
│  - Initialize BackgroundScheduler/BlockingScheduler          │
│  - Add scraping job with IntervalTrigger                     │
│  - Register event listeners                                  │
│  - Start APScheduler                                         │
│  - Wait for trigger...                                       │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ (Every 4 hours)
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  _run_scraping_job()                                         │
│  1. Open database session                                    │
│  2. Create ScraperOrchestrator                               │
│  3. Call orchestrator.run_all_scrapers()                     │
│     ├─ Read products from config                             │
│     ├─ Create 3 parallel workers                             │
│     ├─ Scrape Amazon, eBay, etc.                             │
│     └─ Save to database (prices + scraper_runs)              │
│  4. Log results                                              │
│  5. Return                                                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         └─── Back to APScheduler ────┐
                                                       │
                                                       ▼
                         Schedule next run (4 hours from now)
                         Wait...
```

**Key Points:**
1. User runs `python main.py start` → Returns immediately
2. Background process spawned → Runs independently
3. APScheduler triggers scraping job every 4 hours
4. Each scrape stores results in database
5. Process continues running 24/7 until stopped

---

## 🎯 Phase 3 Complete!

**What You Can Do Now:**
```bash
# 1. Start automatic scraping
$ python main.py start

# 2. Check status anytime
$ python main.py status

# 3. View scheduled jobs
$ python main.py list-jobs

# 4. Query price history
$ sqlite3 price_tracker.db
sqlite> SELECT * FROM prices ORDER BY scraped_at DESC LIMIT 10;

# 5. Stop when needed
$ python main.py stop
```

**Next:** Phase 4 will add email and Slack alerts when prices drop below thresholds!

---

## ⚡ Quick Reference

| Command      | What It Does                      |
| ------------ | --------------------------------- |
| `start`      | Start scheduler in background     |
| `stop`       | Stop scheduler                    |
| `restart`    | Restart scheduler                 |
| `status`     | Show detailed status              |
| `status -v`  | Show status + recent logs         |
| `list-jobs`  | Show scheduled jobs & config      |

**Files:**
- `scheduler.pid` - Process ID file
- `logs/scheduler.log` - Scheduler output
- `config.yaml` - Schedule configuration (scrape_interval_hours)

**Behavior:**
- Runs 24/7 in background
- Survives terminal closure
- Starts scraping immediately when started
- Then runs at configured intervals
- Stores all results in database
