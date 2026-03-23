"""
Configuration Validator

Validates config.yaml structure and settings to prevent runtime errors.
Performs checks on:
- Required sections and fields
- Data types and ranges
- Email/SMTP configuration
- Schedule formats
- Database settings

Usage:
    from utils.config_validator import validate_config
    
    errors = validate_config(config_dict)
    if errors:
        for error in errors:
            print(f"CONFIG ERROR: {error}")
"""

from typing import Dict, Any, List
import re


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate configuration dictionary.
    
    Args:
        config: Configuration dictionary from config.yaml
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    # Validate database section
    errors.extend(_validate_database(config.get('database', {})))
    
    # Validate scraping section
    errors.extend(_validate_scraping(config.get('scraping', {})))
    
    # Validate scheduling section
    errors.extend(_validate_scheduling(config.get('scheduling', {})))
    
    # Validate alerts section
    errors.extend(_validate_alerts(config.get('alerts', {})))
    
    # Validate reports section
    errors.extend(_validate_reports(config.get('reports', {})))
    
    # Validate logging section
    errors.extend(_validate_logging(config.get('logging', {})))
    
    return errors


def _validate_database(db_config: Dict[str, Any]) -> List[str]:
    """Validate database configuration."""
    errors = []
    
    if not db_config:
        errors.append("Missing 'database' section in config")
        return errors
    
    # Check required fields
    if 'path' not in db_config:
        errors.append("database.path is required")
    elif not isinstance(db_config['path'], str):
        errors.append("database.path must be a string")
    
    # Validate retention days
    if 'data_retention_days' in db_config:
        retention = db_config['data_retention_days']
        if not isinstance(retention, int) or retention < 1:
            errors.append("database.data_retention_days must be a positive integer")
    
    return errors


def _validate_scraping(scraping_config: Dict[str, Any]) -> List[str]:
    """Validate scraping configuration."""
    errors = []
    
    if not scraping_config:
        errors.append("Missing 'scraping' section in config")
        return errors
    
    # Validate delays
    min_delay = scraping_config.get('min_delay')
    max_delay = scraping_config.get('max_delay')
    
    if min_delay is not None:
        if not isinstance(min_delay, (int, float)) or min_delay < 0:
            errors.append("scraping.min_delay must be a non-negative number")
    
    if max_delay is not None:
        if not isinstance(max_delay, (int, float)) or max_delay < 0:
            errors.append("scraping.max_delay must be a non-negative number")
    
    if min_delay is not None and max_delay is not None:
        if min_delay > max_delay:
            errors.append("scraping.min_delay cannot be greater than max_delay")
    
    # Validate retries
    if 'max_retries' in scraping_config:
        retries = scraping_config['max_retries']
        if not isinstance(retries, int) or retries < 0:
            errors.append("scraping.max_retries must be a non-negative integer")
    
    # Validate timeout
    if 'timeout_seconds' in scraping_config:
        timeout = scraping_config['timeout_seconds']
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            errors.append("scraping.timeout_seconds must be a positive number")
    
    return errors


def _validate_scheduling(schedule_config: Dict[str, Any]) -> List[str]:
    """Validate scheduling configuration."""
    errors = []
    
    if not schedule_config:
        errors.append("Missing 'scheduling' section in config")
        return errors
    
    # Validate scrape interval
    if 'scrape_interval_hours' in schedule_config:
        interval = schedule_config['scrape_interval_hours']
        if not isinstance(interval, (int, float)) or interval <= 0:
            errors.append("scheduling.scrape_interval_hours must be a positive number")
    
    # Validate weekly report schedule
    if 'weekly_report' in schedule_config:
        report_config = schedule_config['weekly_report']
        
        if 'day_of_week' in report_config:
            day = report_config['day_of_week']
            valid_days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            if not isinstance(day, str) or day.lower() not in valid_days:
                errors.append(
                    f"scheduling.weekly_report.day_of_week must be one of: {', '.join(valid_days)}"
                )
        
        if 'hour' in report_config:
            hour = report_config['hour']
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                errors.append("scheduling.weekly_report.hour must be an integer between 0 and 23")
        
        if 'minute' in report_config:
            minute = report_config['minute']
            if not isinstance(minute, int) or minute < 0 or minute > 59:
                errors.append("scheduling.weekly_report.minute must be an integer between 0 and 59")
    
    return errors


def _validate_alerts(alerts_config: Dict[str, Any]) -> List[str]:
    """Validate alerts configuration."""
    errors = []
    
    if not alerts_config:
        # Alerts are optional
        return errors
    
    # Validate cooldown
    if 'cooldown_hours' in alerts_config:
        cooldown = alerts_config['cooldown_hours']
        if not isinstance(cooldown, (int, float)) or cooldown < 0:
            errors.append("alerts.cooldown_hours must be a non-negative number")
    
    # Validate email configuration
    if 'email' in alerts_config:
        email_config = alerts_config['email']
        
        if email_config.get('enabled', False):
            if 'smtp_server' not in email_config:
                errors.append("alerts.email.smtp_server is required when email is enabled")
            
            if 'smtp_port' in email_config:
                port = email_config['smtp_port']
                if not isinstance(port, int) or port < 1 or port > 65535:
                    errors.append("alerts.email.smtp_port must be an integer between 1 and 65535")
            
            if 'to_emails' in email_config:
                emails = email_config['to_emails']
                if not isinstance(emails, list):
                    errors.append("alerts.email.to_emails must be a list")
                elif len(emails) == 0:
                    errors.append("alerts.email.to_emails cannot be empty when email is enabled")
                else:
                    # Validate email format
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    for email in emails:
                        if not isinstance(email, str) or not re.match(email_pattern, email):
                            errors.append(f"Invalid email format: {email}")
    
    # Validate Slack configuration
    if 'slack' in alerts_config:
        slack_config = alerts_config['slack']
        
        if slack_config.get('enabled', False):
            if 'channel' not in slack_config:
                errors.append("alerts.slack.channel is required when Slack is enabled")
            elif not isinstance(slack_config['channel'], str):
                errors.append("alerts.slack.channel must be a string")
    
    return errors


