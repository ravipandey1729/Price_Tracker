"""
Scraping API Router

Endpoints for triggering scrapes and viewing scraper history.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import desc

from database.connection import get_session
from database.models import Product, ScraperRun, ScraperStatus, User
from scrapers.orchestrator import ScraperOrchestrator
from scrapers.scraper_factory import get_available_sites
from utils.config import get_config
from web.auth import get_current_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


async def run_scraping_task(
    user_id: int,
    site_name: Optional[str] = None,
    product_id: Optional[str] = None,
):
    """Background task to run scraping"""
    try:
        config = get_config()
        
        with get_session() as session:
            orchestrator = ScraperOrchestrator(session, config, owner_user_id=user_id)
            allowed_product_ids = [
                row[0]
                for row in session.query(Product.product_id)
                .filter(Product.user_id == user_id)
                .all()
            ]
            
            if site_name:
                logger.info(f"Starting scrape for site: {site_name}")
                results = orchestrator.run_site_scraper(
                    site_name,
                    allowed_product_ids=allowed_product_ids,
                )
            elif product_id:
                logger.info(f"Starting scrape for product: {product_id}")
                results = orchestrator.run_all_scrapers(allowed_product_ids=[product_id])
            else:
                logger.info("Starting scrape for all sites")
                results = orchestrator.run_all_scrapers(allowed_product_ids=allowed_product_ids)
            
            logger.info(
                "Scraping completed: %s attempted, %s successful",
                results.get("total_products", 0),
                results.get("successful", 0),
            )
            return {
                "status": "success",
                "total_products": results.get("total_products", 0),
                "successful": results.get("successful", 0),
                "failed": results.get("failed", 0),
            }
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/now")
async def scrape_now(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Trigger immediate scrape of all products"""
    background_tasks.add_task(run_scraping_task, user_id=current_user.id)
    
    return {
        "status": "started",
        "message": "Scraping started in background",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/site/{site_name}")
async def scrape_site(
    site_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Trigger immediate scrape for a specific site"""
    # Validate site_name
    valid_sites = get_available_sites()
    if site_name not in valid_sites:
        raise HTTPException(status_code=400, detail=f"Invalid site. Must be one of: {valid_sites}")
    
    background_tasks.add_task(run_scraping_task, user_id=current_user.id, site_name=site_name)
    
    return {
        "status": "started",
        "site": site_name,
        "message": f"Scraping started for {site_name}",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/product/{product_id}")
async def scrape_product(
    product_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Trigger immediate scrape for a specific product"""
    with get_session() as session:
        product = (
            session.query(Product)
            .filter_by(product_id=product_id, user_id=current_user.id)
            .first()
        )
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
    
    background_tasks.add_task(run_scraping_task, user_id=current_user.id, product_id=product_id)
    
    return {
        "status": "started",
        "product_id": product_id,
        "message": f"Scraping started for product {product_id}",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/history")
async def get_scraper_history(
    limit: int = 50,
    site: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get recent scraper run history"""
    with get_session() as session:
        query = session.query(ScraperRun).filter(ScraperRun.user_id == current_user.id)
        
        if site:
            query = query.filter(ScraperRun.site_name == site)
        
        if status:
            try:
                status_enum = ScraperStatus(status)
                query = query.filter(ScraperRun.status == status_enum)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid status filter") from exc
        
        runs = query.order_by(desc(ScraperRun.start_time)).limit(limit).all()
        
        return {
            "total": len(runs),
            "runs": [
                {
                    "id": run.id,
                    "site_name": run.site_name,
                    "status": run.status.value,
                    "products_attempted": run.products_attempted,
                    "products_succeeded": run.products_succeeded,
                    "products_failed": run.products_failed,
                    "start_time": run.start_time.isoformat(),
                    "end_time": run.end_time.isoformat() if run.end_time else None,
                    "duration_seconds": run.duration_seconds,
                    "error_details": run.error_details
                }
                for run in runs
            ]
        }


@router.get("/statistics")
async def get_scraper_statistics(
    days: int = 7,
    current_user: User = Depends(get_current_user),
):
    """Get scraping statistics for the last N days"""
    with get_session() as session:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        runs = (
            session.query(ScraperRun)
            .filter(
                ScraperRun.start_time >= start_date,
                ScraperRun.user_id == current_user.id,
            )
            .all()
        )
        
        if not runs:
            return {
                "days": days,
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0,
                "avg_duration": 0,
                "by_site": {}
            }
        
        # Calculate statistics
        total_runs = len(runs)
        successful_runs = sum(1 for r in runs if r.status == ScraperStatus.SUCCESS)
        failed_runs = sum(1 for r in runs if r.status == ScraperStatus.FAILED)
        success_rate = (successful_runs / total_runs) * 100 if total_runs > 0 else 0
        
        # Average duration
        durations = [r.duration_seconds for r in runs if r.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Statistics by site
        by_site = {}
        for run in runs:
            site = run.site_name
            if site not in by_site:
                by_site[site] = {
                    "total": 0,
                    "successful": 0,
                    "failed": 0,
                    "products_scraped": 0
                }
            
            by_site[site]["total"] += 1
            if run.status == ScraperStatus.SUCCESS:
                by_site[site]["successful"] += 1
                by_site[site]["products_scraped"] += run.products_succeeded
            else:
                by_site[site]["failed"] += 1
        
        # Calculate success rate per site
        for site_stats in by_site.values():
            total = site_stats["total"]
            site_stats["success_rate"] = (site_stats["successful"] / total) * 100 if total > 0 else 0
        
        return {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": success_rate,
            "avg_duration_seconds": avg_duration,
            "by_site": by_site
        }
