"""One-click launcher for the protocol simulator.

Starts Modbus-TCP slave(s), an OPC-UA server and an embedded MQTT broker + MQTT
device clients, drives them with industrial signal generators, and watches a
control directory for scenario commands (fault injection, stop/start devices).

Usage:
    python run_simulator.py                 # start all defined devices
    python run_simulator.py --only SIM_MODBUS_PLC
    python run_simulator.py --no-seed       # (seed is manual; kept for symmetry)

Control (run in another terminal):
    python scenario_ctl.py fault SIM_MODBUS_PLC temperature spike
    python scenario_ctl.py stop SIM_MQTT_SENSOR
    python scenario_ctl.py start SIM_MQTT_SENSOR
"""
import argparse
import asyncio
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config import load_scenarios
from generators.signals import make_signal
from servers.modbus_slave import ModbusSimDevice
from servers.opcua_server import OpcUaSimServer
from servers.mqtt_broker import MqttBroker
from servers.mqtt_device import MqttSimDevice

CONTROL_DIR = os.path.join(HERE, "control")

VALID_FAULTS = ("spike", "drop", "freeze", "drift")


class SimTag:
    def __init__(self, spec: dict):
        self.spec = spec
        self.name = spec["name"]
        self.signal = make_signal(spec.get("generator", {"type": "constant", "value": 0}))
        self.fault = None
        self.fault_until = 0.0
        self.fault_level = None
        self.frozen = None

    def next_value(self, t: float = None):
        t = t or time.time()
        if self.fault and t < self.fault_until:
            base = self.signal.next(t)
            if self.fault == "spike":
                return self.fault_level if self.fault_level is not None else base * 2
            if self.fault == "drop":
                return 0
            if self.fault == "freeze":
                return self.frozen if self.frozen is not None else base
            if self.fault == "drift":
                return base + (self.fault_level or 50)
        return self.signal.next(t)

    def inject(self, mode: str, duration: int = 30, level=None):
        self.fault = mode
        self.fault_until = time.time() + duration
        self.fault_level = level
        if mode == "freeze":
            self.frozen = self.signal.next()

    def set_value(self, value, duration: int = 3600):
        self.inject("freeze", duration, level=None)
        self.frozen = value

    def clear_fault(self):
        self.fault = None


class SimDevice:
    def __init__(self, spec: dict, defaults: dict):
        self.spec = spec
        self.protocol = spec["protocol"]
        self.name = spec["name"]
        self.defaults = defaults
        self.tags = [SimTag(t) for t in spec.get("tags", [])]
        self.handle = None
        self.active = True

    def tag_by_name(self, n: str):
        return next((t for t in self.tags if t.name == n), None)


