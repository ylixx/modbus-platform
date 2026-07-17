"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Modbus Data Acquisition Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    API_PREFIX: str = "/api/v1"

    # Database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "modbus_platform"
    DATABASE_URL: Optional[str] = None

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

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

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
