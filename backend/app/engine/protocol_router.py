"""Protocol router — dispatches operations to the correct engine."""
from typing import Optional
from app.models.device import Device, DeviceTag, ProtocolType


class ProtocolRouter:
    """Unified interface over Modbus / MQTT / OPC-UA engines."""

    def __init__(self):
        self._modbus = None
        self._mqtt = None
        self._opcua = None

    def init(self):
        from app.engine.modbus_engine_v2 import modbus_engine_v2
        from app.engine.mqtt_engine import mqtt_engine
        from app.engine.opcua_engine import opcua_engine
        self._modbus = modbus_engine_v2
        self._mqtt = mqtt_engine
        self._opcua = opcua_engine

    def start_all(self):
        self.init()
        self._modbus.start()
        self._mqtt.start()
        self._opcua.start()

    def stop_all(self):
        if self._modbus:
            self._modbus.stop()
        if self._mqtt:
            self._mqtt.stop()
        if self._opcua:
            self._opcua.stop()

    def reload_device(self, device_id: int, protocol: str = None):
        """Stop old session, then start a new one for the device."""
        if not protocol:
            protocol = self._get_protocol(device_id)
        if not protocol:
            return

        if protocol == ProtocolType.MQTT:
            self._mqtt.reload_device(device_id)
        elif protocol == ProtocolType.OPC_UA:
            self._opcua.reload_device(device_id)
        else:
            self._modbus.reload_device(device_id)

    def stop_device(self, device_id: int, protocol: str = None):
        """Stop polling/connecting for a single device (used on delete)."""
        if not protocol:
            protocol = self._get_protocol(device_id)
        if not protocol:
            return

        if protocol == ProtocolType.MQTT:
            self._mqtt._stop_device(device_id)
        elif protocol == ProtocolType.OPC_UA:
            self._opcua._stop_device(device_id)
        else:
            task = self._modbus._tasks.pop(device_id, None)
            if task and not task.done():
                task.cancel()

    def write_value(self, device_id: int, tag: DeviceTag, value, protocol: str = None) -> bool:
        if not protocol:
            protocol = self._get_protocol(device_id)

        if protocol == ProtocolType.MQTT:
            return self._mqtt.write_value(device_id, tag, value)
        elif protocol == ProtocolType.OPC_UA:
            return self._opcua.write_value(device_id, tag, value)
        else:
            return self._modbus.write_value(device_id, tag, value)

    def get_live_values(self, device_id: int, protocol: str = None) -> dict:
        if protocol == ProtocolType.MQTT:
            return self._mqtt.get_live_values(device_id)
        elif protocol == ProtocolType.OPC_UA:
            return self._opcua.get_live_values(device_id)
        else:
            return self._modbus.get_live_values(device_id)

    def _get_protocol(self, device_id: int) -> Optional[str]:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            return device.protocol if device else None
        finally:
            db.close()


# Global instance
protocol_router = ProtocolRouter()
