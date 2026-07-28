"""
Modbus TCP 异步采集引擎 v2 — 混合架构

使用共享 WriteBuffer 和 WsBatchPusher（shared_buffer.py）。
"""

import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag, FunctionCode
from app.models.history import TagHistory
from app.engine.modbus_codec import get_register_count, decode_value
from app.engine.shared_buffer import write_buffer, ws_pusher


# ═══════════════════════════════════════════════════
# WriteBuffer — 批量写入缓冲
# ModbusEngineV2 — 异步采集引擎
# ═══════════════════════════════════════════════════

class ModbusEngineV2:
    """异步 Modbus TCP 采集引擎。

    - asyncio 单线程管理所有设备连接
    - 使用共享 WriteBuffer 批量写入数据库
    - 使用共享 WsBatchPusher 批量推送 WebSocket
    """

    # 重连退避
    BACKOFF_BASE = 1.0
    BACKOFF_MAX = 60.0
    BACKOFF_MULTIPLIER = 2.0
    MAX_CONSECUTIVE_FAILURES = 50
    OFFLINE_ALARM_THRESHOLD = 3
    # 事件循环崩溃后自动重启等待时间
    RESTART_DELAY = 5.0

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._tasks: dict[int, asyncio.Task] = {}  # device_id -> task
        self._running = False
        self._live_values: dict[str, dict] = {}
        self._device_states: dict[int, dict] = {}  # device_id -> {status, error, consecutive_failures}

    def start(self):
        if self._running:
            return
        self._running = True

        # 启动 asyncio 事件循环（在专用线程中）
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True, name="modbus-asyncio")
        self._loop_thread.start()

        logger.info("ModbusEngineV2 started")

    def stop(self):
        self._running = False

        # 停止所有设备任务
        if self._loop and not self._loop.is_closed():
            for task in self._tasks.values():
                task.cancel()
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread:
            self._loop_thread.join(timeout=10)

        logger.info("ModbusEngineV2 stopped")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_start())
        except Exception as e:
            logger.error(f"AsyncIO loop error: {e}")
        finally:
            self._loop.close()
        # 事件循环异常退出后，如果引擎仍在运行状态，自动重启
        if self._running:
            logger.warning(f"Event loop exited unexpectedly, restarting in {self.RESTART_DELAY}s...")
            import time as _time
            _time.sleep(self.RESTART_DELAY)
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._run_loop, daemon=True, name="modbus-asyncio-restart")
            self._loop_thread.start()

    async def _async_start(self):
        """加载所有设备并启动采集协程。"""
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.enabled == True).all()
            for device in devices:
                self._start_device_task(device)
        finally:
            db.close()

        # 常驻：保持事件循环存活（即使启动时无启用设备），
        # 否则 run_until_complete 立即返回 → loop 被 close，
        # 之后 reload_device 无法动态启动新设备任务。
        while self._running:
            await asyncio.sleep(1)

    def _start_device_task(self, device: Device):
        device_id = device.id
        if device_id in self._tasks and not self._tasks[device_id].done():
            return

        self._device_states[device_id] = {
            "status": "offline", "error": None, "consecutive_failures": 0, "was_online": False
        }

        task = self._loop.create_task(self._device_coroutine(device))
        self._tasks[device_id] = task
        task.add_done_callback(lambda t: self._on_task_done(device_id, t))

    @staticmethod
    def _on_task_done(device_id: int, task: asyncio.Task):
        """Task 完成回调：记录异常、清理状态。"""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"Device {device_id} coroutine exited with exception: {exc}")

    def stop_device(self, device_id: int):
        """停止单个设备的采集（用于 API 层删除/禁用设备）。"""
        task = self._tasks.pop(device_id, None)
        if task and not task.done():
            task.cancel()
        self._device_states.pop(device_id, None)
        # 清理实时缓存
        prefix = f"{device_id}_"
        keys_to_remove = [k for k in self._live_values if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._live_values[k]

    def reload_device(self, device_id: int):
        """重新加载设备（配置变更后调用）。"""
        task = self._tasks.pop(device_id, None)
        if task and not task.done():
            task.cancel()

        if not self._running or not self._loop:
            return

        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.enabled:
                self._loop.call_soon_threadsafe(self._start_device_task, device)
        finally:
            db.close()

    async def _device_coroutine(self, device: Device):
        """单个设备的采集协程。"""
        from pymodbus.client import AsyncModbusTcpClient

        device_id = device.id
        device_name = device.name
        state = self._device_states[device_id]
        client = AsyncModbusTcpClient(
            host=device.host, port=device.port,
            timeout=device.timeout, retries=device.retries,
        )

        logger.info(f"[采集] 设备 {device_name}(ID={device_id}) 采集协程启动 → {device.host}:{device.port} slave={device.slave_id}")

        backoff = self.BACKOFF_BASE

        while self._running:
            try:
                # 连接
                if not client.connected:
                    logger.debug(f"[采集] 设备 {device_name}(ID={device_id}) 正在连接 {device.host}:{device.port}...")
                    connected = await client.connect()
                    if not connected:
                        state["consecutive_failures"] += 1
                        self._update_status(device_id, "error", "连接失败")

                        if state["was_online"]:
                            self._mark_tags_offline(device_id)
                            state["was_online"] = False

                        if state["consecutive_failures"] == self.OFFLINE_ALARM_THRESHOLD:
                            self._trigger_disconnect_alarm(device_id)

                        if state["consecutive_failures"] >= self.MAX_CONSECUTIVE_FAILURES:
                            self._auto_disable(device_id, f"连续 {state['consecutive_failures']} 次连接失败")
                            break

                        sleep_time = min(backoff, self.BACKOFF_MAX)
                        backoff *= self.BACKOFF_MULTIPLIER
                        await asyncio.sleep(sleep_time)
                        continue

                # 采集
                logger.debug(f"[采集] 设备 {device_name}(ID={device_id}) 开始本轮采集 ({len(tags) if 'tags' in dir() else '?'} 点位)")
                await self._poll_device_async(device_id, client, device.slave_id)

                # 恢复
                if state["consecutive_failures"] > 0:
                    logger.info(f"Device {device_id} 恢复在线")
                    from app.services.alarm_service import alarm_service
                    alarm_service.clear_disconnect(device_id)

                state["consecutive_failures"] = 0
                backoff = self.BACKOFF_BASE
                state["was_online"] = True
                self._update_status(device_id, "online", None)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Device {device_id} poll error: {e}")
                state["consecutive_failures"] += 1
                self._update_status(device_id, "error", str(e))

                if state["was_online"]:
                    self._mark_tags_offline(device_id)
                    state["was_online"] = False

                if state["consecutive_failures"] == self.OFFLINE_ALARM_THRESHOLD:
                    self._trigger_disconnect_alarm(device_id)

                if state["consecutive_failures"] >= self.MAX_CONSECUTIVE_FAILURES:
                    self._auto_disable(device_id, f"连续 {state['consecutive_failures']} 次异常: {e}")
                    break

                try:
                    client.close()
                except Exception:
                    pass

                sleep_time = min(backoff, self.BACKOFF_MAX)
                backoff *= self.BACKOFF_MULTIPLIER
                await asyncio.sleep(sleep_time)
                continue

            # 正常间隔
            logger.debug(f"[采集] 设备 {device_name}(ID={device_id}) 本轮完成，等待 {device.poll_interval}s")
            await asyncio.sleep(device.poll_interval)

        # 清理
        try:
            client.close()
        except Exception:
            pass
        self._tasks.pop(device_id, None)
        self._device_states.pop(device_id, None)
        # 清理实时缓存
        prefix = f"{device_id}_"
        keys_to_remove = [k for k in self._live_values if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._live_values[k]

    async def _poll_device_async(self, device_id: int, client, slave_id: int):
        """异步采集单个设备的所有点位。"""
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id, DeviceTag.enabled == True,
            ).all()

            groups = self._group_tags(tags)
            logger.debug(f"[采集] 设备ID={device_id}: {len(tags)} 个点位, {len(groups)} 组读取请求")

            for (fc, start_addr, count), tag_list in groups.items():
                try:
                    raw_values = await self._read_registers_async(client, slave_id, fc, start_addr, count)
                    if raw_values is None:
                        logger.warning(f"[采集] 设备ID={device_id}: FC={fc} addr={start_addr}+{count} 读取返回空")
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

                            # 脚本处理（同步，但很快）
                            processed, quality, alarm_msg = self._apply_script(db, tag, device_id, processed)

                            logger.info(f"[采集] 设备ID={device_id} 点位={tag.name} 原始值={value} 处理值={processed} 质量={quality}")

                            # 更新实时缓存
                            key = f"{device_id}_{tag.id}"
                            now_iso = datetime.now(timezone.utc).isoformat()
                            self._live_values[key] = {
                                "value": processed, "raw_value": str(value),
                                "quality": quality, "time": now_iso,
                            }

                            # 写入缓冲（不直接写 DB）
                            write_buffer.add({
                                "device_id": device_id,
                                "tag_id": tag.id,
                                "tag_name": tag.name,
                                "value": processed if quality == "good" else None,
                                "raw_value": str(value),
                                "quality": quality,
                                "recorded_at": datetime.now(timezone.utc),
                            })

                            # WebSocket 批量推送
                            ws_pusher.push_live_value(device_id, tag.id, tag.name, processed, quality)

                            # 报警评估
                            from app.services.alarm_service import alarm_service
                            alarm_service.evaluate(device_id, tag.id, tag.name, processed)

                except Exception as e:
                    logger.error(f"[采集] 设备ID={device_id}: FC={fc} addr={start_addr} 读取异常: {e}")

            # 更新最后采集时间
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.last_poll_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.error(f"[采集] 设备ID={device_id} 采集过程异常: {e}")
            db.rollback()
        finally:
            db.close()

    async def _read_registers_async(self, client, slave_id: int, fc: str, address: int, count: int):
        """异步读取寄存器。"""
        try:
            if fc == FunctionCode.COIL:
                result = await client.read_coils(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.bits[:count]
            elif fc == FunctionCode.DISCRETE_INPUT:
                result = await client.read_discrete_inputs(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.bits[:count]
            elif fc == FunctionCode.INPUT_REGISTER:
                result = await client.read_input_registers(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.registers
            elif fc == FunctionCode.HOLDING_REGISTER:
                result = await client.read_holding_registers(address, count=count, slave=slave_id)
                if result.isError():
                    return None
                return result.registers
            return None
        except Exception as e:
            logger.error(f"Async read error: FC={fc}, addr={address}: {e}")
            return None

    def _group_tags(self, tags: list[DeviceTag]) -> dict:
        """按功能码和连续地址分组。"""
        groups = {}
        fc_groups = {}
        for tag in tags:
            fc = tag.function_code
            if fc not in fc_groups:
                fc_groups[fc] = []
            fc_groups[fc].append(tag)

        for fc, tag_list in fc_groups.items():
            tag_list.sort(key=lambda t: t.address)
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
                elif tag_start <= current_end + 5:
                    current_end = max(current_end, tag_end)
                    current_tags.append(tag)
                else:
                    count = current_end - current_start
                    groups[(fc, current_start, count)] = current_tags
                    current_start = tag_start
                    current_end = tag_end
                    current_tags = [tag]

            if current_tags and current_start is not None:
                count = current_end - current_start
                groups[(fc, current_start, count)] = current_tags

        return groups

    def _apply_script(self, db, tag, device_id: int, value: float):
        """脚本处理（同步，单次执行很快 <1ms）。"""
        if not tag.script_id:
            return value, "good", None

        from app.models.script import Script
        from app.engine.script_engine import script_engine

        script = db.query(Script).filter(Script.id == tag.script_id, Script.enabled == True).first()
        if not script:
            return value, "good", None

        recent = db.query(TagHistory.value).filter(
            TagHistory.device_id == device_id, TagHistory.tag_id == tag.id,
        ).order_by(TagHistory.recorded_at.desc()).limit(script.max_history).all()
        history = [r[0] for r in reversed(recent)]

        tag_config = {"name": tag.name, "unit": tag.unit, "scale_factor": tag.scale_factor, "offset": tag.offset, "params": {}}
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

        return result_value if result_value is not None else value, quality, alarm_msg

    def _mark_tags_offline(self, device_id: int):
        """离线标记写入缓冲。"""
        db = SessionLocal()
        try:
            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id, DeviceTag.enabled == True
            ).all()
            now = datetime.now(timezone.utc)
            for tag in tags:
                key = f"{device_id}_{tag.id}"
                if key in self._live_values:
                    self._live_values[key]["quality"] = "bad"
                    self._live_values[key]["time"] = now.isoformat()

                write_buffer.add({
                    "device_id": device_id, "tag_id": tag.id, "tag_name": tag.name,
                    "value": None, "raw_value": "offline", "quality": "bad",
                    "recorded_at": now,
                })

                ws_pusher.push_live_value(device_id, tag.id, tag.name, None, "bad")

            logger.info(f"Device {device_id}: 离线标记已写入缓冲 ({len(tags)} 个点位)")
        except Exception as e:
            logger.error(f"Mark offline error: {e}")
        finally:
            db.close()

    def _trigger_disconnect_alarm(self, device_id: int):
        from app.services.alarm_service import alarm_service
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                alarm_service.evaluate_disconnect(device_id, device.name)
        finally:
            db.close()

    def _auto_disable(self, device_id: int, reason: str):
        logger.error(f"Device {device_id} 自动禁用: {reason}")
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.enabled = False
                device.status = "error"
                device.last_error = f"自动禁用: {reason}"
                db.commit()
                ws_pusher.push_device_status(device_id, device.name, "disabled", reason)
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _update_status(self, device_id: int, status: str, error: Optional[str]):
        state = self._device_states.get(device_id, {})
        if state.get("status") == status and state.get("error") == error:
            return  # 状态未变，跳过 DB 写入
        state["status"] = status
        state["error"] = error

        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device:
                device.status = status
                device.last_error = error
                db.commit()
                ws_pusher.push_device_status(device_id, device.name, status, error)
        except Exception:
            db.rollback()
        finally:
            db.close()

    def get_live_values(self, device_id: int) -> dict:
        result = {}
        for key, val in self._live_values.items():
            if key.startswith(f"{device_id}_"):
                tag_id = int(key.split("_", 1)[1])
                result[tag_id] = val
        return result

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        """写入值（同步，通过事件循环调度）。"""
        # 简化实现：直接创建同步连接写入
        from pymodbus.client import ModbusTcpClient
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                return False
            client = ModbusTcpClient(host=device.host, port=device.port, timeout=3, retries=1)
            if not client.connect():
                return False
            try:
                if tag.function_code == FunctionCode.COIL:
                    result = client.write_coil(tag.address, bool(value), slave=device.slave_id)
                elif tag.function_code == FunctionCode.HOLDING_REGISTER:
                    from pymodbus.payload import BinaryPayloadBuilder
                    from pymodbus.constants import Endian
                    if tag.data_type in ("int16", "uint16", "bcd", "bool"):
                        result = client.write_register(tag.address, int(value), slave=device.slave_id)
                    elif tag.data_type in ("int32", "uint32"):
                        encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                        if tag.data_type == "int32":
                            encoder.add_32bit_int(int(value))
                        else:
                            encoder.add_32bit_uint(int(value))
                        result = client.write_registers(tag.address, encoder.to_registers(), slave=device.slave_id)
                    elif tag.data_type == "float32":
                        encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                        encoder.add_32bit_float(float(value))
                        result = client.write_registers(tag.address, encoder.to_registers(), slave=device.slave_id)
                    elif tag.data_type == "float64":
                        encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                        encoder.add_64bit_float(float(value))
                        result = client.write_registers(tag.address, encoder.to_registers(), slave=device.slave_id)
                    else:
                        return False
                else:
                    return False
                return not result.isError()
            finally:
                client.close()
        except Exception as e:
            logger.error(f"Write error: {e}")
            return False
        finally:
            db.close()

    BACKOFF_MULTIPLIER = 2.0  # kept at class end for backward compat


# 全局实例
modbus_engine_v2 = ModbusEngineV2()
