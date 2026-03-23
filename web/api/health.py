"""
System API Router

Endpoints for system health, database stats, and scheduler control.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

from database.connection import get_session
from database.models import Product, Price, ScraperRun, Threshold, AlertSent
from sqlalchemy import func
from utils.health_check import HealthChecker
from utils.db_maintenance import DatabaseMaintenance
from utils.config import get_config
from scheduler.daemon_manager import SchedulerDaemon

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def system_health():
    """Get comprehensive system health status"""
    try:
        config = get_config()
        
        with get_session() as session:
            health_checker = HealthChecker(config, session)
            results = health_checker.run_all_checks()
            
            return {
                "status": results["overall_status"],
                "timestamp": datetime.utcnow().isoformat(),
                "checks_passed": results["passed_checks"],
                "checks_failed": results["failed_checks"],
                "checks": results["checks"],
                "warnings": results["warnings"],
                "errors": results["errors"]
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/stats")
async def database_stats():
    """Get database statistics"""
    try:
        db_maintenance = DatabaseMaintenance()
        stats = db_maintenance.get_database_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database": stats
        }
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler daemon status"""
    try:
        config = get_config()
        daemon = SchedulerDaemon(config)
        status = daemon.get_status()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler": status
        }
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/start")
async def start_scheduler():
    """Start the scheduler daemon"""
    try:
        config = get_config()
        daemon = SchedulerDaemon(config)
        
        if daemon.is_running():
            return {
                "status": "already_running",
                "message": "Scheduler is already running",
                "pid": daemon.get_pid()
            }
        
        success = daemon.start(foreground=False)
        
        return {
            "status": "started" if success else "failed",
            "message": "Scheduler started successfully" if success else "Failed to start scheduler",
            "pid": daemon.get_pid() if success else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the scheduler daemon"""
    try:
        config = get_config()
        daemon = SchedulerDaemon(config)
        
        if not daemon.is_running():
            return {
                "status": "not_running",
                "message": "Scheduler is not running"
            }
        
        success = daemon.stop()
        
        return {
            "status": "stopped" if success else "failed",
            "message": "Scheduler stopped successfully" if success else "Failed to stop scheduler",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/restart")
async def restart_scheduler():
    """Restart the scheduler daemon"""
    try:
        config = get_config()
        daemon = SchedulerDaemon(config)
        
        if daemon.is_running():
            daemon.stop()
            logger.info("Stopped scheduler for restart")
        
        success = daemon.start(foreground=False)
        
        return {
            "status": "restarted" if success else "failed",
            "message": "Scheduler restarted successfully" if success else "Failed to restart scheduler",
            "pid": daemon.get_pid() if success else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to restart scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview")
async def system_overview():
    """Get high-level system overview"""
    with get_session() as session:
        # Count records
        total_products = session.query(func.count(Product.id)).scalar()
        total_prices = session.query(func.count(Price.id)).scalar()
        total_runs = session.query(func.count(ScraperRun.id)).scalar()
        total_thresholds = session.query(func.count(Threshold.id)).scalar()
        total_alerts = session.query(func.count(AlertSent.id)).scalar()
        
        # Get latest scraper run
        latest_run = (
            session.query(ScraperRun)
            .order_by(ScraperRun.start_time.desc())
            .first()
        )
        
        # Get latest price
        latest_price = (
            session.query(Price)
            .order_by(Price.scraped_at.desc())
            .first()
        )
        
        # Check scheduler status
        try:
            config = get_config()
            daemon = SchedulerDaemon(config)
            scheduler_running = daemon.is_running()
        except:
            scheduler_running = False
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "counts": {
                "products": total_products,
                "prices": total_prices,
                "scraper_runs": total_runs,
                "thresholds": total_thresholds,
                "alerts_sent": total_alerts
            },
            "latest": {
                "scraper_run": {
                    "site": latest_run.site_name,
                    "status": latest_run.status.value,
                    "time": latest_run.start_time.isoformat()
                } if latest_run else None,
                "price": {
                    "product": latest_price.product.name,
                    "price": latest_price.price,
                    "currency": latest_price.currency,
                    "site": latest_price.source_site,
                    "time": latest_price.scraped_at.isoformat()
                } if latest_price else None
            },
            "scheduler": {
                "running": scheduler_running
            }
        }


@router.get("/version")
async def get_version():
    """Get application version info"""
    return {
        "application": "Price Tracker",
        "version": "0.7.0",
        "phase": "Phase 7: Web Dashboard",
        "build_date": "2026-03-11",
        "api_version": "1.0"
    }
