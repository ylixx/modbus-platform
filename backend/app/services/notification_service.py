"""Multi-channel notification service.

Supports:
  - SMS (existing)
  - DingTalk webhook
  - WeChat Work webhook
  - Email (SMTP)

Config is stored in system_configs (key: notification_config) and can be
managed via API/UI; missing fields fall back to .env values so existing
deployments keep working without changes.
"""
import json
import smtplib
from copy import deepcopy
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
import httpx
from app.core.config import settings

NOTIFICATION_CONFIG_KEY = "notification_config"

DEFAULT_NOTIFICATION_CONFIG = {
    "dingtalk": {
        "enabled": False, "webhook_url": "",
        "label": "钉钉机器人", "desc": "钉钉群自定义机器人 Webhook 地址",
    },
    "wechat": {
        "enabled": False, "webhook_url": "",
        "label": "企业微信", "desc": "企业微信群机器人 Webhook 地址",
    },
    "email": {
        "enabled": False, "host": "", "port": 465, "user": "", "password": "",
        "from": "", "to": "",
        "label": "邮件", "desc": "SMTP 服务器与收件人（多个收件人用逗号分隔）",
    },
}


def _load_config() -> dict:
    """Load notification config from DB, filling env defaults for empty fields."""
    from app.services.config_service import get_config
    cfg = get_config(NOTIFICATION_CONFIG_KEY) or {}
    merged = deepcopy(DEFAULT_NOTIFICATION_CONFIG)

    # Env fallback values
    env_defaults = {
        "dingtalk": {"webhook_url": settings.DINGTALK_WEBHOOK_URL},
        "wechat": {"webhook_url": settings.WECHAT_WEBHOOK_URL},
        "email": {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT or 465,
                  "user": settings.SMTP_USER, "password": settings.SMTP_PASSWORD,
                  "from": settings.SMTP_FROM, "to": settings.ALARM_EMAIL_TO},
    }

    for channel in merged:
        saved = cfg.get(channel) or {}
        merged[channel].update({k: v for k, v in saved.items() if k in merged[channel]})
        for key, env_val in env_defaults.get(channel, {}).items():
            if env_val and not merged[channel].get(key):
                merged[channel][key] = env_val
    return merged


def save_config(cfg: dict) -> dict:
    """Persist notification config (only known keys)."""
    from app.services.config_service import set_config
    clean = {}
    for channel, defaults in DEFAULT_NOTIFICATION_CONFIG.items():
        clean[channel] = {k: cfg.get(channel, {}).get(k) for k in defaults}
    set_config(NOTIFICATION_CONFIG_KEY, clean, "报警通知通道配置（钉钉/企业微信/邮件）")
    return _load_config()


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
        """Send alarm notification to all enabled & configured channels."""
        cfg = _load_config()
        title = f"【{alarm_level.upper()}报警】{device_name}"
        content = f"{alarm_message}\n时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"

        results = {}
        ding = cfg["dingtalk"]
        if ding.get("enabled") and ding.get("webhook_url"):
            results["dingtalk"] = self._send_dingtalk(title, content)

        wechat = cfg["wechat"]
        if wechat.get("enabled") and wechat.get("webhook_url"):
            results["wechat"] = self._send_wechat_work(title, content)

        email = cfg["email"]
        if email.get("enabled") and all([email.get("host"), email.get("user"), email.get("password"), email.get("to")]):
            results["email"] = self._send_email(title, content, email.get("to"))

        return results

    def test_send(self, channel: str) -> dict:
        """Send a test notification to verify channel configuration."""
        cfg = _load_config()
        title = "【测试通知】Modbus 数据采集平台"
        content = f"这是一条测试消息，来自报警通知通道：{channel}\n时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
        if channel == "dingtalk":
            if not cfg["dingtalk"].get("webhook_url"):
                return {"success": False, "message": "钉钉 Webhook 地址未配置"}
            ok = self._send_dingtalk(title, content)
        elif channel == "wechat":
            if not cfg["wechat"].get("webhook_url"):
                return {"success": False, "message": "企业微信 Webhook 地址未配置"}
            ok = self._send_wechat_work(title, content)
        elif channel == "email":
            if not all([cfg["email"].get("host"), cfg["email"].get("user"), cfg["email"].get("to")]):
                return {"success": False, "message": "邮件 SMTP 配置不完整"}
            ok = self._send_email(title, content, cfg["email"].get("to"))
        else:
            return {"success": False, "message": f"不支持的通道: {channel}"}
        return {"success": ok, "message": "发送成功" if ok else "发送失败，请检查日志"}

    # ── DingTalk ──

    def _send_dingtalk(self, title: str, content: str) -> bool:
        cfg = _load_config()["dingtalk"]
        url = cfg.get("webhook_url") or settings.DINGTALK_WEBHOOK_URL
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
        cfg = _load_config()["wechat"]
        url = cfg.get("webhook_url") or settings.WECHAT_WEBHOOK_URL
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
        cfg = _load_config()["email"]
        host = cfg.get("host") or settings.SMTP_HOST
        port = cfg.get("port") or settings.SMTP_PORT or 465
        user = cfg.get("user") or settings.SMTP_USER
        password = cfg.get("password") or settings.SMTP_PASSWORD
        from_addr = cfg.get("from") or settings.SMTP_FROM or user

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
