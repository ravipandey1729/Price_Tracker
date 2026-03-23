"""
Alert Manager

Detects threshold triggers and sends email/slack alerts, while persisting
in-app notifications for real-time website updates.
"""

import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from database.models import (
    AlertSent,
    AlertType,
    NotificationRecord,
    NotificationType,
    Price,
    Product,
    Threshold,
)
from utils.logging_config import get_logger

logger = get_logger(__name__)


class AlertManager:
    """Manages threshold checks and alert delivery."""

    def __init__(self, config: Dict[str, Any], db_session: Session):
        self.config = config
        self.db_session = db_session

        alert_cfg = config.get("alerts", {})
        self.enabled = alert_cfg.get("enabled", True)
        self.cooldown_hours = alert_cfg.get("cooldown_hours", 24)

        self.email_config = alert_cfg.get("email", {})
        self.email_enabled = self.email_config.get("enabled", False)

        self.slack_config = alert_cfg.get("slack", {})
        self.slack_enabled = self.slack_config.get("enabled", False)

    def check_and_send_alerts(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "alerts_sent": 0, "errors": 0}

        alerts_sent = 0
        errors = 0

        thresholds = (
            self.db_session.query(Threshold)
            .filter(Threshold.enabled.is_(True))
            .all()
        )

        for threshold in thresholds:
            try:
                if self._check_threshold(threshold):
                    alerts_sent += 1
            except Exception as exc:
                logger.error("Error checking threshold %s: %s", threshold.id, exc, exc_info=True)
                errors += 1

        return {"enabled": True, "alerts_sent": alerts_sent, "errors": errors}

    def _check_threshold(self, threshold: Threshold) -> bool:
        product = threshold.product

        latest = (
            self.db_session.query(Price)
            .filter(Price.product_id == product.id)
            .order_by(Price.scraped_at.desc())
            .first()
        )
        if not latest:
            return False

        previous = (
            self.db_session.query(Price)
            .filter(Price.product_id == product.id, Price.id != latest.id)
            .order_by(Price.scraped_at.desc())
            .first()
        )

        triggered_type: Optional[AlertType] = None
        threshold_value: Optional[float] = None
        change_pct: Optional[float] = None

        if threshold.target_price is not None and latest.price <= threshold.target_price:
            triggered_type = AlertType.TARGET_PRICE
            threshold_value = threshold.target_price

        if (
            threshold.percentage_drop is not None
            and previous is not None
            and previous.price > 0
        ):
            drop_pct = ((previous.price - latest.price) / previous.price) * 100
            if drop_pct >= threshold.percentage_drop:
                triggered_type = AlertType.PERCENTAGE_DROP
                threshold_value = threshold.percentage_drop
                change_pct = drop_pct

        if triggered_type is None or threshold_value is None:
            return False

        if not self._is_cooldown_expired(product.id, triggered_type):
            return False

        message = self._build_message(product, latest.price, threshold_value, triggered_type, latest.source_site)

        delivered = False
        if threshold.send_email and self.email_enabled:
            delivered = self._send_email_alert(product, latest, previous, threshold_value, triggered_type) or delivered

        if threshold.send_slack and self.slack_enabled:
            delivered = self._send_slack_alert(product, latest, previous, threshold_value, triggered_type) or delivered

        # Always create in-app notification record for live UI updates
        self._create_notification(
            user_id=threshold.user_id or product.user_id,
            product_id=product.id,
            title=f"Price Alert: {product.name}",
            message=message,
            notification_type=(
                NotificationType.TARGET_HIT
                if triggered_type == AlertType.TARGET_PRICE
                else NotificationType.PRICE_DROP
            ),
        )

        self._record_alert(
            user_id=threshold.user_id or product.user_id,
            product_id=product.id,
            alert_type=triggered_type,
            message=message,
            old_price=previous.price if previous else None,
            new_price=latest.price,
            percentage_change=change_pct,
            source_site=latest.source_site,
            sent_to=self._sent_to_label(threshold),
            delivery_method=self._delivery_method(threshold),
            delivery_status="sent" if delivered else "in_app_only",
        )

        return True

    def _is_cooldown_expired(self, product_id: int, alert_type: AlertType) -> bool:
        cooldown_after = datetime.utcnow() - timedelta(hours=self.cooldown_hours)
        recent = (
            self.db_session.query(AlertSent)
            .filter(AlertSent.product_id == product_id)
            .filter(AlertSent.alert_type == alert_type)
            .filter(AlertSent.sent_at > cooldown_after)
            .first()
        )
        return recent is None

    def _build_message(
        self,
        product: Product,
        new_price: float,
        threshold_value: float,
        alert_type: AlertType,
        source_site: str,
    ) -> str:
        if alert_type == AlertType.TARGET_PRICE:
            return (
                f"{product.name} hit your target price on {source_site}. "
                f"Current: ${new_price:.2f}, Target: ${threshold_value:.2f}."
            )

        return (
            f"{product.name} dropped by at least {threshold_value:.2f}% on {source_site}. "
            f"Current: ${new_price:.2f}."
        )

    def _product_urls(self, product: Product) -> Dict[str, str]:
        urls = {}
        if product.amazon_url:
            urls["Amazon"] = product.amazon_url
        if product.ebay_url:
            urls["eBay"] = product.ebay_url
        if product.walmart_url:
            urls["Walmart"] = product.walmart_url
        if product.flipkart_url:
            urls["Flipkart"] = product.flipkart_url
        return urls

    def _send_email_alert(
        self,
        product: Product,
        latest: Price,
        previous: Optional[Price],
        threshold_value: float,
        alert_type: AlertType,
    ) -> bool:
        try:
            smtp_server = self.email_config.get("smtp_server")
            smtp_port = self.email_config.get("smtp_port", 587)
            smtp_username = self.email_config.get("smtp_username")
            smtp_password = self.email_config.get("smtp_password")
            from_email = self.email_config.get("from_email", smtp_username)
            to_emails = self.email_config.get("to_emails", [])

            if not all([smtp_server, smtp_username, smtp_password, to_emails]):
                return False

            subject = f"Price Alert: {product.name}"
            old_price = previous.price if previous else None
            old_str = f"${old_price:.2f}" if old_price else "N/A"
            urls_text = "\n".join(f"- {site}: {url}" for site, url in self._product_urls(product).items())

            body = (
                f"Product: {product.name}\n"
                f"Site: {latest.source_site}\n"
                f"Old Price: {old_str}\n"
                f"New Price: ${latest.price:.2f}\n"
                f"Alert Type: {alert_type.value}\n"
                f"Threshold: {threshold_value}\n\n"
                f"Links:\n{urls_text}"
            )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            return True
        except Exception as exc:
            logger.error("Failed to send email alert: %s", exc, exc_info=True)
            return False

    def _send_slack_alert(
        self,
        product: Product,
        latest: Price,
        previous: Optional[Price],
        threshold_value: float,
        alert_type: AlertType,
    ) -> bool:
        try:
            webhook_url = self.slack_config.get("webhook_url")
            if not webhook_url:
                return False

            old_price = previous.price if previous else None
            old_str = f"${old_price:.2f}" if old_price else "N/A"
            payload = {
                "text": (
                    f"Price Alert for {product.name}\n"
                    f"Site: {latest.source_site}\n"
                    f"Old: {old_str} -> New: ${latest.price:.2f}\n"
                    f"Type: {alert_type.value}, Threshold: {threshold_value}"
                )
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as exc:
            logger.error("Failed to send slack alert: %s", exc, exc_info=True)
            return False

    def _create_notification(
        self,
        user_id: Optional[int],
        product_id: Optional[int],
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> None:
        notification = NotificationRecord(
            user_id=user_id,
            product_id=product_id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        self.db_session.add(notification)
        self.db_session.commit()

    def _record_alert(
        self,
        user_id: Optional[int],
        product_id: int,
        alert_type: AlertType,
        message: str,
        old_price: Optional[float],
        new_price: float,
        percentage_change: Optional[float],
        source_site: Optional[str],
        sent_to: str,
        delivery_method: str,
        delivery_status: str,
    ) -> None:
        record = AlertSent(
            user_id=user_id,
            product_id=product_id,
            alert_type=alert_type,
            message=message,
            old_price=old_price,
            new_price=new_price,
            percentage_change=percentage_change,
            source_site=source_site,
            sent_to=sent_to,
            delivery_method=delivery_method,
            delivery_status=delivery_status,
            sent_at=datetime.utcnow(),
        )
        self.db_session.add(record)
        self.db_session.commit()

    def _sent_to_label(self, threshold: Threshold) -> str:
        targets = []
        if threshold.send_email:
            targets.append("email")
        if threshold.send_slack:
            targets.append("slack")
        if not targets:
            targets.append("in-app")
        return ",".join(targets)

    def _delivery_method(self, threshold: Threshold) -> str:
        if threshold.send_email and threshold.send_slack:
            return "multi"
        if threshold.send_email:
            return "email"
        if threshold.send_slack:
            return "slack"
        return "in_app"


def check_alerts(config: Dict[str, Any], db_session: Session) -> Dict[str, Any]:
    manager = AlertManager(config, db_session)
    return manager.check_and_send_alerts()
