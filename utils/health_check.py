"""
System Health Check

Monitors system health and provides diagnostic information:
- Database health
- Disk space
- Configuration validity
- Scraper status
- Email/Slack connectivity  
- Recent errors

Usage:
    from utils.health_check import HealthChecker
    
    checker = HealthChecker(config, session)
    health = checker.run_all_checks()
    print(f"Overall status: {health['status']}")
"""

import os
import logging
import smtplib
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path

import requests
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import Product, Price, ScraperRun
from database.connection import get_database_path
from utils.config_validator import validate_config, validate_env_vars

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    System health monitoring and diagnostics.
    """
    
    def __init__(self, config: Dict[str, Any], db_session: Session):
        """
        Initialize health checker.
        
        Args:
            config: Application configuration
            db_session: SQLAlchemy database session
        """
        self.config = config
        self.session = db_session
        self.checks = []
        
        logger.info("HealthChecker initialized")
    
    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all health checks.
        
        Returns:
            Dictionary with check results and overall status
        """
        logger.info("Running health checks...")
        
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'checks': [],
            'status': 'healthy',  # healthy, degraded, unhealthy
            'warnings': [],
            'errors': []
        }
        
        # Run individual checks
        checks = [
            self.check_database(),
            self.check_configuration(),
            self.check_disk_space(),
            self.check_recent_scrapes(),
            self.check_products(),
            self.check_email_config(),
            self.check_slack_config()
        ]
        
        for check in checks:
            results['checks'].append(check)
            
            if check['status'] == 'error':
                results['errors'].append(check['message'])
                results['status'] = 'unhealthy'
            elif check['status'] == 'warning':
                results['warnings'].append(check['message'])
                if results['status'] == 'healthy':
                    results['status'] = 'degraded'
        
        # Summary counts
        results['total_checks'] = len(results['checks'])
        results['passed'] = sum(1 for c in results['checks'] if c['status'] == 'ok')
        results['warnings_count'] = len(results['warnings'])
        results['errors_count'] = len(results['errors'])
        
        logger.info(f"Health check complete: {results['status']}")
        
        return results
    
    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and health."""
        check = {
            'name': 'Database',
            'status': 'ok',
            'message': 'Database is accessible',
            'details': {}
        }
        
        try:
            db_path = get_database_path()
            
            # Check file exists
            if not os.path.exists(db_path):
                check['status'] = 'error'
                check['message'] = f'Database file not found: {db_path}'
                return check
            
            # Check file size
            size = os.path.getsize(db_path)
            check['details']['size_bytes'] = size
            check['details']['size_formatted'] = self._format_bytes(size)
            
            # Check we can query
            count = self.session.query(func.count(Product.id)).scalar()
            check['details']['products_count'] = count
            
            # Check file permissions
            check['details']['readable'] = os.access(db_path, os.R_OK)
            check['details']['writable'] = os.access(db_path, os.W_OK)
            
            if not check['details']['writable']:
                check['status'] = 'warning'
                check['message'] = 'Database is read-only'
            
        except Exception as e:
            check['status'] = 'error'
            check['message'] = f'Database error: {str(e)}'
            logger.error(f"Database health check failed: {e}")
        
        return check
    
    def check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        check = {
            'name': 'Configuration',
            'status': 'ok',
            'message': 'Configuration is valid',
            'details': {}
        }
        
        try:
            # Validate config
            errors = validate_config(self.config)
            warnings = validate_env_vars(self.config)
            
            check['details']['config_errors'] = len(errors)
            check['details']['config_warnings'] = len(warnings)
            
            if errors:
                check['status'] = 'error'
                check['message'] = f'Configuration has {len(errors)} error(s)'
                check['details']['errors'] = errors
            elif warnings:
                check['status'] = 'warning'
                check['message'] = f'Configuration has {len(warnings)} warning(s)'
                check['details']['warnings'] = warnings
        
        except Exception as e:
            check['status'] = 'error'
            check['message'] = f'Configuration check failed: {str(e)}'
            logger.error(f"Configuration health check failed: {e}")
        
        return check
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        check = {
            'name': 'Disk Space',
            'status': 'ok',
            'message': 'Disk space is adequate',
            'details': {}
        }
        
        try:
            db_path = Path(get_database_path())
            drive = db_path.drive if os.name == 'nt' else str(db_path.parent)
            
            # Get disk usage
            stat = os.statvfs(drive) if os.name != 'nt' else None
            
            if os.name == 'nt':
                # Windows
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive),
                    None,
                    None,
                    ctypes.pointer(free_bytes)
                )
                free_space = free_bytes.value
                total_space = None  # Would need another API call
            else:
                # Unix/Linux
                free_space = stat.f_bavail * stat.f_frsize
                total_space = stat.f_blocks * stat.f_frsize
            
            check['details']['free_space'] = free_space
            check['details']['free_space_formatted'] = self._format_bytes(free_space)
            
            if total_space:
                check['details']['total_space'] = total_space
                percent_free = (free_space / total_space) * 100
                check['details']['percent_free'] = round(percent_free, 2)
                
                if percent_free < 5:
                    check['status'] = 'error'
                    check['message'] = f'Critical: Only {percent_free:.1f}% disk space free'
                elif percent_free < 10:
                    check['status'] = 'warning'
                    check['message'] = f'Low disk space: {percent_free:.1f}% free'
            
            # Check if less than 100MB free
            if free_space < 100 * 1024 * 1024:
                check['status'] = 'error'
                check['message'] = f'Critical: Only {self._format_bytes(free_space)} free'
        
        except Exception as e:
            check['status'] = 'warning'
            check['message'] = f'Could not check disk space: {str(e)}'
            logger.warning(f"Disk space health check failed: {e}")
        
        return check
    
    def check_recent_scrapes(self) -> Dict[str, Any]:
        """Check recent scraper activity."""
        check = {
            'name': 'Recent Scrapes',
            'status': 'ok',
            'message': 'Scraper is running normally',
            'details': {}
        }
        
        try:
            # Get latest scrape run
            latest_run = (
                self.session.query(ScraperRun)
                .order_by(ScraperRun.start_time.desc())
                .first()
            )
            
            if not latest_run:
                check['status'] = 'warning'
                check['message'] = 'No scraper runs found'
                return check
            
            check['details']['last_run'] = latest_run.start_time.isoformat()
            check['details']['last_status'] = latest_run.status.value
            
            # Check how long ago
            time_since = datetime.utcnow() - latest_run.start_time
            check['details']['hours_since_last_run'] = round(time_since.total_seconds() / 3600, 2)
            
            # Get scrape interval from config
            interval_hours = self.config.get('scheduling', {}).get('scrape_interval_hours', 4)
            
            # Warn if no scrapes in 2x the interval
            if time_since.total_seconds() > interval_hours * 2 * 3600:
                check['status'] = 'warning'
                check['message'] = f'No scrapes in {check["details"]["hours_since_last_run"]} hours'
            
            # Check recent success rate
            recent_runs = (
                self.session.query(ScraperRun)
                .order_by(ScraperRun.start_time.desc())
                .limit(10)
                .all()
            )
            
            if recent_runs:
                successful = sum(1 for r in recent_runs if r.status.value == 'completed')
                success_rate = (successful / len(recent_runs)) * 100
                check['details']['recent_success_rate'] = round(success_rate, 2)
                
                if success_rate < 50:
                    check['status'] = 'error'
                    check['message'] = f'Low success rate: {success_rate:.1f}%'
                elif success_rate < 80:
                    check['status'] = 'warning'
                    check['message'] = f'Degraded success rate: {success_rate:.1f}%'
        
        except Exception as e:
            check['status'] = 'warning'
            check['message'] = f'Could not check scrapes: {str(e)}'
            logger.warning(f"Scrape health check failed: {e}")
        
        return check
    
    def check_products(self) -> Dict[str, Any]:
        """Check product configuration."""
        check = {
            'name': 'Products',
            'status': 'ok',
            'message': 'Products configured',
            'details': {}
        }
        
        try:
            product_count = self.session.query(func.count(Product.id)).scalar()
            check['details']['product_count'] = product_count
            
            if product_count == 0:
                check['status'] = 'warning'
                check['message'] = 'No products configured'
            else:
                # Check recent prices
                recent_cutoff = datetime.utcnow() - timedelta(days=7)
                products_with_recent_prices = (
                    self.session.query(func.count(func.distinct(Price.product_id)))
                    .filter(Price.scraped_at >= recent_cutoff)
                    .scalar()
                )
                
                check['details']['products_with_recent_prices'] = products_with_recent_prices
                
                if products_with_recent_prices == 0 and product_count > 0:
                    check['status'] = 'warning'
                    check['message'] = 'No recent price data'
        
        except Exception as e:
            check['status'] = 'warning'
            check['message'] = f'Could not check products: {str(e)}'
            logger.warning(f"Product health check failed: {e}")
        
        return check
    
    def check_email_config(self) -> Dict[str, Any]:
        """Check email configuration and connectivity."""
        check = {
            'name': 'Email',
            'status': 'ok',
            'message': 'Email not configured (optional)',
            'details': {}
        }
        
        try:
            email_config = self.config.get('alerts', {}).get('email', {})
            
            if not email_config.get('enabled', False):
                return check
            
            check['details']['enabled'] = True
            check['message'] = 'Email configured'
            
            # Check required settings
            smtp_server = email_config.get('smtp_server')
            smtp_port = email_config.get('smtp_port', 587)
            username = email_config.get('smtp_username')
            password = email_config.get('smtp_password')
            
            if not all([smtp_server, username, password]):
                check['status'] = 'error'
                check['message'] = 'Email credentials incomplete'
                return check
            
            check['details']['smtp_server'] = smtp_server
            check['details']['smtp_port'] = smtp_port
            
            # Test connection (optional, can be slow)
            # Uncomment to enable
            # try:
            #     with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            #         server.ehlo()
            #         check['details']['smtp_reachable'] = True
            # except Exception as e:
            #     check['status'] = 'warning'
            #     check['message'] = f'SMTP server unreachable: {str(e)}'
            #     check['details']['smtp_reachable'] = False
        
        except Exception as e:
            check['status'] = 'warning'
            check['message'] = f'Could not check email: {str(e)}'
            logger.warning(f"Email health check failed: {e}")
        
        return check
    
    def check_slack_config(self) -> Dict[str, Any]:
        """Check Slack configuration."""
        check = {
            'name': 'Slack',
            'status': 'ok',
            'message': 'Slack not configured (optional)',
            'details': {}
        }
        
        try:
            slack_config = self.config.get('alerts', {}).get('slack', {})
            
            if not slack_config.get('enabled', False):
                return check
            
            check['details']['enabled'] = True
            check['message'] = 'Slack configured'
            
            webhook_url = slack_config.get('webhook_url')
            
            if not webhook_url:
                check['status'] = 'error'
                check['message'] = 'Slack webhook URL missing'
                return check
            
            check['details']['webhook_configured'] = True
            
            # Test webhook (optional)
            # Uncomment to enable
            # try:
            #     response = requests.post(
            #         webhook_url,
            #         json={'text': 'Health check'},
            #         timeout=5
            #     )
            #     check['details']['webhook_reachable'] = response.status_code == 200
            #     if response.status_code != 200:
            #         check['status'] = 'warning'
            #         check['message'] = f'Slack webhook returned {response.status_code}'
            # except Exception as e:
            #     check['status'] = 'warning'
            #     check['message'] = f'Slack webhook unreachable: {str(e)}'
            #     check['details']['webhook_reachable'] = False
        
        except Exception as e:
            check['status'] = 'warning'
            check['message'] = f'Could not check Slack: {str(e)}'
            logger.warning(f"Slack health check failed: {e}")
        
        return check
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Format bytes as human-readable size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} TB"


def main():
    """Standalone health check."""
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
    
    # Run health checks
    with get_session() as session:
        checker = HealthChecker(config, session)
        health = checker.run_all_checks()
        
        print("\n" + "="*70)
        print("SYSTEM HEALTH CHECK")
        print("="*70)
        print(f"Status: {health['status'].upper()}")
        print(f"Checks: {health['passed']}/{health['total_checks']} passed")
        
        if health['warnings']:
            print(f"\nWarnings ({len(health['warnings'])}):")
            for warning in health['warnings']:
                print(f"  ⚠  {warning}")
        
        if health['errors']:
            print(f"\nErrors ({len(health['errors'])}):")
            for error in health['errors']:
                print(f"  ✗  {error}")
        
        print("\n" + "="*70)
        print("DETAILED CHECK RESULTS")
        print("="*70)
        
        for check in health['checks']:
            status_symbol = {'ok': '✓', 'warning': '⚠', 'error': '✗'}[check['status']]
            print(f"\n{status_symbol} {check['name']}: {check['message']}")
            
            if check['details']:
                for key, value in check['details'].items():
                    print(f"    {key}: {value}")


if __name__ == '__main__':
    main()
