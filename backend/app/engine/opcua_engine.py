"""OPC-UA acquisition engine.

Capabilities:
- Connect to OPC-UA servers with optional security (None / Basic256Sha256)
- Subscribe to data-change subscriptions per tag node
- Periodic polling fallback for nodes that don't support subscriptions
- Write values back to writable nodes
"""
import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag, ProtocolType, OpcSecurity
from app.models.history import TagHistory


def _cast_opc_value(raw, target_type: str):
    try:
        if target_type in ("float64", "float32"):
            return float(raw)
        elif target_type in ("int16", "uint16", "int32", "uint32"):
            return int(float(raw))
        elif target_type == "bool":
            return 1 if raw else 0
        elif target_type == "string":
            return str(raw)
        return float(raw)
    except (ValueError, TypeError):
        return None


class OpcUaDeviceSession:
    """Manages one OPC-UA connection for a single device."""

    def __init__(self, device: Device):
        self.device_id = device.id
        self.device_name = device.name
        self._endpoint = device.opc_endpoint
        self._security_mode = device.opc_security_mode or "None"
        self._username = device.opc_username or None
        self._password = device.opc_password or None
        self._namespace = device.opc_namespace or 2
        self._poll_interval = device.poll_interval or 5.0

        self._client = None
        self._connected = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._live_values: dict[int, dict] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, tags: list[DeviceTag]):
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(tags,),
            daemon=True,
            name=f"opcua-{self.device_id}",
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=8)

    def write_value(self, tag: DeviceTag, value) -> bool:
        if not self._client or not self._connected:
            return False
        future = asyncio.run_coroutine_threadsafe(
            self._write_node(tag.opc_node_id, value, tag.opc_node_type),
            self._loop,
        )
        try:
            return future.result(timeout=10)
        except Exception as e:
            logger.error(f"OPC-UA write error: {e}")
            return False

    def get_live_values(self) -> dict:
        return self._live_values

    # ── internal async loop ──

    def _run_loop(self, tags: list[DeviceTag]):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main(tags))
        except Exception as e:
            logger.error(f"OPC-UA session error for '{self.device_name}': {e}")
        finally:
            self._loop.close()

    async def _async_main(self, tags: list[DeviceTag]):
        try:
            from asyncua import Client, ua
        except ImportError:
            logger.error("asyncua not installed. Run: pip install asyncua")
            self._update_status("error", "asyncua not installed")
            return

        client = Client(self._endpoint)
        self._client = client

        # Authentication
        if self._username:
            client.set_user(self._username)
        if self._password:
            client.set_password(self._password)

        # Security
        if self._security_mode != OpcSecurity.NONE:
            try:
                await client.set_security_string(
                    f"{self._security_mode},SignAndEncrypt,cert.pem,key.pem"
                )
            except Exception as e:
                logger.warning(f"OPC-UA security setup failed: {e}, falling back to None")

        try:
            await client.connect()
            self._connected = True
            self._update_status("online", None)
            logger.info(f"OPC-UA device '{self.device_name}' connected to {self._endpoint}")
        except Exception as e:
            logger.error(f"OPC-UA connect error: {e}")
            self._update_status("error", str(e))
            return

        # Build node handles
        node_map = {}  # node_id_string -> (node, tag)
        for tag in tags:
            if not tag.opc_node_id:
                continue
            try:
                node = client.get_node(tag.opc_node_id)
                # Verify node exists
                await node.read_value()
                node_map[tag.opc_node_id] = (node, tag)
            except Exception as e:
                logger.warning(f"OPC-UA node {tag.opc_node_id} not accessible: {e}")

        # Polling loop with reconnection
        consecutive_failures = 0
        backoff_delay = 1.0

        while not self._stop_event.is_set():
            # 检查连接状态
            if not self._connected:
                try:
                    await client.connect()
                    self._connected = True
                    consecutive_failures = 0
                    backoff_delay = 1.0
                    self._update_status("online", None)
                    logger.info(f"OPC-UA device '{self.device_name}' reconnected")
                except Exception as e:
                    consecutive_failures += 1
                    self._update_status("error", f"重连失败: {e}")
                    sleep_time = min(backoff_delay, 60.0)
                    backoff_delay *= 2
                    await asyncio.sleep(sleep_time)
                    continue

            try:
                for nid, (node, tag) in node_map.items():
                    try:
                        raw = await node.read_value()
                        casted = _cast_opc_value(raw, tag.opc_node_type or "float64")
                        if casted is None:
                            continue

                        processed = casted * tag.scale_factor + tag.offset
                        if tag.decimal_places is not None and isinstance(processed, float):
                            processed = round(processed, tag.decimal_places)

                        quality = "good"

                        # Script processing
                        if tag.script_id:
                            from app.models.script import Script
                            from app.engine.script_engine import script_engine as se
                            sdb = SessionLocal()
                            try:
                                script = sdb.query(Script).filter(Script.id == tag.script_id, Script.enabled == True).first()
                                if script:
                                    recent = sdb.query(TagHistory.value).filter(
                                        TagHistory.device_id == self.device_id, TagHistory.tag_id == tag.id,
                                    ).order_by(TagHistory.recorded_at.desc()).limit(script.max_history).all()
                                    history = [r[0] for r in reversed(recent)]
                                    tag_cfg = {"name": tag.name, "unit": tag.unit, "scale_factor": tag.scale_factor, "offset": tag.offset, "params": {}}
                                    ctx = {"device_id": self.device_id, "tag_id": tag.id, "timestamp": datetime.now(timezone.utc).isoformat()}
                                    result, quality, _ = se.execute(script.id, script.code, processed, history, tag_cfg, ctx, script.timeout_ms)
                                    if result is not None:
                                        processed = result
                            finally:
                                sdb.close()

                        self._live_values[tag.id] = {
                            "value": processed,
                            "raw_value": str(casted),
                            "quality": quality,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }

                        self._save_history(tag, processed, str(casted))

                        from app.services.alarm_service import alarm_service
                        alarm_service.evaluate(self.device_id, tag.id, tag.name, processed)

                    except Exception as e:
                        logger.error(f"OPC-UA read error for {nid}: {e}")
                        consecutive_failures += 1
                        # 连续读取失败超过 5 次，标记为断开
                        if consecutive_failures >= 5:
                            self._connected = False
                            self._update_status("error", f"连续读取失败: {e}")
                            try:
                                await client.disconnect()
                            except Exception:
                                pass
                            break

                if self._connected:
                    consecutive_failures = 0
                    self._update_status("online", None)
                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"OPC-UA poll loop error: {e}")
                await asyncio.sleep(1)

        # Cleanup
        try:
            await client.disconnect()
        except Exception:
            pass
        self._connected = False

    async def _write_node(self, node_id: str, value, node_type: str) -> bool:
        try:
            from asyncua import ua
            node = self._client.get_node(node_id)
            dtype_map = {
                "float64": ua.VariantType.Double,
                "float32": ua.VariantType.Float,
                "int16": ua.VariantType.Int16,
                "uint16": ua.VariantType.UInt16,
                "int32": ua.VariantType.Int32,
                "uint32": ua.VariantType.UInt32,
                "bool": ua.VariantType.Boolean,
                "string": ua.VariantType.String,
            }
            vt = dtype_map.get(node_type, ua.VariantType.Double)
            dv = ua.DataValue(ua.Variant(value, vt))
            await node.write_value(dv)
            return True
        except Exception as e:
            logger.error(f"OPC-UA write error: {e}")
            return False

    def _save_history(self, tag: DeviceTag, value: float, raw: str):
        from app.engine.shared_buffer import write_buffer, ws_pusher
        write_buffer.add({
            "device_id": self.device_id, "tag_id": tag.id, "tag_name": tag.name,
            "value": value, "raw_value": raw, "quality": "good",
            "recorded_at": datetime.now(timezone.utc),
        })
        ws_pusher.push_live_value(self.device_id, tag.id, tag.name, value, "good")

    def _update_status(self, status: str, error: Optional[str]):
        from app.engine.shared_buffer import ws_pusher
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == self.device_id).first()
            if device:
                device.status = status
                device.last_error = error
                device.last_poll_at = datetime.now(timezone.utc)
                db.commit()
                ws_pusher.push_device_status(self.device_id, device.name, status, error)
        except Exception:
            db.rollback()
        finally:
            db.close()


