"""Application configuration."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

# backend/ 目录（本文件位于 backend/app/core/config.py）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Modbus Data Acquisition Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    API_PREFIX: str = "/api/v1"

    # CORS — comma-separated list of allowed browser origins.
    # Never use "*" together with credentials. Leave empty to allow same-origin only.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Security hardening
    DISABLE_DEFAULT_ADMIN: bool = False  # set True to skip auto-creating the default admin

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "modbus_platform"
    DATABASE_URL: Optional[str] = None

    # 历史库（聚合 / 长期历史数据，正式版用独立的 MySQL 实例，与主关系库隔离）
    # 留空 → 复用主库 engine（开发期单库行为不变）
    HISTORY_DATABASE_URL: Optional[str] = None

    # Redis（缓存库：最新值缓存 / 多 worker WebSocket 广播 / 会话等）
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # 时序库（原始高频测点：正式版用时序库，留空则回退到关系库 tag_history）
    # 运行环境/选型（用户决策 2026-08-14）：Windows 下实际使用时序库 = TDengine 开源版
    #   （AGPLv3，Windows 友好，国产工业时序库，高频测点首选）；Apache IoTDB 适配器保留为
    #   可选接口（无测点上限，作为 TDengine 免费品牌档 5k 上限的替代方案，代码已就绪）。
    # 5k 上限说明：TDengine「Free Tier 品牌免费档」有 5000 测点上限（超出需商业授权）；
    #   其开源版(AGPL)从 GitHub 获取一般不受此墙。若实际部署的开源版仍受限，只要把
    #   TIMESERIES_TYPE 改成 iotdb 即可获得无上限能力，业务代码无需改动。
    # TIMESERIES_TYPE 可选: tdengine(默认选用) | iotdb(无上限备选) | timescaledb | influxdb | clickhouse
    TIMESERIES_TYPE: str = ""
    TIMESERIES_HOST: str = "127.0.0.1"
    TIMESERIES_PORT: int = 6041            # TDengine REST 默认 6041；IoTDB 用 6667
    TIMESERIES_USER: str = "root"
    TIMESERIES_PASSWORD: str = "taosdata"  # TDengine 默认口令；IoTDB 用 root（在 .env 显式覆盖）
    TIMESERIES_DATABASE: str = "modbus_ts" # IoTDB 的 storage group / TDengine 的 database 名
    TIMESERIES_TOKEN: Optional[str] = None  # influxdb 等需要 token 时填
    # 仅当 TIMESERIES_TYPE 已配置时生效：True=原始点只写时序库、不再写关系库 tag_history；
    # False(默认)=双写（关系库 tag_history 保留，便于历史 API 过渡）。
    TIMESERIES_RAW_ONLY: bool = False

    # Modbus
    MODBUS_POLL_INTERVAL: float = 5.0  # seconds
    MODBUS_TIMEOUT: float = 3.0
    MODBUS_RETRIES: int = 3

    # SMS - Aliyun
    ALIYUN_SMS_ACCESS_KEY: Optional[str] = None
    ALIYUN_SMS_ACCESS_SECRET: Optional[str] = None
    ALIYUN_SMS_SIGN_NAME: Optional[str] = None
    ALIYUN_SMS_TEMPLATE_CODE: Optional[str] = None

    # SMS - Tencent
    TENCENT_SMS_SECRET_ID: Optional[str] = None
    TENCENT_SMS_SECRET_KEY: Optional[str] = None
    TENCENT_SMS_APP_ID: Optional[str] = None
    TENCENT_SMS_SIGN_NAME: Optional[str] = None
    TENCENT_SMS_TEMPLATE_ID: Optional[str] = None

    # SMS - Custom Gateway
    CUSTOM_SMS_URL: Optional[str] = None
    CUSTOM_SMS_METHOD: str = "POST"
    CUSTOM_SMS_HEADERS: Optional[str] = None  # JSON string

    # SMS Provider: aliyun | tencent | custom
    SMS_PROVIDER: str = "aliyun"

    # Alarm
    ALARM_CHECK_INTERVAL: float = 2.0  # seconds
    MAX_SMS_PER_HOUR: int = 50

    # Notification - DingTalk
    DINGTALK_WEBHOOK_URL: Optional[str] = None

    # Notification - WeChat Work
    WECHAT_WEBHOOK_URL: Optional[str] = None

    # Notification - Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 465
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    ALARM_EMAIL_TO: Optional[str] = None

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # 让 sqlite 相对路径以 backend/ 为基准解析，避免依赖启动时的 cwd。
            # 否则从仓库根目录启动时，./modbus_platform.db 会误命中根目录的旧副本，
            # 后端静默用错库（之前 dry_run 测试就踩过这个坑）。
            if url.startswith("sqlite") and ":///" in url:
                rel = url.split(":///", 1)[1]
                if not Path(rel).is_absolute():
                    url = f"sqlite:///{(BASE_DIR / rel).resolve().as_posix()}"
            return url
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def history_database_url(self) -> Optional[str]:
        """历史库连接串；未配置时返回 None（调用方回退主库）。"""
        if not self.HISTORY_DATABASE_URL:
            return None
        url = self.HISTORY_DATABASE_URL
        # 同样把 sqlite 相对路径以 backend/ 为基准解析，保持与 database_url 一致
        if url.startswith("sqlite") and ":///" in url:
            rel = url.split(":///", 1)[1]
            if not Path(rel).is_absolute():
                url = f"sqlite:///{(BASE_DIR / rel).resolve().as_posix()}"
        return url

    @property
    def timeseries_enabled(self) -> bool:
        return bool(self.TIMESERIES_TYPE)

    @property
    def timeseries_config(self) -> dict:
        return {
            "type": self.TIMESERIES_TYPE,
            "host": self.TIMESERIES_HOST,
            "port": self.TIMESERIES_PORT,
            "user": self.TIMESERIES_USER,
            "password": self.TIMESERIES_PASSWORD,
            "database": self.TIMESERIES_DATABASE,
            "token": self.TIMESERIES_TOKEN,
        }

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
        env_file_encoding = "utf-8"


settings = Settings()
