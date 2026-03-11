"""
Alert Manager

Detects price drops and sends notifications via email and Slack.
Monitors price changes against configured thresholds and tracks sent alerts.

Features:
- Price drop detection against thresholds
- Email notifications via SMTP
- Slack notifications via webhook
- Alert history tracking
- Duplicate alert prevention

Usage:
    from alerts.alert_manager import AlertManager
    from utils.config import load_config
    
    config = load_config()
    alert_manager = AlertManager(config, db_session)
    
    # Check for price drops after scraping
    alert_manager.check_and_send_alerts()
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

from sqlalchemy.orm import Session
from database.models import Product, Price, Threshold, AlertSent
from utils.logging_config import get_logger


logger = get_logger(__name__)


class AlertManager:
    """
    Manages price drop alerts via email and Slack.
    
    Checks for price drops below configured thresholds and sends
    notifications through configured channels.
    """
    
    def __init__(self, config: Dict[str, Any], db_session: Session):
        """
        Initialize alert manager.
        
        Args:
            config: Configuration dictionary from config.yaml
            db_session: SQLAlchemy database session
        """
        self.config = config
        self.db_session = db_session
        
        # Get alert configuration
        self.alert_config = config.get('alerts', {})
        self.enabled = self.alert_config.get('enabled', True)
        
        # Email configuration
        self.email_config = self.alert_config.get('email', {})
        self.email_enabled = self.email_config.get('enabled', False)
        
        # Slack configuration
        self.slack_config = self.alert_config.get('slack', {})
        self.slack_enabled = self.slack_config.get('enabled', False)
        
        # Alert cooldown (prevent spam)
        self.cooldown_hours = self.alert_config.get('cooldown_hours', 24)
        
        logger.info(
            f"Initialized AlertManager "
            f"(email: {self.email_enabled}, slack: {self.slack_enabled})"
        )
    
    
    def check_and_send_alerts(self) -> Dict[str, Any]:
        """
        Check for price drops and send alerts.
        
        Main entry point for alert checking. Queries recent prices,
        compares against thresholds, and sends notifications.
        
        Returns:
            Dictionary with alert statistics
        """
        if not self.enabled:
            logger.debug("Alerts are disabled")
            return {
                'enabled': False,
                'alerts_sent': 0,
                'errors': 0
            }
        
        logger.info("=" * 70)
        logger.info("CHECKING FOR PRICE DROP ALERTS")
        logger.info("=" * 70)
        
        alerts_sent = 0
        errors = 0
        
        try:
            # Get all active thresholds
            thresholds = self.db_session.query(Threshold).all()
            
            if not thresholds:
                logger.info("No thresholds configured")
                return {
                    'enabled': True,
                    'alerts_sent': 0,
                    'errors': 0
                }
            
            logger.info(f"Found {len(thresholds)} thresholds to check")
            
            # Check each threshold
            for threshold in thresholds:
                try:
                    if self._check_threshold(threshold):
                        alerts_sent += 1
                except Exception as e:
                    logger.error(
                        f"Error checking threshold {threshold.id}: {e}",
                        exc_info=True
                    )
                    errors += 1
            
            logger.info("=" * 70)
            logger.info(f"Alert check complete: {alerts_sent} sent, {errors} errors")
            logger.info("=" * 70)
            
            return {
                'enabled': True,
                'alerts_sent': alerts_sent,
                'errors': errors
            }
        
        except Exception as e:
            logger.error(f"Alert check failed: {e}", exc_info=True)
            return {
                'enabled': True,
                'alerts_sent': alerts_sent,
                'errors': errors + 1
            }
    
    
    def _check_threshold(self, threshold: Threshold) -> bool:
        """
        Check if a specific threshold has been triggered.
        
        Args:
            threshold: Threshold object from database
        
        Returns:
            True if alert was sent, False otherwise
        """
        product = threshold.product
        
        # Get the most recent price for this product
        latest_price = (
            self.db_session.query(Price)
            .filter(Price.product_id == product.id)
            .order_by(Price.scraped_at.desc())
            .first()
        )
        
        if not latest_price:
            logger.debug(f"No prices found for product {product.name}")
            return False
        
        # Check if price is below threshold
        if latest_price.price >= threshold.threshold_price:
            logger.debug(
                f"Price ${latest_price.price} is above threshold "
                f"${threshold.threshold_price} for {product.name}"
            )
            return False
        
        # Check cooldown period (prevent spam)
        if not self._is_cooldown_expired(product.id, threshold.alert_type):
            logger.debug(
                f"Alert cooldown active for {product.name} "
                f"({threshold.alert_type})"
            )
            return False
        
        # Get previous price for comparison
        previous_price = (
            self.db_session.query(Price)
            .filter(Price.product_id == product.id)
            .filter(Price.id != latest_price.id)
            .order_by(Price.scraped_at.desc())
            .first()
        )
        
        old_price = previous_price.price if previous_price else None
        
        # Send alert
        logger.info(
            f"🔔 PRICE ALERT: {product.name} "
            f"dropped to ${latest_price.price} "
            f"(threshold: ${threshold.threshold_price})"
        )
        
        success = self._send_alert(
            product=product,
            old_price=old_price,
            new_price=latest_price.price,
            threshold_price=threshold.threshold_price,
            alert_type=threshold.alert_type,
            source_site=latest_price.source_site
        )
        
        if success:
            # Record alert in database
            self._record_alert(
                product_id=product.id,
                old_price=old_price,
                new_price=latest_price.price,
                threshold_price=threshold.threshold_price,
                alert_type=threshold.alert_type
            )
            return True
        
        return False
    
    
    def _is_cooldown_expired(self, product_id: int, alert_type: str) -> bool:
        """
        Check if cooldown period has expired for a product.
        
        Args:
            product_id: Product ID
            alert_type: Alert type (email, slack, all)
        
        Returns:
            True if cooldown expired, False if still active
        """
        cooldown_time = datetime.now() - timedelta(hours=self.cooldown_hours)
        
        recent_alert = (
            self.db_session.query(AlertSent)
            .filter(AlertSent.product_id == product_id)
            .filter(AlertSent.alert_type == alert_type)
            .filter(AlertSent.sent_at > cooldown_time)
            .first()
        )
        
        return recent_alert is None
    
    
    def _send_alert(
        self,
        product: Product,
        old_price: Optional[float],
        new_price: float,
        threshold_price: float,
        alert_type: str,
        source_site: str
    ) -> bool:
        """
        Send alert via configured channels.
        
        Args:
            product: Product object
            old_price: Previous price (or None)
            new_price: Current price
            threshold_price: Threshold that was triggered
            alert_type: Alert type (email, slack, all)
            source_site: Site where price was found
        
        Returns:
            True if at least one alert was sent successfully
        """
        success = False
        
        # Prepare alert message
        message_data = {
            'product_name': product.name,
            'old_price': old_price,
            'new_price': new_price,
            'threshold_price': threshold_price,
            'source_site': source_site,
            'discount_percent': self._calculate_discount(old_price, new_price),
            'urls': product.urls
        }
        
        # Send email alert
        if (alert_type in ['email', 'all']) and self.email_enabled:
            if self._send_email_alert(message_data):
                success = True
        
        # Send Slack alert
        if (alert_type in ['slack', 'all']) and self.slack_enabled:
            if self._send_slack_alert(message_data):
                success = True
        
        return success
    
    
    def _send_email_alert(self, data: Dict[str, Any]) -> bool:
        """
        Send email notification.
        
        Args:
            data: Alert message data
        
        Returns:
            True if sent successfully
        """
        try:
            # Get email configuration
            smtp_server = self.email_config.get('smtp_server')
            smtp_port = self.email_config.get('smtp_port', 587)
            smtp_username = self.email_config.get('smtp_username')
            smtp_password = self.email_config.get('smtp_password')
            from_email = self.email_config.get('from_email', smtp_username)
            to_emails = self.email_config.get('to_emails', [])
            
            if not all([smtp_server, smtp_username, smtp_password, to_emails]):
                logger.warning("Email configuration incomplete")
                return False
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔔 Price Drop Alert: {data['product_name']}"
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            
            # Create HTML body
            html_body = self._create_email_html(data)
            
            # Create plain text body (fallback)
            text_body = self._create_email_text(data)
            
            # Attach both versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            logger.info(f"✓ Email alert sent to {', '.join(to_emails)}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}", exc_info=True)
            return False
    
    
    def _send_slack_alert(self, data: Dict[str, Any]) -> bool:
        """
        Send Slack notification.
        
        Args:
            data: Alert message data
        
        Returns:
            True if sent successfully
        """
        try:
            webhook_url = self.slack_config.get('webhook_url')
            
            if not webhook_url:
                logger.warning("Slack webhook URL not configured")
                return False
            
            # Create Slack message
            slack_message = self._create_slack_message(data)
            
            # Send to Slack
            response = requests.post(
                webhook_url,
                json=slack_message,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✓ Slack alert sent")
                return True
            else:
                logger.error(
                    f"Slack webhook failed: {response.status_code} "
                    f"{response.text}"
                )
                return False
        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}", exc_info=True)
            return False
    
    
    def _create_email_html(self, data: Dict[str, Any]) -> str:
        """Create HTML email body."""
        old_price_str = f"${data['old_price']:.2f}" if data['old_price'] else "N/A"
        discount_str = f"({data['discount_percent']:.1f}% off)" if data['discount_percent'] else ""
        
        # Build URLs list
        urls_html = ""
        for site, url in data['urls'].items():
            urls_html += f'<li><a href="{url}">{site}</a></li>\n'
        
        html = f"""
        <html>
          <head>
            <style>
              body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
              .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
              .header {{ background-color: #4CAF50; color: white; padding: 15px; border-radius: 5px; text-align: center; }}
              .content {{ padding: 20px 0; }}
              .price-box {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #4CAF50; margin: 15px 0; }}
              .old-price {{ text-decoration: line-through; color: #999; }}
              .new-price {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
              .discount {{ color: #ff5722; font-weight: bold; }}
              .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #999; }}
              ul {{ list-style-type: none; padding: 0; }}
              li {{ margin: 5px 0; }}
              a {{ color: #2196F3; text-decoration: none; }}
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h2>🔔 Price Drop Alert!</h2>
              </div>
              <div class="content">
                <h3>{data['product_name']}</h3>
                <p><strong>Source:</strong> {data['source_site']}</p>
                
                <div class="price-box">
                  <p><span class="old-price">Old Price: {old_price_str}</span></p>
                  <p><span class="new-price">New Price: ${data['new_price']:.2f}</span> <span class="discount">{discount_str}</span></p>
                  <p>Below your threshold of <strong>${data['threshold_price']:.2f}</strong></p>
                </div>
                
                <h4>View Product:</h4>
                <ul>
                  {urls_html}
                </ul>
              </div>
              <div class="footer">
                <p>This alert was sent by Price Tracker at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
              </div>
            </div>
          </body>
        </html>
        """
        return html
    
    
    def _create_email_text(self, data: Dict[str, Any]) -> str:
        """Create plain text email body."""
        old_price_str = f"${data['old_price']:.2f}" if data['old_price'] else "N/A"
        discount_str = f"({data['discount_percent']:.1f}% off)" if data['discount_percent'] else ""
        
        urls_text = "\n".join([f"  {site}: {url}" for site, url in data['urls'].items()])
        
        text = f"""
🔔 PRICE DROP ALERT!

Product: {data['product_name']}
Source: {data['source_site']}

Old Price: {old_price_str}
New Price: ${data['new_price']:.2f} {discount_str}
Your Threshold: ${data['threshold_price']:.2f}

View Product:
{urls_text}

---
Sent by Price Tracker at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return text.strip()
    
    
    def _create_slack_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Slack message payload."""
        old_price_str = f"${data['old_price']:.2f}" if data['old_price'] else "N/A"
        discount_str = f" ({data['discount_percent']:.1f}% off)" if data['discount_percent'] else ""
        
        # Build URL buttons
        url_buttons = []
        for site, url in data['urls'].items():
            url_buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": f"View on {site}"
                },
                "url": url
            })
        
        message = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔔 Price Drop Alert!"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Product:*\n{data['product_name']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Source:*\n{data['source_site']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Old Price:*\n~{old_price_str}~"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*New Price:*\n:moneybag: ${data['new_price']:.2f}{discount_str}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Threshold:*\n${data['threshold_price']:.2f}"
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "actions",
                    "elements": url_buttons
                }
            ]
        }
        
        return message
    
    
    def _calculate_discount(
        self,
        old_price: Optional[float],
        new_price: float
    ) -> Optional[float]:
        """
        Calculate discount percentage.
        
        Args:
            old_price: Previous price
            new_price: Current price
        
        Returns:
            Discount percentage or None
        """
        if old_price and old_price > new_price:
            return ((old_price - new_price) / old_price) * 100
        return None
    
    
    def _record_alert(
        self,
        product_id: int,
        old_price: Optional[float],
        new_price: float,
        threshold_price: float,
        alert_type: str
    ):
        """
        Record sent alert in database.
        
        Args:
            product_id: Product ID
            old_price: Previous price
            new_price: Current price
            threshold_price: Threshold price
            alert_type: Alert type (email, slack, all)
        """
        try:
            alert = AlertSent(
                product_id=product_id,
                old_price=old_price,
                new_price=new_price,
                threshold_price=threshold_price,
                alert_type=alert_type,
                sent_at=datetime.now()
            )
            
            self.db_session.add(alert)
            self.db_session.commit()
            
            logger.debug(f"Recorded alert in database (ID: {alert.id})")
        
        except Exception as e:
            logger.error(f"Failed to record alert: {e}", exc_info=True)
            self.db_session.rollback()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_alerts(config: Dict[str, Any], db_session: Session) -> Dict[str, Any]:
    """
    Convenience function to check and send alerts.
    
    Args:
        config: Configuration dictionary
        db_session: Database session
    
    Returns:
        Alert statistics dictionary
    
    Example:
        >>> from utils.config import load_config
        >>> from database.connection import get_session
        >>> config = load_config()
        >>> with get_session() as session:
        ...     results = check_alerts(config, session)
    """
    alert_manager = AlertManager(config, db_session)
    return alert_manager.check_and_send_alerts()
