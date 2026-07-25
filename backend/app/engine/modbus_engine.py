"""Modbus TCP polling engine with full protocol support.

Supports:
- Function codes: FC01 (Coil), FC02 (Discrete Input), FC03 (Holding Register), FC04 (Input Register)
- Write: FC05 (Write Single Coil), FC06 (Write Single Register), FC15 (Write Multiple Coils), FC16 (Write Multiple Registers)
- Data types: bool, int16, uint16, int32, uint32, float32, float64, string, bcd
- Byte orders: big_endian, little_endian, big_endian_swap, little_endian_swap
"""
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag, FunctionCode
from app.models.history import TagHistory
from app.core.config import settings
from app.engine.modbus_codec import get_register_count, decode_value, decode_32bit, decode_float32, decode_float64, bcd_to_int


class ModbusEngine:
    """Manages Modbus TCP connections and polling for all devices."""

    def __init__(self):
        self._clients: dict[int, ModbusTcpClient] = {}  # device_id -> client
        self._live_values: dict[str, dict] = {}  # f"{device_id}_{tag_id}" -> {value, quality, time}
        self._running = False
        self._threads: dict[int, threading.Thread] = {}
        self._stop_events: dict[int, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self):
        """Start polling all enabled devices."""
        if self._running:
            return
        self._running = True
        logger.info("Modbus engine starting...")

        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.enabled == True).all()
            for device in devices:
                self._start_device_polling(device)
        finally:
            db.close()

    def stop(self):
        """Stop all polling."""
        self._running = False
        logger.info("Modbus engine stopping...")
        for device_id, event in self._stop_events.items():
            event.set()
        for t in self._threads.values():
            t.join(timeout=5)
        for client in self._clients.values():
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()
        self._threads.clear()
        self._stop_events.clear()
        logger.info("Modbus engine stopped.")

    def reload_device(self, device_id: int):
        """Reload polling for a specific device (after config change)."""
        self._stop_device_polling(device_id)
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.enabled:
                self._start_device_polling(device)
        finally:
            db.close()

    def _start_device_polling(self, device: Device):
        device_id = device.id
        if device_id in self._threads and self._threads[device_id].is_alive():
            return

        stop_event = threading.Event()
        self._stop_events[device_id] = stop_event

        thread = threading.Thread(
            target=self._poll_device_loop,
            args=(device_id, device.host, device.port, device.slave_id,
                  device.timeout, device.retries, device.poll_interval, stop_event),
            daemon=True,
            name=f"modbus-poll-{device_id}",
        )
        self._threads[device_id] = thread
        thread.start()
        logger.info(f"Started polling device {device.name} ({device.host}:{device.port})")

    def _stop_device_polling(self, device_id: int):
        event = self._stop_events.get(device_id)
        if event:
            event.set()
        thread = self._threads.get(device_id)
        if thread:
            thread.join(timeout=5)
        client = self._clients.pop(device_id, None)
        if client:
            try:
                client.close()
            except Exception:
                pass
        self._stop_events.pop(device_id, None)
        self._threads.pop(device_id, None)

    # ── 重连退避常量 ──
    BACKOFF_BASE = 1.0        # 初始退避 1 秒
    BACKOFF_MAX = 60.0        # 最大退避 60 秒
    BACKOFF_MULTIPLIER = 2.0  # 指数倍数
    MAX_CONSECUTIVE_FAILURES = 50  # 连续失败上限，超过自动禁用设备
    OFFLINE_ALARM_THRESHOLD = 3   # 连续失败 N 次后触发离线报警

    def _poll_device_loop(
        self, device_id: int, host: str, port: int, slave_id: int,
        timeout: float, retries: int, interval: float, stop_event: threading.Event,
    ):
        client = ModbusTcpClient(host=host, port=port, timeout=timeout, retries=retries)
        self._clients[device_id] = client
        consecutive_failures = 0
        was_online = False  # 上一轮是否在线（用于检测状态转换）
        backoff_delay = self.BACKOFF_BASE

        while not stop_event.is_set():
            try:
                if not client.connected:
                    connected = client.connect()
                    if not connected:
                        consecutive_failures += 1
                        self._update_device_status(device_id, "error", "连接失败")

                        # 首次离线：写入 quality=bad 标记
                        if was_online:
                            self._mark_tags_offline(device_id)
                            was_online = False

                        # 触发离线报警
                        if consecutive_failures == self.OFFLINE_ALARM_THRESHOLD:
                            self._trigger_disconnect_alarm(device_id)

                        # 超过上限：自动禁用设备
                        if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                            self._auto_disable_device(device_id, f"连续 {consecutive_failures} 次连接失败")
                            break

                        # 指数退避
                        sleep_time = min(backoff_delay, self.BACKOFF_MAX)
                        logger.warning(f"Device {device_id} 连接失败 ({consecutive_failures}次)，{sleep_time:.0f}s 后重试")
                        backoff_delay *= self.BACKOFF_MULTIPLIER
                        stop_event.wait(sleep_time)
                        continue

                # 连接成功，执行采集
                self._poll_device(device_id, client, slave_id)

                # 状态恢复
                if consecutive_failures > 0:
                    logger.info(f"Device {device_id} 恢复在线，连续失败 {consecutive_failures} 次")
                    # 清除离线期间的 quality=bad 标记（用新数据覆盖即可）
                    from app.services.alarm_service import alarm_service
                    alarm_service.clear_disconnect(device_id)

                consecutive_failures = 0
                backoff_delay = self.BACKOFF_BASE  # 重置退避
                was_online = True
                self._update_device_status(device_id, "online", None)

            except Exception as e:
                logger.error(f"Poll error for device {device_id}: {e}")
                consecutive_failures += 1
                self._update_device_status(device_id, "error", str(e))

                # 首次离线：写入 quality=bad 标记
                if was_online:
                    self._mark_tags_offline(device_id)
                    was_online = False

                # 触发离线报警
                if consecutive_failures == self.OFFLINE_ALARM_THRESHOLD:
                    self._trigger_disconnect_alarm(device_id)

                # 超过上限：自动禁用
                if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                    self._auto_disable_device(device_id, f"连续 {consecutive_failures} 次采集异常: {e}")
                    break

                # 关闭连接，下次重连
                try:
                    client.close()
                except Exception:
                    pass

                # 指数退避
                sleep_time = min(backoff_delay, self.BACKOFF_MAX)
                logger.warning(f"Device {device_id} 采集异常 ({consecutive_failures}次)，{sleep_time:.0f}s 后重试")
                backoff_delay *= self.BACKOFF_MULTIPLIER
                stop_event.wait(sleep_time)
                continue

            # 正常轮询间隔
            stop_event.wait(interval)

        try:
            client.close()
        except Exception:
            pass

    def _mark_tags_offline(self, device_id: int):
        """为设备所有启用的点位写入 quality=bad 的历史标记，用于离线期间数据可追溯。"""
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id, DeviceTag.enabled == True
            ).all()
            now = datetime.now(timezone.utc)
            for tag in tags:
                # 更新实时缓存
                key = f"{device_id}_{tag.id}"
                if key in self._live_values:
                    self._live_values[key]["quality"] = "bad"
                    self._live_values[key]["time"] = now.isoformat()

                # 写入历史标记
                history = TagHistory(
                    device_id=device_id,
                    tag_id=tag.id,
                    tag_name=tag.name,
                    value=None,
                    raw_value="offline",
                    quality="bad",
                )
                db.add(history)

                # WebSocket 推送
                try:
                    from app.engine.ws_broadcast import broadcast_live_value
                    broadcast_live_value(device_id, tag.id, tag.name, None, "bad")
                except Exception:
                    pass

            db.commit()
            logger.info(f"Device {device_id}: 已写入 {len(tags)} 个点位的离线标记")
        except Exception as e:
            logger.error(f"Mark offline error for device {device_id}: {e}")
            db.rollback()
        finally:
            db.close()

    def _trigger_disconnect_alarm(self, device_id: int):
        """触发设备离线报警。"""
        from app.services.alarm_service import alarm_service
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                alarm_service.evaluate_disconnect(device_id, device.name)
        finally:
            db.close()

    def _auto_disable_device(self, device_id: int, reason: str):
        """连续失败过多，自动禁用设备。"""
        logger.error(f"Device {device_id} 自动禁用: {reason}")
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.enabled = False
                device.status = "error"
                device.last_error = f"自动禁用: {reason}"
                db.commit()
                try:
                    from app.engine.ws_broadcast import broadcast_device_status
                    broadcast_device_status(device_id, device.name, "disabled", reason)
                except Exception:
                    pass
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _poll_device(self, device_id: int, client: ModbusTcpClient, slave_id: int):
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id,
                DeviceTag.enabled == True,
            ).all()

            # Group tags by function code and contiguous addresses for batch reading
            groups = self._group_tags(tags)

            for (fc, start_addr, count), tag_list in groups.items():
                try:
                    raw_values = self._read_registers(client, slave_id, fc, start_addr, count)
                    if raw_values is None:
                        continue

                    for tag in tag_list:
                        offset = tag.address - start_addr
                        value = decode_value(
                            raw_values, offset, tag.data_type, tag.byte_order,
                            bit_index=tag.bit_index,
                            register_count=tag.register_count,
                            function_code=tag.function_code,
                        )
                        if value is not None:
                            processed = value * tag.scale_factor + tag.offset
                            if tag.decimal_places is not None:
                                processed = round(processed, tag.decimal_places)

                            # Script processing
                            processed, quality, alarm_msg = self._apply_script(
                                db, tag, device_id, processed
                            )

                            # Update live values
                            key = f"{device_id}_{tag.id}"
                            self._live_values[key] = {
                                "value": processed,
                                "raw_value": str(value),
                                "quality": quality,
                                "time": datetime.now(timezone.utc).isoformat(),
                            }

                            # Real-time push to WebSocket clients (single-worker & Redis paths).
                            try:
                                from app.engine.ws_broadcast import broadcast_live_value
                                broadcast_live_value(device_id, tag.id, tag.name, processed, quality)
                            except Exception:
                                pass

                            # Save to history
                            history = TagHistory(
                                device_id=device_id,
                                tag_id=tag.id,
                                tag_name=tag.name,
                                value=processed,
                                raw_value=str(value),
                                quality=quality,
                            )
                            db.add(history)

                            # Evaluate alarms
                            from app.services.alarm_service import alarm_service
                            alarm_service.evaluate(device_id, tag.id, tag.name, processed)

                except Exception as e:
                    logger.error(f"Read error for tag group at addr {start_addr}: {e}")

            # Update last poll time
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.last_poll_at = datetime.now(timezone.utc)

            db.commit()
        except Exception as e:
            logger.error(f"Poll device {device_id} error: {e}")
            db.rollback()
        finally:
            db.close()

    def _group_tags(self, tags: list[DeviceTag]) -> dict:
        """Group tags by function code into contiguous address blocks for efficient batch reading."""
        groups = {}
        # Sort by function code and address
        fc_groups = {}
        for tag in tags:
            fc = tag.function_code
            if fc not in fc_groups:
                fc_groups[fc] = []
            fc_groups[fc].append(tag)

        for fc, tag_list in fc_groups.items():
            tag_list.sort(key=lambda t: t.address)

            # Determine register size per tag
            current_start = None
            current_end = None
            current_tags = []

            for tag in tag_list:
                reg_count = get_register_count(tag.data_type, tag.register_count)
                tag_start = tag.address
                tag_end = tag.address + reg_count

                if current_start is None:
                    current_start = tag_start
                    current_end = tag_end
                    current_tags = [tag]
                elif tag_start <= current_end + 5:  # Allow small gaps (up to 5 registers)
                    current_end = max(current_end, tag_end)
                    current_tags.append(tag)
                else:
                    # Flush current group
                    count = current_end - current_start
                    groups[(fc, current_start, count)] = current_tags
                    current_start = tag_start
                    current_end = tag_end
                    current_tags = [tag]

            if current_tags and current_start is not None:
                count = current_end - current_start
                groups[(fc, current_start, count)] = current_tags

        return groups

    def _read_registers(self, client: ModbusTcpClient, slave_id: int, fc: str, address: int, count: int):
        try:
            if fc == FunctionCode.COIL:
                result = client.read_coils(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.bits[:count]
            elif fc == FunctionCode.DISCRETE_INPUT:
                result = client.read_discrete_inputs(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.bits[:count]
            elif fc == FunctionCode.INPUT_REGISTER:
                result = client.read_input_registers(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.registers
            elif fc == FunctionCode.HOLDING_REGISTER:
                result = client.read_holding_registers(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.registers
            return None
        except Exception as e:
            logger.error(f"Modbus read error: FC={fc}, addr={address}, count={count}: {e}")
            return None

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        """Write a value to a Modbus device."""
        client = self._clients.get(device_id)
        if not client or not client.connected:
            # Try to connect
            db = SessionLocal()
            try:
                device = db.query(Device).filter(Device.id == device_id).first()
                if not device:
                    return False
                client = ModbusTcpClient(
                    host=device.host, port=device.port,
                    timeout=device.timeout, retries=device.retries,
                )
                if not client.connect():
                    return False
                self._clients[device_id] = client
            finally:
                db.close()

        slave_id = 1
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                slave_id = device.slave_id
        finally:
            db.close()

        try:
            if tag.function_code == FunctionCode.COIL:
                result = client.write_coil(tag.address, bool(value), slave=slave_id)
            elif tag.function_code == FunctionCode.HOLDING_REGISTER:
                if tag.data_type in (DataType.INT16, DataType.UINT16, DataType.BCD, DataType.BOOL):
                    result = client.write_register(tag.address, int(value), slave=slave_id)
                elif tag.data_type in (DataType.INT32, DataType.UINT32):
                    # Encode as 2 registers
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    if tag.data_type == DataType.INT32:
                        encoder.add_32bit_int(int(value))
                    else:
                        encoder.add_32bit_uint(int(value))
                    payload = encoder.to_registers()
                    result = client.write_registers(tag.address, payload, slave=slave_id)
                elif tag.data_type == DataType.FLOAT32:
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_32bit_float(float(value))
                    payload = encoder.to_registers()
                    result = client.write_registers(tag.address, payload, slave=slave_id)
                elif tag.data_type == DataType.FLOAT64:
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_64bit_float(float(value))
                    payload = encoder.to_registers()
                    result = client.write_registers(tag.address, payload, slave=slave_id)
                else:
                    return False
            else:
                return False

            return not result.isError()
        except Exception as e:
            logger.error(f"Write error: {e}")
            return False

    def get_live_values(self, device_id: int) -> dict:
        """Get all live values for a device."""
        result = {}
        for key, val in self._live_values.items():
            if key.startswith(f"{device_id}_"):
                tag_id = int(key.split("_", 1)[1])
                result[tag_id] = val
        return result

    def _apply_script(self, db, tag, device_id: int, value: float):
        """Apply script processing to a value if the tag has a script assigned."""
        if not tag.script_id:
            return value, "good", None

        from app.models.script import Script
        from app.engine.script_engine import script_engine

        script = db.query(Script).filter(Script.id == tag.script_id, Script.enabled == True).first()
        if not script:
            return value, "good", None

        # Build history
        recent = db.query(TagHistory.value).filter(
            TagHistory.device_id == device_id,
            TagHistory.tag_id == tag.id,
        ).order_by(TagHistory.recorded_at.desc()).limit(script.max_history).all()
        history = [r[0] for r in reversed(recent)]

        tag_config = {
            "name": tag.name, "unit": tag.unit,
            "scale_factor": tag.scale_factor, "offset": tag.offset,
            "params": {},
        }
        try:
            import json
            tag_config["params"] = json.loads(script.default_params) if script.default_params else {}
        except Exception:
            pass

        context = {"device_id": device_id, "tag_id": tag.id, "timestamp": datetime.now(timezone.utc).isoformat()}

        result_value, quality, alarm_msg = script_engine.execute(
            script_id=script.id, code=script.code,
            raw_value=value, history=history,
            tag_config=tag_config, context=context,
            timeout_ms=script.timeout_ms,
        )

        if result_value is None and quality == "bad":
            logger.warning(f"Script {script.id} failed for tag {tag.name}: {alarm_msg}")
            return value, quality, alarm_msg  # return original value with bad quality

        return result_value if result_value is not None else value, quality, alarm_msg

    def _update_device_status(self, device_id: int, status: str, error: Optional[str]):
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.status = status
                device.last_error = error
                db.commit()
                try:
                    from app.engine.ws_broadcast import broadcast_device_status
                    broadcast_device_status(device_id, device.name, status, error)
                except Exception:
                    pass
        except Exception:
            db.rollback()
        finally:
            db.close()


# Global instance
modbus_engine = ModbusEngine()
