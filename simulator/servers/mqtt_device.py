"""Simulated MQTT device client.

Connects to the embedded broker, publishes each tag's value as JSON
``{"value": <v>, "quality": "good", "timestamp": <ms>}`` to ``{prefix}/{tag}``,
and subscribes to ``{prefix}/{tag}/set`` so platform writes are reflected back
(readback works naturally because the next publish carries the new value).
"""
import json
import threading
import time

import paho.mqtt.client as mqtt

HOLD_SECONDS = 30  # 平台写入后保持该值，便于回读验证 round-trip


class MqttSimDevice:
    def __init__(self, spec: dict, prefix: str, broker: str, port: int, interval: float):
        self.spec = spec
        self.name = spec["name"]
        self.prefix = prefix
        self.broker = broker
        self.port = port
        self.interval = interval
        self.values = {t["name"]: 0.0 for t in spec.get("tags", [])}
        self.writable = {t["name"]: bool(t.get("writable")) for t in spec.get("tags", [])}
        self.latch_until = {}
        self.lock = threading.Lock()
        self.client = None
        self._stop = threading.Event()

    def set_value(self, tag_name: str, value):
        """Called by the generator loop. Honours the external-write latch
        for writable tags so a platform write can be observed on readback."""
        with self.lock:
            if self.writable.get(tag_name) and time.time() < self.latch_until.get(tag_name, 0):
                return  # 保持平台写入值，暂不覆盖
            self.values[tag_name] = value

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        for t in self.spec.get("tags", []):
            if t.get("writable"):
                client.subscribe(f"{self.prefix}/{t['name']}/set")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="replace"))
            value = payload.get("value")
            if value is None:
                return
            name = msg.topic.rsplit("/", 2)[-2]  # "sim/target_temp/set" -> "target_temp"
            if not self.writable.get(name):
                return
            with self.lock:
                self.values[name] = value
                self.latch_until[name] = time.time() + HOLD_SECONDS
        except Exception:
            pass

    def start(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{self.name}",
            protocol=mqtt.MQTTv311,  # amqtt 0.12 对 MQTT5 支持不全，统一用 3.1.1
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        threading.Thread(target=self._publish_loop, daemon=True).start()

    def _publish_loop(self):
        while not self._stop.is_set():
            with self.lock:
                snapshot = dict(self.values)
            for t in self.spec.get("tags", []):
                payload = json.dumps({
                    "value": snapshot.get(t["name"]),
                    "quality": "good",
                    "timestamp": int(time.time() * 1000),
                })
                self.client.publish(f"{self.prefix}/{t['name']}", payload, qos=0)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
