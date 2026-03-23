"""
Database Maintenance Utilities

Provides tools for database cleanup, optimization, and maintenance:
- Clean old price data
- Vacuum database to reclaim space
- Generate database statistics
- Backup database
- Repair database integrity

Usage:
    from utils.db_maintenance import DatabaseMaintenance
    
    maintenance = DatabaseMaintenance(config, session)
    maintenance.cleanup_old_data(days=90)
    maintenance.vacuum_database()
"""

import os
import shutil
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database.models import Product, Price, ScraperRun, AlertSent, Threshold
from database.connection import get_database_path, get_engine

logger = logging.getLogger(__name__)


class DatabaseMaintenance:
    """
    Database maintenance and optimization utilities.
    """
    
    def __init__(self, config: Dict[str, Any], db_session: Session):
        """
        Initialize database maintenance.
        
        Args:
            config: Application configuration
            db_session: SQLAlchemy database session
        """
        self.config = config
        self.session = db_session
        self.db_path = get_database_path()
        
        logger.info("DatabaseMaintenance initialized")
    
    def cleanup_old_data(self, days: Optional[int] = None) -> Dict[str, int]:
        """
        Delete price records older than specified days.
        
        Args:
            days: Number of days to keep (default from config)
        
        Returns:
            Dictionary with deletion counts
        """
        if days is None:
            days = self.config.get('database', {}).get('data_retention_days', 90)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        logger.info(f"Cleaning up data older than {days} days (before {cutoff_date.date()})")
        
        try:
            # Count records before deletion
            old_prices_count = (
                self.session.query(func.count(Price.id))
                .filter(Price.scraped_at < cutoff_date)
                .scalar()
            )
            
            old_runs_count = (
                self.session.query(func.count(ScraperRun.id))
                .filter(ScraperRun.start_time < cutoff_date)
                .scalar()
            )
            
            old_alerts_count = (
                self.session.query(func.count(AlertSent.id))
                .filter(AlertSent.sent_at < cutoff_date)
                .scalar()
            )
            
            # Delete old records
            if old_prices_count > 0:
                self.session.query(Price).filter(Price.scraped_at < cutoff_date).delete()
                logger.info(f"Deleted {old_prices_count} old price records")
            
            if old_runs_count > 0:
                self.session.query(ScraperRun).filter(ScraperRun.start_time < cutoff_date).delete()
                logger.info(f"Deleted {old_runs_count} old scraper run records")
            
            if old_alerts_count > 0:
                self.session.query(AlertSent).filter(AlertSent.sent_at < cutoff_date).delete()
                logger.info(f"Deleted {old_alerts_count} old alert records")
            
            self.session.commit()
            
            return {
                'prices_deleted': old_prices_count,
                'runs_deleted': old_runs_count,
                'alerts_deleted': old_alerts_count,
                'total_deleted': old_prices_count + old_runs_count + old_alerts_count
            }
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            raise
    
    def vacuum_database(self) -> Dict[str, Any]:
        """
        Vacuum SQLite database to reclaim space and optimize.
        
        Returns:
            Dictionary with before/after sizes
        """
        logger.info("Vacuuming database...")
        
        try:
            # Get size before vacuum
            size_before = os.path.getsize(self.db_path)
            
            # Execute VACUUM command
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("VACUUM"))
                conn.commit()
            
            # Get size after vacuum
            size_after = os.path.getsize(self.db_path)
            space_freed = size_before - size_after
            
            logger.info(
                f"Vacuum complete: {self._format_bytes(size_before)} → "
                f"{self._format_bytes(size_after)} (freed {self._format_bytes(space_freed)})"
            )
            
            return {
                'size_before': size_before,
                'size_after': size_after,
                'space_freed': space_freed,
                'reduction_percent': (space_freed / size_before * 100) if size_before > 0 else 0
            }
        
        except Exception as e:
            logger.error(f"Error during vacuum: {e}", exc_info=True)
            raise
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics.
        
        Returns:
            Dictionary with database stats
        """
        logger.info("Gathering database statistics...")
        
        try:
            stats = {}
            
            # File size
            if os.path.exists(self.db_path):
                stats['file_size'] = os.path.getsize(self.db_path)
                stats['file_size_formatted'] = self._format_bytes(stats['file_size'])
            
            # Table row counts
            stats['products'] = self.session.query(func.count(Product.id)).scalar()
            stats['prices'] = self.session.query(func.count(Price.id)).scalar()
            stats['scraper_runs'] = self.session.query(func.count(ScraperRun.id)).scalar()
            stats['thresholds'] = self.session.query(func.count(Threshold.id)).scalar()
            stats['alerts_sent'] = self.session.query(func.count(AlertSent.id)).scalar()
            
            stats['total_records'] = (
                stats['products'] + stats['prices'] + stats['scraper_runs'] +
                stats['thresholds'] + stats['alerts_sent']
            )
            
            # Date ranges
            oldest_price = (
                self.session.query(func.min(Price.scraped_at))
                .scalar()
            )
            newest_price = (
                self.session.query(func.max(Price.scraped_at))
                .scalar()
            )
            
            if oldest_price:
                stats['oldest_price_date'] = oldest_price.isoformat()
                stats['newest_price_date'] = newest_price.isoformat()
                stats['data_span_days'] = (newest_price - oldest_price).days
            else:
                stats['oldest_price_date'] = None
                stats['newest_price_date'] = None
                stats['data_span_days'] = 0
            
            # Average prices per product
            if stats['products'] > 0:
                stats['avg_prices_per_product'] = stats['prices'] / stats['products']
            else:
                stats['avg_prices_per_product'] = 0
            
            return stats
        
        except Exception as e:
            logger.error(f"Error gathering stats: {e}", exc_info=True)
            raise
    
    def backup_database(self, backup_dir: Optional[str] = None) -> str:
        """
        Create a backup of the database.
        
        Args:
            backup_dir: Directory for backups (default: backups/)
        
        Returns:
            Path to backup file
        """
        if backup_dir is None:
            backup_dir = "backups"
        
        # Create backup directory if it doesn't exist
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"price_tracker_backup_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        logger.info(f"Creating database backup: {backup_path}")
        
        try:
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            backup_size = os.path.getsize(backup_path)
            logger.info(
                f"Backup created successfully: {backup_path} "
                f"({self._format_bytes(backup_size)})"
            )
            
            return backup_path
        
        except Exception as e:
            logger.error(f"Error creating backup: {e}", exc_info=True)
            raise
    
    def check_integrity(self) -> Dict[str, Any]:
        """
        Check database integrity using SQLite's PRAGMA integrity_check.
        
        Returns:
            Dictionary with integrity check results
        """
        logger.info("Checking database integrity...")
        
        try:
            engine = get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("PRAGMA integrity_check"))
                rows = result.fetchall()
                
                # SQLite returns "ok" if everything is fine
                is_ok = len(rows) == 1 and rows[0][0] == 'ok'
                
                return {
                    'is_ok': is_ok,
                    'results': [row[0] for row in rows]
                }
        
        except Exception as e:
            logger.error(f"Error checking integrity: {e}", exc_info=True)
            raise
    
    def optimize_database(self) -> Dict[str, Any]:
        """
        Run full optimization: cleanup + vacuum + integrity check.
        
        Returns:
            Dictionary with optimization results
        """
        logger.info("=" * 70)
        logger.info("STARTING DATABASE OPTIMIZATION")
        logger.info("=" * 70)
        
        results = {}
        
        try:
            # Step 1: Cleanup old data
            logger.info("\nStep 1: Cleaning old data...")
            cleanup_result = self.cleanup_old_data()
            results['cleanup'] = cleanup_result
            
            # Step 2: Vacuum database
            logger.info("\nStep 2: Vacuuming database...")
            vacuum_result = self.vacuum_database()
            results['vacuum'] = vacuum_result
            
            # Step 3: Check integrity
            logger.info("\nStep 3: Checking integrity...")
            integrity_result = self.check_integrity()
            results['integrity'] = integrity_result
            
            # Step 4: Get final stats
            logger.info("\nStep 4: Gathering final statistics...")
            stats = self.get_database_stats()
            results['stats'] = stats
            
            logger.info("\n" + "=" * 70)
            logger.info("DATABASE OPTIMIZATION COMPLETE")
            logger.info("=" * 70)
            
            return results
        
        except Exception as e:
            logger.error(f"Error during optimization: {e}", exc_info=True)
            raise
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes as human-readable size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"


def main():
    """Standalone database maintenance."""
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from utils.config import load_config
    from utils.logging_config import setup_logging
    from database.connection import get_session
    
    # Setup
    setup_logging()
    config = load_config()
    
    # Run maintenance
    with get_session() as session:
        maintenance = DatabaseMaintenance(config, session)
        
        print("\n" + "="*70)
        print("DATABASE MAINTENANCE")
        print("="*70)
        
        # Get current stats
        print("\nCurrent Database Statistics:")
        stats = maintenance.get_database_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Run optimization
        print("\n" + "="*70)
        results = maintenance.optimize_database()
        print("="*70)
        
        print("\nOptimization Results:")
        print(f"  Records deleted: {results['cleanup']['total_deleted']}")
        print(f"  Space freed: {maintenance._format_bytes(results['vacuum']['space_freed'])}")
        print(f"  Integrity check: {'✓ PASSED' if results['integrity']['is_ok'] else '✗ FAILED'}")


if __name__ == '__main__':
    main()
