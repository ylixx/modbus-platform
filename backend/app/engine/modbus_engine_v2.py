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


class ConnectError(Exception):
    """连接层失败（区别于 Modbus 应用层异常），需冒泡到协程做离线/重连处理。"""


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
        # 共享连接池：按 (host, port) 复用单条 TCP 连接，避免单连接类从机被并发连接踢掉
        self._clients: dict[tuple, object] = {}
        self._client_locks: dict[tuple, "asyncio.Lock"] = {}
        self._conn_lock: Optional["asyncio.Lock"] = None  # 在事件循环内创建

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
        self._conn_lock = asyncio.Lock()
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

        # 引擎停止：关闭所有共享连接
        await self._close_all_clients()

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
        device_id = device.id
        device_name = device.name
        state = self._device_states[device_id]

        logger.info(f"[采集] 设备 {device_name}(ID={device_id}) 采集协程启动 → {device.host}:{device.port} slave={device.slave_id}")

        backoff = self.BACKOFF_BASE

        while self._running:
            try:
                # 采集（共享连接池 + 串行锁 + 断线重连由引擎内部处理）
                read_ok = await self._poll_device_async(device_id, device)

                # 恢复
                if state["consecutive_failures"] > 0:
                    logger.info(f"Device {device_id} 恢复在线")
                    from app.services.alarm_service import alarm_service
                    alarm_service.clear_disconnect(device_id)

                state["consecutive_failures"] = 0
                backoff = self.BACKOFF_BASE
                state["was_online"] = True
                if read_ok is False:
                    # 连接正常，但本轮未读取到任何点位数据：区分「在线无数据」状态
                    self._update_status(
                        device_id, "no-data",
                        "连接正常，但本轮未读取到任何点位数据（请检查寄存器地址/功能码/从机ID配置）",
                    )
                else:
                    self._update_status(device_id, "online", None)

            except asyncio.CancelledError:
                break
            except ConnectError as e:
                # 连接层失败：视为离线/错误，进入退避
                logger.error(f"Device {device_id} connect error: {e}")
                state["consecutive_failures"] += 1
                self._update_status(device_id, "error", str(e))

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

                sleep_time = min(backoff, self.BACKOFF_MAX)
                backoff *= self.BACKOFF_MULTIPLIER
                await asyncio.sleep(sleep_time)
                continue

            # 正常间隔
            logger.debug(f"[采集] 设备 {device_name}(ID={device_id}) 本轮完成，等待 {device.poll_interval}s")
            await asyncio.sleep(device.poll_interval)

        # 清理
        self._tasks.pop(device_id, None)
        self._device_states.pop(device_id, None)
        # 清理实时缓存
        prefix = f"{device_id}_"
        keys_to_remove = [k for k in self._live_values if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._live_values[k]

    async def _poll_device_async(self, device_id: int, device: Device) -> Optional[bool]:
        """异步采集单个设备的所有点位。

        使用 (host, port) 共享连接 + 串行锁 + 断线重连，避免单连接类从机被并发踢掉。

        返回：
          True  - 本轮至少成功读取到一组寄存器（即真正读到数据）
          False - 设备有配置点位，但全部读取返回空（连接正常却读不到数据）
          None  - 设备无可用点位（不纳入「在线无数据」判定）
        连接失败会抛 ConnectError，由协程层做离线/重连处理。
        """
        db = SessionLocal()
        try:
            # 获取共享连接（连接失败会抛 ConnectError 冒泡到协程）
            client, lock = await self._get_client(device)

            tags = db.query(DeviceTag).filter(
                DeviceTag.device_id == device_id, DeviceTag.enabled == True,
            ).all()

            groups = self._group_tags(tags)

            if not groups:
                # 无可用点位，不纳入「在线无数据」判定
                return None

            logger.debug(f"[采集] 设备ID={device_id}: {len(tags)} 个点位, {len(groups)} 组读取请求")

            read_any = False
            for (fc, start_addr, count), tag_list in groups.items():
                try:
                    raw_values = await self._read_with_reconnect(
                        client, lock, device.slave_id, fc, start_addr, count,
                        device.host, device.port,
                    )
                    if raw_values is None:
                        logger.warning(f"[采集] 设备ID={device_id}: FC={fc} addr={start_addr}+{count} 读取返回空（应用层异常，可能地址/功能码错误）")
                        continue
                    read_any = True

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

                except ConnectError:
                    # 连接失败：向上抛出，由协程做离线/重连处理
                    raise
                except Exception as e:
                    logger.error(f"[采集] 设备ID={device_id}: FC={fc} addr={start_addr} 读取异常: {e}")

            # 更新最后采集时间
            dev_row = db.query(Device).filter(Device.id == device_id).first()
            if dev_row:
                dev_row.last_poll_at = datetime.now(timezone.utc)
            db.commit()

            return read_any

        except ConnectError:
            raise
        except Exception as e:
            logger.error(f"[采集] 设备ID={device_id} 采集过程异常: {e}")
            db.rollback()
        finally:
            db.close()

    async def _read_registers_async(self, client, slave_id: int, fc: str, address: int, count: int):
        """异步读取寄存器。

        连接层异常（断线/未连接/超时）重新抛出，由调用方重连重试；
        Modbus 应用层异常（非法地址/功能，从机回 isError）返回 None，不重试。
        """
        from pymodbus.exceptions import ModbusIOException, ConnectionException

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
        except (ModbusIOException, ConnectionException, OSError, asyncio.TimeoutError):
            # 连接层失败：重新抛出，由 _read_with_reconnect 重连后重试
            raise
        except Exception as e:
            logger.error(f"Async read error: FC={fc}, addr={address}: {e}")
            return None

    async def _get_client(self, device: Device):
        """按 (host, port) 获取或创建共享连接，并发安全。"""
        from pymodbus.client import AsyncModbusTcpClient

        key = (device.host, device.port)
        async with self._conn_lock:
            client = self._clients.get(key)
            if client is None:
                client = AsyncModbusTcpClient(
                    host=device.host, port=device.port,
                    timeout=device.timeout, retries=device.retries,
                )
                self._clients[key] = client
                self._client_locks[key] = asyncio.Lock()
            lock = self._client_locks[key]
        return client, lock

    async def _read_with_reconnect(self, client, lock, slave_id, fc, address, count, host, port):
        """在连接锁内读取；连不上或读中掉线则重连一次再试。"""
        async with lock:
            if not client.connected:
                if not await client.connect():
                    raise ConnectError(f"connect {host}:{port} failed")
            try:
                return await self._read_registers_async(client, slave_id, fc, address, count)
            except (ModbusIOException, ConnectionException, OSError, asyncio.TimeoutError) as e:
                logger.warning(f"[采集] {host}:{port} 读取连接异常({e})，重连一次")
                try:
                    await client.close()
                except Exception:
                    pass
                if not await client.connect():
                    raise ConnectError(f"reconnect {host}:{port} failed")
                return await self._read_registers_async(client, slave_id, fc, address, count)

    async def _close_all_clients(self):
        """关闭所有共享连接（引擎停止时调用）。"""
        for key, client in list(self._clients.items()):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()
        self._client_locks.clear()

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

    async def _write_via_shared_client(self, device: Device, tag: DeviceTag, value) -> bool:
        """通过共享连接池异步写值（与读共用同一连接 + 同一把锁）。

        避免单连接真机写操作新建第 2 条连接把读连接踢掉。
        连接失败抛 ConnectError；写中掉线重连一次再试。
        """
        from pymodbus.payload import BinaryPayloadBuilder
        from pymodbus.constants import Endian
        from pymodbus.exceptions import ModbusIOException, ConnectionException

        client, lock = await self._get_client(device)
        slave_id = device.slave_id

        # 构造待写报文（同步、快速）
        try:
            if tag.function_code == FunctionCode.COIL:
                async def _do_write():
                    return await client.write_coil(tag.address, bool(value), slave=slave_id)
            elif tag.function_code == FunctionCode.HOLDING_REGISTER:
                if tag.data_type in ("int16", "uint16", "bcd", "bool"):
                    iv = int(value)
                    async def _do_write():
                        return await client.write_register(tag.address, iv, slave=slave_id)
                elif tag.data_type == "int32":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_32bit_int(int(value))
                    regs = encoder.to_registers()
                    async def _do_write():
                        return await client.write_registers(tag.address, regs, slave=slave_id)
                elif tag.data_type == "uint32":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_32bit_uint(int(value))
                    regs = encoder.to_registers()
                    async def _do_write():
                        return await client.write_registers(tag.address, regs, slave=slave_id)
                elif tag.data_type == "float32":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_32bit_float(float(value))
                    regs = encoder.to_registers()
                    async def _do_write():
                        return await client.write_registers(tag.address, regs, slave=slave_id)
                elif tag.data_type == "float64":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_64bit_float(float(value))
                    regs = encoder.to_registers()
                    async def _do_write():
                        return await client.write_registers(tag.address, regs, slave=slave_id)
                else:
                    return False
            else:
                # 输入寄存器 / 离散输入只读
                return False
        except Exception as e:
            logger.error(f"[写] device {device.id} tag {tag.name} 编码失败: {e}")
            return False

        async def _ensure_connected():
            if not client.connected:
                if not await client.connect():
                    raise ConnectError(f"connect {device.host}:{device.port} failed")

        async with lock:
            try:
                await _ensure_connected()
                result = await _do_write()
                if result is not None and getattr(result, "isError", None) and result.isError():
                    logger.warning(f"[写] device {device.id} tag {tag.name} 从机返回错误: {result}")
                    return False
                return True
            except (ModbusIOException, ConnectionException, OSError, asyncio.TimeoutError) as e:
                logger.warning(f"[写] {device.host}:{device.port} 写入连接异常({e})，重连一次")
                try:
                    await client.close()
                except Exception:
                    pass
                try:
                    await _ensure_connected()
                    result = await _do_write()
                    if result is not None and getattr(result, "isError", None) and result.isError():
                        return False
                    return True
                except (ModbusIOException, ConnectionException, OSError, asyncio.TimeoutError) as e2:
                    raise ConnectError(f"write reconnect {device.host}:{device.port} failed: {e2}")
            except ConnectError:
                raise
            except Exception as e:
                logger.error(f"[写] device {device.id} tag {tag.name} 写入异常: {e}")
                return False

    def _write_via_sync_client(self, device: Device, tag: DeviceTag, value) -> bool:
        """引擎未运行时的退回实现（一次性同步连接），保证仍可写。"""
        from pymodbus.client import ModbusTcpClient
        from pymodbus.payload import BinaryPayloadBuilder
        from pymodbus.constants import Endian
        client = ModbusTcpClient(host=device.host, port=device.port, timeout=3, retries=1)
        if not client.connect():
            return False
        try:
            if tag.function_code == FunctionCode.COIL:
                result = client.write_coil(tag.address, bool(value), slave=device.slave_id)
            elif tag.function_code == FunctionCode.HOLDING_REGISTER:
                if tag.data_type in ("int16", "uint16", "bcd", "bool"):
                    result = client.write_register(tag.address, int(value), slave=device.slave_id)
                elif tag.data_type == "int32":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
                    encoder.add_32bit_int(int(value))
                    result = client.write_registers(tag.address, encoder.to_registers(), slave=device.slave_id)
                elif tag.data_type == "uint32":
                    encoder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
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

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        """写入值：复用共享连接池（与读同连接同锁），避免单连接真机写踢读。

        同步 API（由 FastAPI 线程池调用），内部通过事件循环线程安全地执行异步写。
        引擎未运行时退回一次性同步连接，保证仍可写。
        """
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                return False
        finally:
            db.close()

        loop = self._loop
        if loop is None or loop.is_closed():
            # 引擎未运行：退回一次性同步连接（原行为）
            return self._write_via_sync_client(device, tag, value)

        try:
            timeout = (device.timeout or 3) * ((device.retries or 1) + 2) + 5
            fut = asyncio.run_coroutine_threadsafe(
                self._write_via_shared_client(device, tag, value), loop
            )
            return fut.result(timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"[写] device {device_id} 写入超时（{timeout}s），连接可能被占用")
            return False
        except Exception as e:
            logger.error(f"[写] device {device_id} 写入调度失败: {e}")
            return False

    BACKOFF_MULTIPLIER = 2.0  # kept at class end for backward compat


# 全局实例
modbus_engine_v2 = ModbusEngineV2()