def _validate_reports(reports_config: Dict[str, Any]) -> List[str]:
    """Validate reports configuration."""
    errors = []
    
    if not reports_config:
        # Reports are optional
        return errors
    
    # Validate days to include
    if 'days_to_include' in reports_config:
        days = reports_config['days_to_include']
        if not isinstance(days, int) or days < 1 or days > 365:
            errors.append("reports.days_to_include must be an integer between 1 and 365")
    
    # Validate chart settings
    if 'chart_width' in reports_config:
        width = reports_config['chart_width']
        if not isinstance(width, (int, float)) or width <= 0:
            errors.append("reports.chart_width must be a positive number")
    
    if 'chart_height' in reports_config:
        height = reports_config['chart_height']
        if not isinstance(height, (int, float)) or height <= 0:
            errors.append("reports.chart_height must be a positive number")
    
    if 'dpi' in reports_config:
        dpi = reports_config['dpi']
        if not isinstance(dpi, int) or dpi < 50 or dpi > 300:
            errors.append("reports.dpi must be an integer between 50 and 300")
    
    if 'top_deals_count' in reports_config:
        count = reports_config['top_deals_count']
        if not isinstance(count, int) or count < 1:
            errors.append("reports.top_deals_count must be a positive integer")
    
    return errors


def _validate_logging(logging_config: Dict[str, Any]) -> List[str]:
    """Validate logging configuration."""
    errors = []
    
    if not logging_config:
        # Logging is optional (has defaults)
        return errors
    
    # Validate log level
    if 'level' in logging_config:
        level = logging_config['level']
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if not isinstance(level, str) or level.upper() not in valid_levels:
            errors.append(
                f"logging.level must be one of: {', '.join(valid_levels)}"
            )
    
    # Validate file size
    if 'max_file_size_mb' in logging_config:
        size = logging_config['max_file_size_mb']
        if not isinstance(size, (int, float)) or size <= 0:
            errors.append("logging.max_file_size_mb must be a positive number")
    
    # Validate backup count
    if 'backup_count' in logging_config:
        count = logging_config['backup_count']
        if not isinstance(count, int) or count < 0:
            errors.append("logging.backup_count must be a non-negative integer")
    
    return errors


def validate_env_vars(config: Dict[str, Any]) -> List[str]:
    """
    Validate that required environment variables are set.
    
    Args:
        config: Configuration dictionary (after env var injection)
    
    Returns:
        List of warning messages for missing optional env vars
    """
    warnings = []
    
    # Check email credentials
    alerts_config = config.get('alerts', {})
    if alerts_config.get('enabled', False):
        email_config = alerts_config.get('email', {})
        if email_config.get('enabled', False):
            if not email_config.get('smtp_username'):
                warnings.append("EMAIL_USERNAME not set in .env (email alerts will not work)")
            if not email_config.get('smtp_password'):
                warnings.append("EMAIL_PASSWORD not set in .env (email alerts will not work)")
    
    # Check Slack webhook
    slack_config = alerts_config.get('slack', {})
    if slack_config.get('enabled', False):
        if not slack_config.get('webhook_url'):
            warnings.append("SLACK_WEBHOOK_URL not set in .env (Slack alerts will not work)")
    
    return warnings


def print_validation_report(errors: List[str], warnings: List[str] = None):
    """
    Print formatted validation report.
    
    Args:
        errors: List of error messages
        warnings: List of warning messages (optional)
    """
    if errors:
        print("\n" + "="*70)
        print("❌ CONFIGURATION ERRORS")
        print("="*70)
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")
        print("="*70)
        print("\nPlease fix these errors in config.yaml and try again.")
    
    if warnings:
        print("\n" + "="*70)
        print("⚠️  CONFIGURATION WARNINGS")
        print("="*70)
        for i, warning in enumerate(warnings, 1):
            print(f"{i}. {warning}")
        print("="*70)
    
    if not errors and not warnings:
        print("\n" + "="*70)
        print("✅ CONFIGURATION VALID")
        print("="*70)
        print("All settings are correct!")


if __name__ == '__main__':
    """Test configuration validation."""
    from utils.config import load_config
    
    try:
        config = load_config()
        errors = validate_config(config)
        warnings = validate_env_vars(config)
        
        print_validation_report(errors, warnings)
        
        if errors:
            exit(1)
        else:
            exit(0)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        exit(1)
