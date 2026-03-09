"""
Scraper Orchestrator

Coordinates scraping operations across multiple sites and products.
Handles parallel execution, database storage, and error tracking.

Key responsibilities:
- Load products from configuration
- Create appropriate scrapers for each site
- Run scrapers in parallel (ThreadPoolExecutor)
- Store results in database (Price and ScraperRun tables)
- Handle errors and log failures

Usage:
    from scrapers.orchestrator import ScraperOrchestrator
    from database.connection import get_session
    from utils.config import load_config
    
    config = load_config()
    
    with get_session() as session:
        orchestrator = ScraperOrchestrator(session, config)
        results = orchestrator.run_all_scrapers()
        
        print(f"Total products scraped: {results['total_products']}")
        print(f"Success: {results['successful']}, Failed: {results['failed']}")
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from database.models import Product, Price, ScraperRun, ScraperStatus
from scrapers.scraper_factory import get_scraper, is_site_supported
from scrapers.base_scraper import ScrapedData
from utils.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class ScrapeTask:
    """Represents a single scraping task."""
    product_id: str
    product_name: str
    url: str
    site_name: str


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    task: ScrapeTask
    success: bool
    data: Optional[ScrapedData] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class ScraperOrchestrator:
    """
    Orchestrates scraping operations across multiple sites.
    
    Manages parallel execution, database persistence, and error handling.
    """
    
    def __init__(
        self,
        db_session: Session,
        config: Dict[str,Any],
        max_workers: int = 3
    ):
        """
        Initialize orchestrator.
        
        Args:
            db_session: Active database session
            config: Configuration dict (from config.yaml)
            max_workers: Maximum parallel scrapers (default: 3)
        """
        self.db_session = db_session
        self.config = config
        self.max_workers = max_workers
        
        logger.info(f"Initialized orchestrator with max_workers={max_workers}")
    
    
    def run_all_scrapers(self) -> Dict[str, Any]:
        """
        Run all configured scrapers.
        
        Returns:
            Summary dict with statistics:
              - total_products: Number of products attempted
              - successful: Number successfully scraped
              - failed: Number that failed
              - results: List of ScrapeResult objects
              - duration: Total execution time in seconds
        """
        start_time = datetime.utcnow()
        logger.info("Starting scraping run for all sites")
        
        # Build list of scraping tasks
        tasks = self._build_scrape_tasks()
        
        if not tasks:
            logger.warning("No scraping tasks found in configuration")
            return {
                'total_products': 0,
                'successful': 0,
                'failed': 0,
                'results': [],
                'duration': 0.0
            }
        
        logger.info(f"Found {len(tasks)} products to scrape")
        
        # Execute tasks in parallel
        results = self._execute_tasks_parallel(tasks)
        
        # Persist results to database
        self._save_results(results, start_time)
        
        # Calculate statistics
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"Scraping run complete: {successful} successful, {failed} failed "
            f"({duration:.2f}s)"
        )
        
        return {
            'total_products': len(results),
            'successful': successful,
            'failed': failed,
            'results': results,
            'duration': duration
        }
    
    
    def run_site_scraper(self, site_name: str) -> Dict[str, Any]:
        """
        Run scraper for a single site only.
        
        Args:
            site_name: Name of site to scrape (e.g., "Amazon")
        
        Returns:
            Summary dict (same format as run_all_scrapers)
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting scraping run for: {site_name}")
        
        # Build tasks for this site only
        all_tasks = self._build_scrape_tasks()
        tasks = [t for t in all_tasks if t.site_name == site_name]
        
        if not tasks:
            logger.warning(f"No products found for site: {site_name}")
            return {
                'total_products': 0,
                'successful': 0,
                'failed': 0,
                'results': [],
                'duration': 0.0
            }
        
        logger.info(f"Found {len(tasks)} products for {site_name}")
        
        # Execute and save
        results = self._execute_tasks_parallel(tasks)
        self._save_results(results, start_time, single_site=site_name)
        
        successful = sum(1 for r in results if r.success)
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            'total_products': len(results),
            'successful': successful,
            'failed': len(results) - successful,
            'results': results,
            'duration': duration
        }
    
    
    def _build_scrape_tasks(self) -> List[ScrapeTask]:
        """
        Build list of scraping tasks from configuration.
        
        Returns:
            List of ScrapeTask objects
        """
        tasks = []
        
        products_config = self.config.get('products', [])
        
        for product in products_config:
            product_id = product.get('id')
            product_name = product.get('name', 'Unknown Product')
            urls = product.get('urls', {})
            
            for site_name, url in urls.items():
                # Skip if site not supported
                if not is_site_supported(site_name):
                    logger.warning(f"Site not supported: {site_name} (product: {product_id})")
                    continue
                
                tasks.append(ScrapeTask(
                    product_id=product_id,
                    product_name=product_name,
                    url=url,
                    site_name=site_name
                ))
        
        return tasks
    
    
    def _execute_tasks_parallel(self, tasks: List[ScrapeTask]) -> List[ScrapeResult]:
        """
        Execute scraping tasks in parallel.
        
        Args:
            tasks: List of ScrapeTask objects
        
        Returns:
            List of ScrapeResult objects
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self._execute_single_task, task): task
                for task in tasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Unexpected error executing task {task.product_id}: {e}")
                    results.append(ScrapeResult(
                        task=task,
                        success=False,
                        error=f"Execution error: {str(e)}"
                    ))
        
        return results
    
    
    def _execute_single_task(self, task: ScrapeTask) -> ScrapeResult:
        """
        Execute a single scraping task.
        
        Args:
            task: ScrapeTask to execute
        
        Returns:
            ScrapeResult with outcome
        """
        start_time = datetime.utcnow()
        
        logger.info(f"Scraping {task.site_name} for product: {task.product_id}")
        
        try:
            # Get appropriate scraper
            scraper = get_scraper(task.site_name)
            if not scraper:
                return ScrapeResult(
                    task=task,
                    success=False,
                    error=f"No scraper available for {task.site_name}"
                )
            
            # Perform scraping
            scraped_data = scraper.scrape(task.url, task.product_id)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            if scraped_data:
                logger.info(
                    f"✓ Successfully scraped {task.product_id} from {task.site_name} "
                    f"(${scraped_data.price})"
                )
                return ScrapeResult(
                    task=task,
                    success=True,
                    data=scraped_data,
                    execution_time=execution_time
                )
            else:
                logger.warning(f"✗ Failed to scrape {task.product_id} from {task.site_name}")
                return ScrapeResult(
                    task=task,
                    success=False,
                    error="Scraper returnedNone",
                    execution_time=execution_time
                )
        
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"✗ Error scraping {task.product_id} from {task.site_name}: {e}")
            return ScrapeResult(
                task=task,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    
    def _save_results(
        self,
        results: List[ScrapeResult],
        run_start_time: datetime,
        single_site: Optional[str] = None
    ) -> None:
        """
        Save scraping results to database.
        
        Creates Price records for successful scrapes and ScraperRun records
        for tracking execution.
        
        Args:
            results: List of ScrapeResult objects
            run_start_time: When the scraping run started
            single_site: If provided, only record run for this site
        """
        # Group results by site
        results_by_site = {}
        for result in results:
            site = result.task.site_name
            if site not in results_by_site:
                results_by_site[site] = []
            results_by_site[site].append(result)
        
        # Save Price records for successful results
        for result in results:
            if result.success and result.data:
                self._save_price_record(result)
        
        # Save ScraperRun records
        for site_name, site_results in results_by_site.items():
            self._save_scraper_run(site_name, site_results, run_start_time)
        
        # Commit transaction
        try:
            self.db_session.commit()
            logger.info("✓ Successfully saved all results to database")
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"✗ Failed to save results to database: {e}")
            raise
    
    
    def _save_price_record(self, result: ScrapeResult) -> None:
        """
        Save a Price record to database.
        
        Args:
            result: ScrapeResult with successful scrape data
        """
        try:
            # Ensure product exists
            product = self.db_session.query(Product).filter_by(
                product_id=result.task.product_id
            ).first()
            
            if not product:
                # Create product if it doesn't exist
                product = Product(
                    product_id=result.task.product_id,
                    name=result.task.product_name,
                    category="Unknown"
                )
                self.db_session.add(product)
                logger.info(f"Created new product: {result.task.product_id}")
            
            # Create price record
            price = Price(
                product_id=result.task.product_id,
                price=result.data.price,
                currency=result.data.currency,
                raw_price_text=result.data.raw_price_text,
                source_site=result.task.site_name,
                source_url=result.data.source_url,
                in_stock=result.data.in_stock,
                scraped_at=result.data.scraped_at
            )
            
            self.db_session.add(price)
            
            logger.debug(f"Saved price record for {result.task.product_id}: ${result.data.price}")
        
        except Exception as e:
            logger.error(f"Failed to save price record: {e}")
            raise
    
    
    def _save_scraper_run(
        self,
        site_name: str,
        results: List[ScrapeResult],
        start_time: datetime
    ) -> None:
        """
        Save a ScraperRun record to track execution.
        
        Args:
            site_name: Name of site
            results: Results for this site
            start_time: When run started
        """
        try:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            # Determine overall status
            if failed == 0:
                status = ScraperStatus.SUCCESS
            elif successful == 0:
                status = ScraperStatus.FAILED
            else:
                status = ScraperStatus.PARTIAL_SUCCESS
            
            # Collect error messages
            errors = [r.error for r in results if r.error]
            error_details = "; ".join(errors[:5])  # Limit to first 5 errors
            
            # Create record
            scraper_run = ScraperRun(
                site_name=site_name,
                status=status,
                products_attempted=len(results),
                products_succeeded=successful,
                products_failed=failed,
                error_details=error_details if error_details else None,
                started_at=start_time,
                completed_at=end_time,
                duration_seconds=duration
            )
            
            self.db_session.add(scraper_run)
            
            logger.info(
                f"Recorded scraper run for {site_name}: {status.value} "
                f"({successful}/{len(results)} successful)"
            )
        
        except Exception as e:
            logger.error(f"Failed to save scraper run record: {e}")
            raise


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def run_all_scrapers(db_session: Session, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to run all scrapers.
    
    Args:
        db_session: Active database session
        config: Configuration dict
    
    Returns:
        Summary dict with results
    """
    orchestrator = ScraperOrchestrator(db_session, config)
    return orchestrator.run_all_scrapers()


def run_site_scraper(
    db_session: Session,
    config: Dict[str, Any],
    site_name: str
) -> Dict[str, Any]:
    """
    Convenience function to run scraper for single site.
    
    Args:
        db_session: Active database session
        config: Configuration dict
        site_name: Name of site to scrape
    
    Returns:
        Summary dict with results
    """
    orchestrator = ScraperOrchestrator(db_session, config)
    return orchestrator.run_site_scraper(site_name)
