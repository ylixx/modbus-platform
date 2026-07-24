"""SMS sending service with multi-provider support."""
import json
import httpx
from typing import Optional
from datetime import datetime, timezone
from loguru import logger
from app.core.config import settings


class SmsService:
    """Unified SMS service supporting Aliyun, Tencent, and custom gateway."""

    def send_sms(self, phone: str, content: str) -> bool:
        provider = settings.SMS_PROVIDER
        try:
            if provider == "aliyun":
                return self._send_aliyun(phone, content)
            elif provider == "tencent":
                return self._send_tencent(phone, content)
            elif provider == "custom":
                return self._send_custom(phone, content)
            elif provider in ("mock", "demo", "none", ""):
                # 演示/本地开发模式：不真正发送，仅记录并返回成功，便于验证 UI 流程
                logger.info(f"[MOCK SMS] to={phone} content={content}")
                return True
            else:
                logger.error(f"Unknown SMS provider: {provider}")
                return False
        except Exception as e:
            logger.error(f"SMS send error ({provider}): {e}")
            return False

    def _send_aliyun(self, phone: str, content: str) -> bool:
        """Send SMS via Aliyun Dysmsapi."""
        try:
            from alibabacloud_dysmsapi20170525.client import Client
            from alibabacloud_dysmsapi20170525 import models as sms_models
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=settings.ALIYUN_SMS_ACCESS_KEY,
                access_key_secret=settings.ALIYUN_SMS_ACCESS_SECRET,
            )
            config.endpoint = "dysmsapi.aliyuncs.com"
            client = Client(config)

            request = sms_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=settings.ALIYUN_SMS_SIGN_NAME,
                template_code=settings.ALIYUN_SMS_TEMPLATE_CODE,
                template_param=json.dumps({"content": content}),
            )
            response = client.send_sms(request)
            if response.body.code == "OK":
                logger.info(f"Aliyun SMS sent to {phone}")
                return True
            else:
                logger.error(f"Aliyun SMS failed: {response.body.message}")
                return False
        except ImportError:
            logger.error("aliyun SDK not installed. Run: pip install alibabacloud-dysmsapi20170525")
            return False

    def _send_tencent(self, phone: str, content: str) -> bool:
        """Send SMS via Tencent Cloud."""
        try:
            from tencentcloud.common import credential
            from tencentcloud.sms.v20210111 import sms_client, models as sms_models

            cred = credential.Credential(settings.TENCENT_SMS_SECRET_ID, settings.TENCENT_SMS_SECRET_KEY)
            client = sms_client.SmsClient(cred, "ap-guangzhou")

            req = sms_models.SendSmsRequest()
            req.PhoneNumberSet = [phone]
            req.SmsSdkAppId = settings.TENCENT_SMS_APP_ID
            req.SignName = settings.TENCENT_SMS_SIGN_NAME
            req.TemplateId = settings.TENCENT_SMS_TEMPLATE_ID
            req.TemplateParamSet = [content]

            response = client.SendSms(req)
            if response.SendStatusSet and response.SendStatusSet[0].Code == "Ok":
                logger.info(f"Tencent SMS sent to {phone}")
                return True
            else:
                logger.error(f"Tencent SMS failed: {response.SendStatusSet}")
                return False
        except ImportError:
            logger.error("tencentcloud SDK not installed. Run: pip install tencentcloud-sdk-python-sms")
            return False

    def _send_custom(self, phone: str, content: str) -> bool:
        """Send SMS via custom HTTP gateway."""
        url = settings.CUSTOM_SMS_URL
        if not url:
            logger.error("CUSTOM_SMS_URL not configured")
            return False

        headers = {}
        if settings.CUSTOM_SMS_HEADERS:
            try:
                headers = json.loads(settings.CUSTOM_SMS_HEADERS)
            except json.JSONDecodeError:
                pass

        # Default payload template - customize as needed
        payload = {
            "phone": phone,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        method = settings.CUSTOM_SMS_METHOD.upper()
        with httpx.Client(timeout=10) as client:
            if method == "POST":
                resp = client.post(url, json=payload, headers=headers)
            else:
                resp = client.get(url, params=payload, headers=headers)

        if resp.status_code == 200:
            logger.info(f"Custom SMS sent to {phone}")
            return True
        else:
            logger.error(f"Custom SMS failed: {resp.status_code} {resp.text}")
            return False


sms_service = SmsService()
