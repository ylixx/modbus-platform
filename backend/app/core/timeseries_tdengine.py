"""TDengine 时序库客户端。

开源免费（AGPLv3，无 license fee），国产工业时序库，最适合 Modbus 高频测点场景。
使用 taosrest（REST 接口，默认端口 6041），无需本地原生驱动。

安装：pip install taos-rest
未安装时客户端仅告警并回退，不会让应用崩溃。
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.timeseries import TimeSeriesClient

logger = logging.getLogger("timeseries.tdengine")

try:
    import taosrest
except ImportError:
    taosrest = None


def _to_ns(ts) -> Optional[int]:
    """将各类时间戳统一转成纳秒整数（TDengine schemaless 用 ns）。"""
    try:
        if isinstance(ts, (int, float)):
            return int(ts * 1_000_000_000)
        if isinstance(ts, str):
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1_000_000_000)
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return int(ts.timestamp() * 1_000_000_000)
    except Exception:
        return None
    return None


class TDEngineClient(TimeSeriesClient):
    enabled = True

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._conn = None
        if taosrest is None:
            logger.warning("taosrest 未安装，TDengine 客户端不可用；请 `pip install taos-rest`")
            return
        try:
            url = f"http://{cfg['host']}:{cfg['port']}"
            self._conn = taosrest.connect(
                url=url, user=cfg["user"], password=cfg["password"]
            )
            self._conn.execute(f"CREATE DATABASE IF NOT EXISTS {cfg['database']}")
            self._conn.execute(f"USE {cfg['database']}")
            logger.info(f"TDengine 已连接: {url} db={cfg['database']}")
        except Exception as e:
            logger.error(f"TDengine 连接失败: {e}")
            self._conn = None

    def write_points(self, records: list[dict]):
        if self._conn is None:
            return
        lines = []
        for r in records:
            val = r.get("value")
            if val is None or r.get("quality") != "good":
                continue
            ts_ns = _to_ns(r.get("recorded_at"))
            if ts_ns is None:
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            tag_name = (str(r.get("tag_name") or "unknown")).replace(" ", "_").replace(",", "_")
            # schemaless 行协议:  measurement,tags fields timestamp(ns)
            lines.append(
                f"metrics,device_id={r['device_id']},tag_id={r['tag_id']},tag_name={tag_name} "
                f"value={fval} {ts_ns}"
            )
        if not lines:
            return
        try:
            self._conn.schemaless_insert(lines, "ns")
        except Exception as e:
            logger.error(f"TDengine 写入失败: {e}")

    def health(self) -> bool:
        if self._conn is None:
            return False
        try:
            self._conn.execute("SELECT server_status()")
            return True
        except Exception:
            return False
