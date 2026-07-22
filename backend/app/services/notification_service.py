"""Multi-channel notification service.

Supports:
  - SMS (existing)
  - DingTalk webhook
  - WeChat Work webhook
  - Email (SMTP)

Each channel is configured via .env and can be enabled/disabled independently.
"""
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
import httpx
from app.core.config import settings


class NotificationService:
    """Unified notification dispatcher."""

    def send(self, channel: str, title: str, content: str, to: str = None) -> bool:
        """Send notification to a specific channel."""
        try:
            if channel == "dingtalk":
                return self._send_dingtalk(title, content)
            elif channel == "wechat":
                return self._send_wechat_work(title, content)
            elif channel == "email":
                return self._send_email(title, content, to)
            elif channel == "sms":
                from app.services.sms_service import sms_service
                return sms_service.send_sms(to, content)
            else:
                logger.error(f"Unknown notification channel: {channel}")
                return False
        except Exception as e:
            logger.error(f"Notification error ({channel}): {e}")
            return False

    def send_alarm(self, alarm_message: str, alarm_level: str, device_name: str = ""):
        """Send alarm notification to all configured channels."""
        title = f"【{alarm_level.upper()}报警】{device_name}"
        content = f"{alarm_message}\n时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"

        results = {}
        # DingTalk
        if settings.DINGTALK_WEBHOOK_URL:
            results["dingtalk"] = self._send_dingtalk(title, content)

        # WeChat Work
        if settings.WECHAT_WEBHOOK_URL:
            results["wechat"] = self._send_wechat_work(title, content)

        # Email
        if settings.SMTP_HOST and settings.ALARM_EMAIL_TO:
            results["email"] = self._send_email(title, content, settings.ALARM_EMAIL_TO)

        return results

    # ── DingTalk ──

    def _send_dingtalk(self, title: str, content: str) -> bool:
        url = settings.DINGTALK_WEBHOOK_URL
        if not url:
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{content}",
            },
        }

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                logger.info(f"DingTalk notification sent: {title}")
                return True
            logger.error(f"DingTalk error: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"DingTalk send error: {e}")
            return False

    # ── WeChat Work ──

    def _send_wechat_work(self, title: str, content: str) -> bool:
        url = settings.WECHAT_WEBHOOK_URL
        if not url:
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n{content}",
            },
        }

        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                logger.info(f"WeChat Work notification sent: {title}")
                return True
            logger.error(f"WeChat Work error: {resp.text}")
            return False
        except Exception as e:
            logger.error(f"WeChat Work send error: {e}")
            return False

    # ── Email ──

    def _send_email(self, title: str, content: str, to: str) -> bool:
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT or 465
        user = settings.SMTP_USER
        password = settings.SMTP_PASSWORD
        from_addr = settings.SMTP_FROM or user

        if not all([host, user, password, to]):
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = to
            msg["Subject"] = title
            msg.attach(MIMEText(content, "plain", "utf-8"))

            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                server.starttls()

            server.login(user, password)
            server.sendmail(from_addr, to.split(","), msg.as_string())
            server.quit()
            logger.info(f"Email sent to {to}: {title}")
            return True
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False


notification_service = NotificationService()
