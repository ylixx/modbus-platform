"""MQTT engine — orchestrator for standard and gateway sessions.

Imports from:
  - mqtt_utils.py    — shared helpers
  - mqtt_session.py  — MqttDeviceSession (one connection per device)
  - mqtt_gateway.py  — MqttGatewaySession (one connection for many devices)
"""
import threading
from loguru import logger
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag, ProtocolType
from app.engine.mqtt_utils import MqttPayloadFormat
from app.engine.mqtt_session import MqttDeviceSession
from app.engine.mqtt_gateway import MqttGatewaySession


class MqttEngine:
    """Manages all MQTT sessions (standard + ThingsBoard gateway)."""

    def __init__(self):
        self._sessions: dict[int, MqttDeviceSession] = {}
        self._gateways: dict[int, MqttGatewaySession] = {}
        self._device_to_gateway: dict[int, int] = {}
        self._lock = threading.Lock()

    def start(self):
        logger.info("MQTT engine starting...")
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(
                Device.protocol == ProtocolType.MQTT,
                Device.enabled == True,
            ).all()

            # 启动时将所有启用设备状态重置为 offline，避免残留旧的 online 状态
            for device in devices:
                if device.status in ("online", "no-data"):
                    device.status = "offline"
                    device.last_error = None
            try:
                db.commit()
            except Exception:
                db.rollback()

            gateway_devices = []
            standard_devices = []
            for d in devices:
                if d.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD and d.mqtt_is_gateway:
                    gateway_devices.append(d)
                else:
                    standard_devices.append(d)

            for gw in gateway_devices:
                managed = [
                    d for d in devices
                    if d.id != gw.id
                    and d.mqtt_broker == gw.mqtt_broker
                    and d.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD
                    and not d.mqtt_is_gateway
                ]
                session = MqttGatewaySession(gw, managed)
                session.start()
                self._gateways[gw.id] = session
                for md in managed:
                    self._device_to_gateway[md.id] = gw.id

            for d in standard_devices:
                if d.id not in self._device_to_gateway:
                    self._start_standard(d)
        finally:
            db.close()

    def stop(self):
        logger.info("MQTT engine stopping...")
        for s in self._sessions.values():
            s.stop()
        for s in self._gateways.values():
            s.stop()
        self._sessions.clear()
        self._gateways.clear()
        self._device_to_gateway.clear()

    def reload_device(self, device_id: int):
        self._sessions.pop(device_id, None)
        gw_id = self._device_to_gateway.pop(device_id, None)
        if gw_id and gw_id in self._gateways:
            self._gateways[gw_id].stop()
            del self._gateways[gw_id]

        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if device and device.enabled and device.protocol == ProtocolType.MQTT:
                if device.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD and device.mqtt_is_gateway:
                    managed = [
                        d for d in db.query(Device).filter(
                            Device.protocol == ProtocolType.MQTT,
                            Device.enabled == True,
                            Device.mqtt_payload_format == MqttPayloadFormat.THINGSBOARD,
                            Device.mqtt_is_gateway == False,
                        ).all()
                        if d.mqtt_broker == device.mqtt_broker
                    ]
                    session = MqttGatewaySession(device, managed)
                    session.start()
                    self._gateways[device.id] = session
                else:
                    self._start_standard(device)
        finally:
            db.close()

    def _start_standard(self, device: Device):
        with self._lock:
            if device.id in self._sessions:
                return
            tags = [t for t in device.tags if t.enabled]
            session = MqttDeviceSession(device)
            session.start(tags)
            self._sessions[device.id] = session
            logger.info(f"MQTT session started for device '{device.name}'")

    def _stop_device(self, device_id: int):
        with self._lock:
            session = self._sessions.pop(device_id, None)
            if session:
                session.stop()

    def write_value(self, device_id: int, tag: DeviceTag, value) -> bool:
        gw_id = self._device_to_gateway.get(device_id)
        if gw_id and gw_id in self._gateways:
            return self._gateways[gw_id].write_value(device_id, tag, value)
        session = self._sessions.get(device_id)
        if session:
            return session.write_value(tag, value)
        return False

    def get_live_values(self, device_id: int) -> dict:
        gw_id = self._device_to_gateway.get(device_id)
        if gw_id and gw_id in self._gateways:
            return self._gateways[gw_id].get_live_values(device_id)
        session = self._sessions.get(device_id)
        if session:
            return session.get_live_values()
        return {}


# Global instance
mqtt_engine = MqttEngine()
