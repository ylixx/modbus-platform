"""时序库抽象层。

通过配置 TIMESERIES_TYPE 选择后端；未配置时回退到关系库（原始测点仍由 WriteBuffer 写入
关系库 tag_history），应用行为与开发期完全一致。所有后端客户端均为「懒导入 + 导入安全」：
缺少对应客户端库时仅告警并回退，不会让应用启动失败。

标准分层（用户确认）：
  原始高频测点  → 时序库（Windows 实际选用 TDengine 开源版；IoTDB 作为无测点上限备选，可一键切换 /
                  TimescaleDB / InfluxDB / ClickHouse）
  聚合/长期历史  → MySQL 历史库（HISTORY_DATABASE_URL）
  设备/用户/配置 → 主关系库
  最新值/广播    → Redis 缓存库
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("timeseries")


class TimeSeriesClient:
    """时序库客户端接口。"""

    enabled = False

    def write_points(self, records: list[dict]):
        """批量写入原始测点。records: [{device_id, tag_id, tag_name, value, quality, recorded_at}]"""
        raise NotImplementedError

    def query_range(self, device_id, tag_id, start, end, limit: int = 1000):
        raise NotImplementedError

    def health(self) -> bool:
        return False


class RelationalFallbackClient(TimeSeriesClient):
    """未配置时序库时使用：原始点已由 WriteBuffer 写入关系库 tag_history，这里无需操作。"""

    enabled = False

    def write_points(self, records: list[dict]):
        return None

    def query_range(self, *args, **kwargs):
        return None

    def health(self) -> bool:
        return True


_client: Optional[TimeSeriesClient] = None


def get_timeseries_client() -> TimeSeriesClient:
    """返回单例时序库客户端；按 TIMESERIES_TYPE 懒加载对应后端，失败则回退关系库。"""
    global _client
    if _client is not None:
        return _client

    if not settings.timeseries_enabled:
        _client = RelationalFallbackClient()
        return _client

    t = (settings.TIMESERIES_TYPE or "").lower()
    cfg = settings.timeseries_config
    try:
        if t == "iotdb":
            from app.core.timeseries_iotdb import IoTDBClient
            _client = IoTDBClient(cfg)
        elif t == "tdengine":
            from app.core.timeseries_tdengine import TDEngineClient
            _client = TDEngineClient(cfg)
        elif t == "timescaledb":
            from app.core.timeseries_timescaledb import TimescaleClient
            _client = TimescaleClient(cfg)
        elif t == "influxdb":
            from app.core.timeseries_influx import InfluxClient
            _client = InfluxClient(cfg)
        elif t == "clickhouse":
            from app.core.timeseries_clickhouse import ClickHouseClient
            _client = ClickHouseClient(cfg)
        else:
            logger.error(f"未知 TIMESERIES_TYPE={t}，回退关系库")
            _client = RelationalFallbackClient()
    except Exception as e:
        logger.error(f"初始化时序库客户端失败(type={t}): {e}，回退关系库")
        _client = RelationalFallbackClient()
    return _client