class Simulator:
    def __init__(self, scenarios: dict, only: list = None):
        self.defaults = scenarios.get("defaults", {})
        self.devices = [SimDevice(d, self.defaults) for d in scenarios.get("devices", [])]
        if only:
            self.devices = [d for d in self.devices if d.name in only]
        self.interval = float(self.defaults.get("update_interval", 2.0))
        self.opc = None
        self.broker = None
        self._tasks = []

    def _by_proto(self, proto):
        return [d for d in self.devices if d.protocol == proto]

    async def start(self):
        # Modbus-TCP slaves
        for d in self._by_proto("modbus_tcp"):
            md = ModbusSimDevice(d.spec)
            d.handle = md
            md.start()  # 线程内启动 TCP 服务，返回 None

        # OPC-UA server (single, hosts all opc devices)
        opc_devs = self._by_proto("opc_ua")
        if opc_devs:
            ep = self.defaults.get("opc_endpoint", "opc.tcp://127.0.0.1:4840")
            ns = int(self.defaults.get("opc_namespace", 2))
            srv = OpcUaSimServer(ep, ns)
            await srv.start([d.spec for d in opc_devs])
            self.opc = srv
            for d in opc_devs:
                d.handle = srv

        # MQTT broker + device clients
        mqtt_devs = self._by_proto("mqtt")
        if mqtt_devs:
            br = MqttBroker("0.0.0.0", int(self.defaults.get("mqtt_port", 1883)))
            await br.start()  # 等 broker 真正监听后再连客户端
            self.broker = br
            prefix = self.defaults.get("mqtt_prefix", "sim")
            broker_host = self.defaults.get("mqtt_broker", "127.0.0.1")
            for d in mqtt_devs:
                md = MqttSimDevice(
                    d.spec, prefix, broker_host,
                    int(self.defaults.get("mqtt_port", 1883)), self.interval,
                )
                md.start()
                d.handle = md

        self._tasks.append(asyncio.create_task(self._gen_loop()))
        self._tasks.append(asyncio.create_task(self._control_loop()))

        n_mb, n_opc, n_mq = len(self._by_proto("modbus_tcp")), len(opc_devs), len(mqtt_devs)
        print(f"[simulator] 已启动 {len(self.devices)} 个模拟设备 "
              f"(Modbus={n_mb}, OPC-UA={n_opc}, MQTT={n_mq})  | 刷新周期={self.interval}s")
        print(f"[simulator] 控制目录: {CONTROL_DIR}  (用 scenario_ctl.py 触发场景)")

    async def _gen_loop(self):
        while True:
            t = time.time()
            for d in self.devices:
                if not d.active or d.handle is None:
                    continue
                for tag in d.tags:
                    v = tag.next_value(t)
                    if d.protocol == "modbus_tcp":
                        d.handle.set_value(tag.spec, v)
                    elif d.protocol == "opc_ua":
                        await d.handle.set_value(d.name, tag.name, v)
                    elif d.protocol == "mqtt":
                        d.handle.set_value(tag.name, v)
            await asyncio.sleep(self.interval)

    async def _control_loop(self):
        os.makedirs(CONTROL_DIR, exist_ok=True)
        while True:
            for fn in os.listdir(CONTROL_DIR):
                if not fn.endswith(".json"):
                    continue
                path = os.path.join(CONTROL_DIR, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cmd = json.load(f)
                    self._apply(cmd)
                except Exception as e:
                    print(f"[control] 命令处理失败 {fn}: {e}")
                finally:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            await asyncio.sleep(1)

    def _apply(self, cmd: dict):
        device = next((d for d in self.devices if d.name == cmd.get("device")), None)
        if not device:
            print(f"[control] 未知设备: {cmd.get('device')}")
            return
        action = cmd.get("action")
        if action in ("fault", "clear", "set"):
            tag = device.tag_by_name(cmd.get("tag"))
            if not tag:
                print(f"[control] {device.name} 无点位 {cmd.get('tag')}")
                return
            if action == "fault":
                mode = cmd.get("mode", "spike")
                if mode not in VALID_FAULTS:
                    print(f"[control] 无效故障模式: {mode}")
                    return
                tag.inject(mode, int(cmd.get("duration", 30)), cmd.get("level"))
                print(f"[control] {device.name}/{tag.name} 注入故障: {mode}")
            elif action == "clear":
                tag.clear_fault()
                print(f"[control] {device.name}/{tag.name} 清除故障")
            elif action == "set":
                tag.set_value(cmd.get("value"))
                print(f"[control] {device.name}/{tag.name} 强制置值: {cmd.get('value')}")
        elif action in ("stop", "start"):
            self._toggle_device(device, action == "start")

    def _toggle_device(self, device: SimDevice, start: bool):
        device.active = start
        if device.protocol == "modbus_tcp" and device.handle:
            if start:
                md = ModbusSimDevice(device.spec)
                device.handle = md
                md.start()
            else:
                device.handle.stop()
        elif device.protocol == "mqtt" and device.handle:
            if start:
                md = MqttSimDevice(
                    device.spec, self.defaults.get("mqtt_prefix", "sim"),
                    self.defaults.get("mqtt_broker", "127.0.0.1"),
                    int(self.defaults.get("mqtt_port", 1883)), self.interval,
                )
                md.start()
                device.handle = md
            else:
                device.handle.stop()
        print(f"[control] {'启动' if start else '停止'} 设备 {device.name}")

    async def stop(self):
        for d in self.devices:
            if d.protocol == "mqtt" and d.handle:
                d.handle.stop()
        if self.opc:
            await self.opc.stop()
        for t in self._tasks:
            t.cancel()


async def _main(scenarios_path, only):
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(
        lambda loop, ctx: None
        if isinstance(ctx.get("exception"), asyncio.CancelledError)
        else loop.default_exception_handler(ctx)
    )
    sim = Simulator(load_scenarios(scenarios_path), only=only)
    await sim.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await sim.stop()


def main():
    ap = argparse.ArgumentParser(description="协议模拟器（Modbus/OPC-UA/MQTT）")
    ap.add_argument("--scenarios", default=os.path.join(HERE, "scenarios.yaml"))
    ap.add_argument("--only", nargs="*", default=None, help="只启动指定设备名")
    args = ap.parse_args()
    try:
        asyncio.run(_main(args.scenarios, args.only))
    except KeyboardInterrupt:
        print("\n[simulator] 已停止")


if __name__ == "__main__":
    main()
