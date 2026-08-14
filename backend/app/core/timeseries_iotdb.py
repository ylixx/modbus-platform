"""Apache IoTDB 时序库客户端。

推荐时序库：Apache-2.0 完全开源、全功能免费、**无任何测点/序列数限制**，工业 IoT 原生
（树形设备层级、内置 Modbus 适配），最贴合本 Modbus 平台。满足「免费 + 点数无上限」硬约束。

使用官方 `apache-iotdb` Session 客户端（默认端口 6667）。
安装：pip install apache-iotdb
未安装时客户端仅告警并回退，不会让应用崩溃；write_points 直接 no-op。

数据模型（每条测点）：
  storage group : root.{TIMESERIES_DATABASE}
  device 路径   : root.{database}.d{device_id}
  measurements  : value(DOUBLE) / quality(TEXT)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.timeseries import TimeSeriesClient

logger = logging.getLogger("timeseries.iotdb")

try:
    from iotdb.Session import Session
    from iotdb.utils.IoTDBConstants import TSDataType
except ImportError:
    Session = None
    TSDataType = None


def _to_ms(ts) -> Optional[int]:
    """将各类时间戳统一转成毫秒整数（IoTDB 默认时间精度为 ms）。"""
    try:
        if isinstance(ts, (int, float)):
            # 若传入的是秒级（< 1e12）则升到毫秒
            v = float(ts)
            if v < 1e12:
                v *= 1000
            return int(v)
        if isinstance(ts, str):
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return int(ts.timestamp() * 1000)
    except Exception:
        return None
    return None


class IoTDBClient(TimeSeriesClient):
    enabled = False

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._session = None
        self._sg = f"root.{cfg.get('database') or 'modbus_ts'}"
        if Session is None:
            logger.warning("apache-iotdb 未安装，IoTDB 客户端不可用；请 `pip install apache-iotdb`")
            return
        try:
            self._session = Session(
                host=cfg["host"], port=int(cfg["port"]),
                user=cfg["user"], password=cfg["password"],
            )
            self._session.open(False)
            # 幂等建存储组（已存在会报已存在，需忽略）
            try:
                self._session.execute_non_query_statement(
                    f"CREATE DATABASE IF NOT EXISTS {self._sg}"
                )
            except Exception:
                pass
            self.enabled = True
            logger.info(f"IoTDB 已连接: {cfg['host']}:{cfg['port']} sg={self._sg}")
        except Exception as e:
            logger.error(f"IoTDB 连接失败: {e}")
            self._session = None

    def write_points(self, records: list[dict]):
        if self._session is None:
            return
        device_ids, timestamps, measurements, values, data_types = [], [], [], [], []
        for r in records:
            val = r.get("value")
            if val is None or r.get("quality") != "good":
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            ts_ms = _to_ms(r.get("recorded_at"))
            if ts_ms is None:
                continue
            device_ids.append(f"{self._sg}.d{r['device_id']}")
            timestamps.append(ts_ms)
            measurements.append(["value", "quality"])
            values.append([f"{fval}", str(r.get("quality") or "good")])
            data_types.append([TSDataType.DOUBLE, TSDataType.TEXT])
        if not device_ids:
            return
        try:
            self._session.insert_records(
                device_ids, timestamps, measurements, values, data_types
            )
        except Exception as e:
            logger.error(f"IoTDB 写入失败: {e}")

    def query_range(self, device_id, tag_id=None, start=None, end=None, limit: int = 1000):
        if self._session is None:
            return None
        dev = f"{self._sg}.d{device_id}"
        where = []
        if start is not None:
            where.append(f"time >= {_to_ms(start)}")
        if end is not None:
            where.append(f"time <= {_to_ms(end)}")
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        limit_sql = f" LIMIT {int(limit)}" if limit else ""
        sql = f"SELECT value FROM {dev}{where_sql} ORDER BY time{limit_sql}"
        try:
            ds = self._session.execute_query_statement(sql)
            return ds.tolist()
        except Exception as e:
            logger.error(f"IoTDB 查询失败({sql}): {e}")
            return None

    def health(self) -> bool:
        if self._session is None:
            return False
        try:
            self._session.execute_query_statement("SHOW DATABASES")
            return True
        except Exception:
            return False
