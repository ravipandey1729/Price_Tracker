"""
Job Scheduler

Manages automated scraping jobs using APScheduler.
Runs scrapers at configured intervals in the background.

Features:
- Interval-based scheduling (e.g., every 4 hours)
- Cron-based scheduling (e.g., daily at 9 AM)
- Graceful start/stop with signal handling
- Job persistence across restarts
- Error recovery and logging

Usage:
    from scheduler.job_scheduler import PriceTrackerScheduler
    from utils.config import load_config
    
    config = load_config()
    scheduler = PriceTrackerScheduler(config)
    
    # Start scheduler (blocks until stopped)
    scheduler.start()
    
    # Or run in background
    scheduler.start_background()
"""

import atexit
import signal
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
from pytz import timezone as pytz_timezone

from database.connection import get_session
from scrapers.orchestrator import ScraperOrchestrator
from alerts.alert_manager import AlertManager
from utils.logging_config import get_logger


logger = get_logger(__name__)


class PriceTrackerScheduler:
    """
    Scheduler for automated price tracking jobs.
    
    Manages periodic execution of scrapers using APScheduler.
    """
    
    def __init__(self, config: Dict[str, Any], blocking: bool = False):
        """
        Initialize scheduler.
        
        Args:
            config: Configuration dictionary from config.yaml
            blocking: If True, use BlockingScheduler (for foreground). 
                     If False, use BackgroundScheduler (for background daemon)
        """
        self.config = config
        self.blocking = blocking
        
        # Create appropriate scheduler type
        if blocking:
            self.scheduler = BlockingScheduler(
                timezone=pytz_timezone('UTC'),
                job_defaults={
                    'coalesce': True,  # Combine missed runs into one
                    'max_instances': 1,  # Only one instance at a time
                    'misfire_grace_time': 300  # 5 minute grace period
                }
            )
        else:
            self.scheduler = BackgroundScheduler(
                timezone=pytz_timezone('UTC'),
                job_defaults={
                    'coalesce': True,
                    'max_instances': 1,
                    'misfire_grace_time': 300
                }
            )
        
        # Register event listeners
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        # Track scheduler state
        self.is_running = False
        
        logger.info("Initialized PriceTrackerScheduler")
    
    
    def add_scraping_job(self) -> str:
        """
        Add the main scraping job to the scheduler.
        
        Uses configuration to determine schedule:
        - scrape_interval_hours: Run every N hours
        - OR scrape_cron: Use cron expression
        
        Returns:
            Job ID
        """
        scheduler_config = self.config.get('scheduler', {})
        
        # Check for interval-based scheduling (default)
        interval_hours = scheduler_config.get('scrape_interval_hours', 4)
        
        if interval_hours:
            job = self.scheduler.add_job(
                func=self._run_scraping_job,
                trigger=IntervalTrigger(hours=interval_hours),
                id='scraping_job',
                name='Automated Price Scraping',
                replace_existing=True,
                next_run_time=datetime.now()  # Run immediately on start
            )
            
            logger.info(
                f"Added scraping job: every {interval_hours} hours "
                f"(next run: {job.next_run_time})"
            )
            return job.id
        
        # Check for cron-based scheduling
        cron_expr = scheduler_config.get('scrape_cron')
        
        if cron_expr:
            # Parse cron expression (e.g., "0 9 * * *" = daily at 9 AM)
            job = self.scheduler.add_job(
                func=self._run_scraping_job,
                trigger=CronTrigger.from_crontab(cron_expr),
                id='scraping_job',
                name='Automated Price Scraping',
                replace_existing=True
            )
            
            logger.info(
                f"Added scraping job: cron '{cron_expr}' "
                f"(next run: {job.next_run_time})"
            )
            return job.id
        
        raise ValueError(
            "No schedule configured. Set 'scrape_interval_hours' or 'scrape_cron' "
            "in config.yaml under 'scheduler' section"
        )
    
    
    def _run_scraping_job(self):
        """
        Execute the scraping job.
        
        This is the job function that APScheduler calls on schedule.
        Runs all scrapers via orchestrator and logs results.
        """
        logger.info("=" * 70)
        logger.info("SCHEDULED SCRAPING JOB STARTED")
        logger.info("=" * 70)
        
        start_time = datetime.now()
        
        try:
            with get_session() as session:
                orchestrator = ScraperOrchestrator(
                    db_session=session,
                    config=self.config,
                    max_workers=self.config.get('scraping', {}).get('max_workers', 3)
                )
                
                results = orchestrator.run_all_scrapers()
                
                # Check for price drop alerts after scraping
                logger.info("Checking for price drop alerts...")
                alert_manager = AlertManager(self.config, session)
                alert_results = alert_manager.check_and_send_alerts()
                
                logger.info(
                    f"Alerts: {alert_results.get('alerts_sent', 0)} sent, "
                    f"{alert_results.get('errors', 0)} errors"
                )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info("=" * 70)
            logger.info("SCHEDULED SCRAPING JOB COMPLETED")
            logger.info("=" * 70)
            logger.info(f"Total products: {results['total_products']}")
            logger.info(f"Successful: {results['successful']}")
            logger.info(f"Failed: {results['failed']}")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info("=" * 70)
            
            # Calculate next run
            job = self.scheduler.get_job('scraping_job')
            if job:
                logger.info(f"Next scheduled run: {job.next_run_time}")
        
        except Exception as e:
            logger.error(f"Scraping job failed: {e}", exc_info=True)
            raise
    
    
    def _job_executed_listener(self, event: JobExecutionEvent):
        """
        Listen to job execution events for logging.
        
        Args:
            event: Job execution event from APScheduler
        """
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed: {event.exception}",
                exc_info=True
            )
        else:
            logger.debug(f"Job {event.job_id} executed successfully")
    
    
    def start(self):
        """
        Start the scheduler.
        
        For BlockingScheduler: Blocks until interrupted (Ctrl+C)
        For BackgroundScheduler: Returns immediately, runs in background thread
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        # Add scraping job
        self.add_scraping_job()
        
        # Register shutdown handlers
        self._register_shutdown_handlers()
        
        # Start scheduler
        logger.info("Starting scheduler...")
        self.scheduler.start()
        self.is_running = True
        
        if self.blocking:
            logger.info("Scheduler started (blocking mode - press Ctrl+C to stop)")
            logger.info("=" * 70)
            
            # Print next run times
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                logger.info(f"Job: {job.name}")
                logger.info(f"  ID: {job.id}")
                logger.info(f"  Next run: {job.next_run_time}")
            
            logger.info("=" * 70)
            
            # Block until interrupted
            try:
                # Keep main thread alive
                while True:
                    import time
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                logger.info("Received shutdown signal")
                self.stop()
        else:
            logger.info("Scheduler started (background mode)")
    
    
    def stop(self, wait: bool = True):
        """
        Stop the scheduler.
        
        Args:
            wait: If True, wait for running jobs to complete
        """
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("Stopping scheduler...")
        
        self.scheduler.shutdown(wait=wait)
        self.is_running = False
        
        logger.info("Scheduler stopped")
    
    
    def get_jobs(self) -> list:
        """
        Get list of scheduled jobs.
        
        Returns:
            List of job objects
        """
        return self.scheduler.get_jobs()
    
    
    def get_job_status(self) -> Dict[str, Any]:
        """
        Get detailed status of scheduler and jobs.
        
        Returns:
            Dictionary with scheduler status
        """
        jobs = self.scheduler.get_jobs()
        
        status = {
            'running': self.is_running,
            'scheduler_type': 'blocking' if self.blocking else 'background',
            'total_jobs': len(jobs),
            'jobs': []
        }
        
        for job in jobs:
            status['jobs'].append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return status
    
    
    def _register_shutdown_handlers(self):
        """
        Register signal handlers for graceful shutdown.
        """
        def shutdown_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.stop()
            sys.exit(0)
        
        # Register handlers for common termination signals
        signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, shutdown_handler)  # Termination signal
        
        # Register cleanup on normal exit
        atexit.register(lambda: self.stop() if self.is_running else None)
        
        logger.debug("Registered shutdown handlers")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def start_scheduler(config: Dict[str, Any], background: bool = False):
    """
    Convenience function to start the scheduler.
    
    Args:
        config: Configuration dictionary
        background: If True, run in background mode
    
    Example:
        >>> from utils.config import load_config
        >>> config = load_config()
        >>> start_scheduler(config, background=False)  # Blocks until stopped
    """
    scheduler = PriceTrackerScheduler(config, blocking=not background)
    scheduler.start()
    return scheduler


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test scheduler.
    Run: python -m scheduler.job_scheduler
    """
    from utils.config import load_config
    
    print("=" * 70)
    print("Price Tracker Scheduler Test")
    print("=" * 70)
    print("\nThis will start the scheduler with a 1-minute interval for testing.")
    print("Press Ctrl+C to stop.\n")
    
    # Load config
    config = load_config()
    
    # Override interval for testing (1 minute instead of 4 hours)
    if 'scheduler' not in config:
        config['scheduler'] = {}
    config['scheduler']['scrape_interval_hours'] = 1/60  # 1 minute
    
    # Start scheduler
    scheduler = PriceTrackerScheduler(config, blocking=True)
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        scheduler.stop()
    
    print("\n" + "=" * 70)
    print("✓ Scheduler test complete")
    print("=" * 70)
