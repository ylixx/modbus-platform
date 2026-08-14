"""OPC-UA server (simulated devices) using asyncua.

A single OPC-UA server hosts all simulated OPC-UA devices. Each device becomes a
folder; each tag becomes a variable node with the exact NodeId configured on the
platform side (e.g. "ns=2;s=TankLevel"). The platform connects as a client and
reads/writes these nodes.

Writable nodes use a read-compare latch: when the platform writes a value, the
generator stops overwriting it for a hold period so the round-trip (write ->
readback) can be observed - mirroring the Modbus behaviour.
"""
import asyncio
import time

from asyncua import Server, ua

HOLD_SECONDS = 30


class OpcUaSimServer:
    def __init__(self, endpoint: str, namespace: int = 2):
        self.endpoint = endpoint
        self.namespace = namespace
        self.server = None
        self.vars = {}          # (device_name, tag_name) -> Variable node
        self.latch_until = {}  # (device_name, tag_name) -> epoch seconds
        self.last_val = {}     # (device_name, tag_name) -> last generator value

    async def start(self, device_specs: list):
        self.server = Server()
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        # ensure namespace index 2 exists (register_namespace returns its index)
        await self.server.register_namespace("modbus-sim")
        objects = self.server.nodes.objects
        for dev in device_specs:
            folder = await objects.add_folder(
                f"ns={self.namespace};s={dev['name']}", dev["name"]
            )
            for tag in dev.get("tags", []):
                nodeid = tag["opc_node_id"]
                bname = nodeid.split("s=")[-1]
                key = (dev["name"], tag["name"])
                var = await folder.add_variable(nodeid, bname, 0.0)
                await var.set_writable()
                self.vars[key] = var
        await self.server.start()

    async def set_value(self, device_name: str, tag_name: str, value):
        var = self.vars.get((device_name, tag_name))
        if var is None:
            return
        key = (device_name, tag_name)
        # Respect external (platform) write latch
        if time.time() < self.latch_until.get(key, 0):
            return
        # Detect external write via read-compare
        if key in self.last_val:
            try:
                cur = await var.read_value()
                if cur is not None and abs(float(cur) - float(self.last_val[key])) > 1e-6:
                    self.latch_until[key] = time.time() + HOLD_SECONDS
                    # 记录外部写入值，避免后续每拍都误判为"又被外部写"而永久锁死
                    self.last_val[key] = cur
                    return
            except Exception:
                pass
        try:
            await var.write_value(value)
            self.last_val[key] = value
        except ua.UaStatusCodeError:
            await var.write_value(float(value))
            self.last_val[key] = float(value)

    async def stop(self):
        if self.server:
            await self.server.stop()
