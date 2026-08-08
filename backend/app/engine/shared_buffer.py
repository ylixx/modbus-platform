"""
共享写入缓冲和 WebSocket 批量推送

供 Modbus/MQTT/OPC-UA 三种协议引擎共用。
"""

import asyncio
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from app.core.database import SessionLocal
from app.models.history import TagHistory
from app.models.lab_data import TagAggregate


class WriteBuffer:
    """线程安全的写入缓冲，攒够一批后批量写入数据库。"""

    FLUSH_SIZE = 500
    FLUSH_INTERVAL = 2.0
    MAX_RETRY_COUNT = 3  # 单批最大重试次数

    def __init__(self):
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._flush_event = threading.Event()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._write_loop, daemon=True, name="db-writer")
        self._thread.start()
        logger.info("WriteBuffer started")

    def stop(self):
        self._running = False
        self._flush_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._do_flush()
        logger.info("WriteBuffer stopped")

    def add(self, record: dict):
        """添加一条历史记录。record 字段: device_id, tag_id, tag_name, value, raw_value, quality, recorded_at。"""
        with self._lock:
            self._buffer.append(record)
            if len(self._buffer) >= self.FLUSH_SIZE:
                self._flush_event.set()

    def _write_loop(self):
        while self._running:
            self._flush_event.wait(timeout=self.FLUSH_INTERVAL)
            self._flush_event.clear()
            self._do_flush()

    def _do_flush(self):
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        if not batch:
            return

        db = SessionLocal()
        retry_batch = None
        try:
            db.bulk_insert_mappings(TagHistory, batch)
            db.commit()
            logger.info(f"[入库] WriteBuffer 批量写入 {len(batch)} 条历史记录")
            self._update_aggregates(db, batch)
        except Exception as e:
            logger.error(f"WriteBuffer flush error: {e}")
            db.rollback()
            # flush 失败时将数据放回缓冲区，但标记重试次数
            retry_batch = []
            for record in batch:
                retry_count = record.get('_retry_count', 0) + 1
                if retry_count <= self.MAX_RETRY_COUNT:
                    record['_retry_count'] = retry_count
                    retry_batch.append(record)
                else:
                    logger.error(f"WriteBuffer: record discarded after {self.MAX_RETRY_COUNT} retries: device_id={record.get('device_id')}, tag_id={record.get('tag_id')}")
            if retry_batch:
                with self._lock:
                    self._buffer.extend(retry_batch)
                    if len(self._buffer) > self.FLUSH_SIZE * 10:
                        self._buffer = self._buffer[-self.FLUSH_SIZE * 5:]
                        logger.warning(f"WriteBuffer: buffer overflow, trimmed to {len(self._buffer)} records")
        finally:
            db.close()

    def _update_aggregates(self, db, records: list[dict]):
        try:
            buckets: dict[str, list[float]] = defaultdict(list)
            meta: dict[str, dict] = {}

            for r in records:
                if r.get("value") is None or r.get("quality") != "good":
                    continue
                ts = r.get("recorded_at")
                if not ts:
                    continue
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                minute_ts = ts.replace(second=0, microsecond=0)
                key = f"{r['device_id']}:{r['tag_id']}:{minute_ts.isoformat()}"
                buckets[key].append(r["value"])
                if key not in meta:
                    meta[key] = {
                        "device_id": r["device_id"], "tag_id": r["tag_id"],
                        "tag_name": r.get("tag_name", ""), "bucket_time": minute_ts,
                    }

            for key, values in buckets.items():
                m = meta[key]
                existing = db.query(TagAggregate).filter(
                    TagAggregate.device_id == m["device_id"],
                    TagAggregate.tag_id == m["tag_id"],
                    TagAggregate.granularity == 60,
                    TagAggregate.bucket_time == m["bucket_time"],
                ).first()

                if existing:
                    all_min = min(existing.min_value, min(values)) if existing.min_value is not None else min(values)
                    all_max = max(existing.max_value, max(values)) if existing.max_value is not None else max(values)
                    total_sum = (existing.avg_value or 0) * existing.count + sum(values)
                    existing.count += len(values)
                    existing.avg_value = round(total_sum / existing.count, 4)
                    existing.min_value = round(all_min, 4)
                    existing.max_value = round(all_max, 4)
                    existing.last_value = round(values[-1], 4)
                else:
                    db.add(TagAggregate(
                        device_id=m["device_id"], tag_id=m["tag_id"], tag_name=m["tag_name"],
                        granularity=60, bucket_time=m["bucket_time"],
                        min_value=round(min(values), 4), max_value=round(max(values), 4),
                        avg_value=round(sum(values) / len(values), 4), count=len(values),
                        first_value=round(values[0], 4), last_value=round(values[-1], 4),
                    ))

            db.commit()
        except Exception as e:
            logger.error(f"Aggregate update error: {e}")
            db.rollback()


class WsBatchPusher:
    """WebSocket 批量推送。"""

    FLUSH_INTERVAL = 0.05  # 50ms

    def __init__(self):
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._push_loop, daemon=True, name="ws-pusher")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def push_live_value(self, device_id: int, tag_id: int, tag_name: str, value, quality: str = "good"):
        with self._lock:
            self._buffer.append({
                "device_id": device_id, "tag_id": tag_id, "tag_name": tag_name,
                "value": value, "quality": quality,
                "time": datetime.now(timezone.utc).isoformat(),
            })

    def push_device_status(self, device_id: int, device_name: str, status: str, error: str = None):
        try:
            from app.engine.ws_broadcast import broadcast_device_status
            broadcast_device_status(device_id, device_name, status, error)
        except Exception:
            pass

    def _push_loop(self):
        while self._running:
            time.sleep(self.FLUSH_INTERVAL)
            self._do_push()

    def _do_push(self):
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        try:
            from app.engine.websocket_manager import ws_manager
            loop = _get_event_loop()
            if loop and not loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    ws_manager.broadcast({"type": "batch_live", "data": batch}), loop,
                )
        except Exception as e:
            logger.warning(f"WsBatchPusher push error: {e}")


def _get_event_loop():
    """Return the running main event loop (captured at startup).

    Broadcasts are fired from background threads, so we must schedule
    them on the *actual running* loop via ws_broadcast's stored loop.
    """
    try:
        from app.engine.ws_broadcast import _get_event_loop as _get_main_loop
        return _get_main_loop()
    except Exception:
        pass
    try:
        loop = asyncio.get_event_loop()
        return loop if not loop.is_closed() else None
    except RuntimeError:
        return None


# 全局共享实例
write_buffer = WriteBuffer()
ws_pusher = WsBatchPusher()
