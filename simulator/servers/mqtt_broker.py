"""Embedded MQTT broker for the simulator (no external dependency required).

Uses amqtt, a pure-Python MQTT broker. The platform's MQTT devices connect here
as clients; the simulator's MQTT device clients also connect here to publish
telemetry and receive writes.
"""
import asyncio

from amqtt.broker import Broker


class MqttBroker:
    def __init__(self, host: str = "0.0.0.0", port: int = 1883):
        # 匿名认证由 amqtt 默认插件 (AnonymousAuthPlugin) 开启，无需额外配置
        self.config = {
            "listeners": {
                "default": {
                    "type": "tcp",
                    "bind": f"{host}:{port}",
                }
            },
        }
        self.broker = Broker(self.config)

    async def start(self):
        await self.broker.start()

    async def stop(self):
        await self.broker.shutdown()
