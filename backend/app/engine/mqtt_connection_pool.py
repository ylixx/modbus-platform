"""Unified MQTT connection pool.

All MQTT clients (device subscribe, data publish, alarm publish) share
connections through this pool.  A single paho.Client is created per
unique (broker, port, username) combination and reused by reference
counting.

Key design:
  - pool_key = f"{broker}:{port}:{username or ''}"
  - Each entry tracks ref_count, connected state, publish stats
  - connect_async + loop_start for non-blocking startup
  - Exponential reconnect via paho built-in reconnect_delay_set
  - Thread-safe via _lock
"""
import ssl
import tempfile
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Callable
from loguru import logger
import paho.mqtt.client as mqtt


@dataclass
class PoolEntry:
    """One shared MQTT connection with ref counting."""
    client: mqtt.Client
    ref_count: int = 0
    connected: bool = False
    # on_connect / on_disconnect callbacks registered by callers
    on_connect_callbacks: list[Callable] = field(default_factory=list)
    on_disconnect_callbacks: list[Callable] = field(default_factory=list)
    # message handlers: topic -> callback
    topic_callbacks: dict[str, list[Callable]] = field(default_factory=dict)
    # publish stats
    publish_count: int = 0
    publish_fail_count: int = 0


class MqttConnectionPool:
    """Global singleton pool for MQTT connections."""

    def __init__(self):
        self._pool: dict[str, PoolEntry] = {}
        self._lock = threading.Lock()

    # ────────────── public API ──────────────

    @staticmethod
    def make_key(broker: str, port: int, username: str = "") -> str:
        return f"{broker}:{port}:{username or ''}"

    def acquire(
        self,
        broker: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: str = "",
        use_tls: bool = False,
        ca_cert: str = "",
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ) -> tuple[str, PoolEntry]:
        """Get or create a pooled connection. Returns (pool_key, entry).

        Callers should call release(key) when they no longer need the connection.
        """
        key = self.make_key(broker, port, username)

        with self._lock:
            if key in self._pool:
                entry = self._pool[key]
                entry.ref_count += 1
                if on_connect:
                    entry.on_connect_callbacks.append(on_connect)
                if on_disconnect:
                    entry.on_disconnect_callbacks.append(on_disconnect)
                logger.debug(f"MqttPool: acquire existing key={key}, ref_count={entry.ref_count}")
                return key, entry

            # Create new client
            cid = client_id or f"pool_{key.replace(':', '_')}_{int(time.time())}"
            client = mqtt.Client(
                client_id=cid,
                protocol=mqtt.MQTTv311,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )

            if username:
                client.username_pw_set(username, password or "")

            if use_tls:
                self._apply_tls(client, ca_cert)

            # Exponential reconnect: 1s ~ 60s
            client.reconnect_delay_set(min_delay=1, max_delay=60)

            entry = PoolEntry(client=client, ref_count=1)
            if on_connect:
                entry.on_connect_callbacks.append(on_connect)
            if on_disconnect:
                entry.on_disconnect_callbacks.append(on_disconnect)

            # Wire callbacks
            client.on_connect = self._make_on_connect(key)
            client.on_disconnect = self._make_on_disconnect(key)
            client.on_message = self._make_on_message(key)

            self._pool[key] = entry

        # Connect outside lock to avoid blocking
        try:
            client.connect_async(broker, port, keepalive=60)
            client.loop_start()
            logger.info(f"MqttPool: created & connecting key={key}")
        except Exception as e:
            logger.error(f"MqttPool: connect error key={key}: {e}")
            # Still return entry — paho will auto-reconnect

        return key, entry

    def release(self, key: str):
        """Decrement ref count. Disconnects when ref_count reaches 0."""
        with self._lock:
            entry = self._pool.get(key)
            if not entry:
                return
            entry.ref_count -= 1
            logger.debug(f"MqttPool: release key={key}, ref_count={entry.ref_count}")
            if entry.ref_count <= 0:
                self._pool.pop(key, None)

        if entry.ref_count <= 0:
            try:
                entry.client.loop_stop()
                entry.client.disconnect()
                logger.info(f"MqttPool: disconnected key={key}")
            except Exception as e:
                logger.warning(f"MqttPool: disconnect error key={key}: {e}")

    def subscribe(self, key: str, topic: str, callback: Optional[Callable] = None, qos: int = 1):
        """Subscribe a topic on a pooled connection. Optionally register a per-topic callback."""
        with self._lock:
            entry = self._pool.get(key)
            if not entry:
                logger.warning(f"MqttPool: subscribe on unknown key={key}")
                return
            if callback:
                entry.topic_callbacks.setdefault(topic, []).append(callback)

        entry.client.subscribe(topic, qos=qos)

    def unsubscribe(self, key: str, topic: str, callback: Optional[Callable] = None):
        """Unsubscribe a topic. If callback given, remove only that callback;
        if no callbacks remain for the topic, unsubscribe from broker."""
        with self._lock:
            entry = self._pool.get(key)
            if not entry:
                return
            if callback and topic in entry.topic_callbacks:
                cbs = entry.topic_callbacks[topic]
                if callback in cbs:
                    cbs.remove(callback)
                if not cbs:
                    del entry.topic_callbacks[topic]
                    entry.client.unsubscribe(topic)
            elif topic in entry.topic_callbacks:
                del entry.topic_callbacks[topic]
                entry.client.unsubscribe(topic)
            else:
                entry.client.unsubscribe(topic)

    def publish(self, key: str, topic: str, payload: bytes | str, qos: int = 0, retain: bool = False) -> bool:
        """Publish a message via a pooled connection. Returns True on success."""
        with self._lock:
            entry = self._pool.get(key)
        if not entry:
            logger.warning(f"MqttPool: publish on unknown key={key}")
            return False

        info = entry.client.publish(topic, payload, qos=qos, retain=retain)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            entry.publish_count += 1
            return True
        else:
            entry.publish_fail_count += 1
            logger.warning(f"MqttPool: publish failed key={key} topic={topic} rc={info.rc}")
            return False

    def get_stats(self) -> dict:
        """Return per-key connection stats for health monitoring."""
        with self._lock:
            result = {}
            for key, entry in self._pool.items():
                result[key] = {
                    "connected": entry.connected,
                    "ref_count": entry.ref_count,
                    "publish_count": entry.publish_count,
                    "publish_fail_count": entry.publish_fail_count,
                }
            return result

    def shutdown(self):
        """Stop all connections (app shutdown)."""
        with self._lock:
            entries = dict(self._pool)
            self._pool.clear()

        for key, entry in entries.items():
            try:
                entry.client.loop_stop()
                entry.client.disconnect()
            except Exception:
                pass
        logger.info("MqttPool: all connections shut down")

    # ────────────── internals ──────────────

    def _apply_tls(self, client: mqtt.Client, ca_cert: str):
        ctx = ssl.create_default_context()
        if ca_cert:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
            tmp.write(ca_cert.encode())
            tmp.close()
            ctx.load_verify_locations(tmp.name)
            os.unlink(tmp.name)
        else:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        client.tls_set_context(ctx)

    def _make_on_connect(self, key: str):
        def on_connect(client, userdata, flags, rc, properties=None):
            with self._lock:
                entry = self._pool.get(key)
                if not entry:
                    return
                entry.connected = (rc == 0)

            if rc == 0:
                logger.info(f"MqttPool: connected key={key}")
                # Re-subscribe all registered topics
                with self._lock:
                    topics = list(entry.topic_callbacks.keys())
                for t in topics:
                    client.subscribe(t, qos=1)
                # Fire caller callbacks
                with self._lock:
                    cbs = list(entry.on_connect_callbacks)
                for cb in cbs:
                    try:
                        cb(client, rc)
                    except Exception as e:
                        logger.error(f"MqttPool: on_connect callback error: {e}")
            else:
                logger.error(f"MqttPool: connect failed key={key} rc={rc}")
        return on_connect

    def _make_on_disconnect(self, key: str):
        def on_disconnect(client, userdata, flags, rc, properties=None):
            with self._lock:
                entry = self._pool.get(key)
                if not entry:
                    return
                entry.connected = False

            logger.warning(f"MqttPool: disconnected key={key} rc={rc}")
            with self._lock:
                cbs = list(entry.on_disconnect_callbacks)
            for cb in cbs:
                try:
                    cb(client, rc)
                except Exception as e:
                    logger.error(f"MqttPool: on_disconnect callback error: {e}")
        return on_disconnect

    def _make_on_message(self, key: str):
        def on_message(client, userdata, msg):
            with self._lock:
                entry = self._pool.get(key)
                if not entry:
                    return
                # Find matching callbacks (exact match + wildcard not supported in pool;
                # sessions should handle their own routing)
                cbs = entry.topic_callbacks.get(msg.topic, [])
                cbs_copy = list(cbs)

            for cb in cbs_copy:
                try:
                    cb(client, msg)
                except Exception as e:
                    logger.error(f"MqttPool: message callback error topic={msg.topic}: {e}")
        return on_message


# Global singleton
mqtt_pool = MqttConnectionPool()