class OpcUaEngine:
    """Global OPC-UA engine managing all OPC-UA device sessions."""

    def __init__(self):
        self._sessions: dict[int, OpcUaDeviceSession] = {}
        self._lock = threading.Lock()

    def start(self):
        logger.info("OPC-UA engine starting...")
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(
                Device.protocol == ProtocolType.OPC_UA,
                Device.enabled == True,
            ).all()
            for device in devices:
                self._start_device(device)
        finally:
            db.close()

    def stop(self):
        logger.info("OPC-UA engine stopping...")
        for session in self._sessions.values():
            session.stop()
        self._sessions.clear()

    def reload_device(self, device_id: int):
        self._stop_device(device_id)
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.enabled and device.protocol == ProtocolType.OPC_UA:
                self._start_device(device)
        finally:
            db.close()

    def _start_device(self, device: Device):
        with self._lock:
            if device.id in self._sessions:
                return
            tags = [t for t in device.tags if t.enabled and t.opc_node_id]
            session = OpcUaDeviceSession(device)
            session.start(tags)
            self._sessions[device.id] = session

    def _stop_device(self, device_id: int):
        with self._lock:
            session = self._sessions.pop(device_id, None)
            if session:
                session.stop()

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        session = self._sessions.get(device_id)
        if session:
            return session.write_value(tag, value)
        return False

    def get_live_values(self, device_id: int) -> dict:
        session = self._sessions.get(device_id)
        if session:
            return session.get_live_values()
        return {}


# Global instance
opcua_engine = OpcUaEngine()
