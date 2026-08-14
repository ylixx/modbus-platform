"""Self-test: start the simulator in-process, connect real clients, verify闭环.

Run:
    python selftest.py
It starts all simulated devices, then uses pymodbus (sync client), asyncua (client)
and paho (pub/sub) to confirm each protocol actually serves data. No platform
required. Each protocol test is independent (one failing does not abort the rest).
"""
import asyncio
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config import load_scenarios
from run_simulator import Simulator


def _test_modbus():
    from pymodbus.client import ModbusTcpClient
    print("[selftest] -> Modbus-TCP @127.0.0.1:15021")
    try:
        c = ModbusTcpClient(host="127.0.0.1", port=15021)
        assert c.connect(), "connect failed"
        r = c.read_holding_registers(0, 2, slave=1)
        print(f"           holding[0..1] = {r.registers if not r.isError() else r}  (温度原始寄存器)")
        c1 = c.read_coils(0, 1, slave=1)
        print(f"           coil[0]      = {c1.bits[0] if not c1.isError() else c1}  (pump_running)")
        c.close()
        return not r.isError()
    except Exception as e:
        print(f"           Modbus 测试异常: {e}")
        return False


async def _test_opc():
    from asyncua import Client
    print("[selftest] -> OPC-UA opc.tcp://127.0.0.1:4840")
    try:
        async with Client(url="opc.tcp://127.0.0.1:4840") as cl:
            val = await cl.get_node("ns=2;s=TankLevel").read_value()
            print(f"           TankLevel = {val}")
            return val is not None
    except Exception as e:
        print(f"           OPC-UA 测试异常: {e}")
        return False


async def _test_mqtt():
    import json
    import paho.mqtt.client as mqtt
    print("[selftest] -> MQTT broker @127.0.0.1:1883 (topic sim/humidity)")
    got = {}

    def on_connect(cl, u, f, rc, p=None):
        cl.subscribe("sim/humidity")

    def on_message(cl, u, msg):
        try:
            got["v"] = json.loads(msg.payload.decode()).get("value")
        except Exception:
            pass

    try:
        cl = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id="selftest", protocol=mqtt.MQTTv311)
        cl.on_connect = on_connect
        cl.on_message = on_message
        cl.connect("127.0.0.1", 1883, 60)
        cl.loop_start()
        # NOTE: 模拟器的 MQTT broker 跑在主事件循环上；这里必须用 await 让出循环，
        # 否则 broker 任务拿不到调度，消息无法 relay。不能用 time.sleep 阻塞。
        for _ in range(20):
            if "v" in got:
                break
            await asyncio.sleep(0.5)
        cl.loop_stop()
        cl.disconnect()
        if "v" in got:
            print(f"           sim/humidity = {got['v']}")
            return True
        print("           未收到 sim/humidity 遥测")
        return False
    except Exception as e:
        print(f"           MQTT 测试异常: {e}")
        return False


async def _test_writes():
    """验证三类协议的可写点位 round-trip（平台写 -> 回读）。"""
    from pymodbus.client import ModbusTcpClient
    from asyncua import Client
    import json
    import paho.mqtt.client as mqtt
    from modbus_codec_local import encode_registers, decode_registers

    res = {"mb": False, "opc": False, "mq": False}

    # ---- Modbus: coil0(True) + holding4(float32=55) ----
    print("[selftest] -> 写 Modbus (coil0=True, holding[4]=55.0)")
    try:
        c = ModbusTcpClient(host="127.0.0.1", port=15021)
        assert c.connect(), "modbus connect failed"
        c.write_coil(0, True, slave=1)
        rr = c.read_coils(0, 1, slave=1)
        coil_ok = (not rr.isError()) and rr.bits[0] is True
        regs = encode_registers(55.0, "float32", "big_endian")
        c.write_registers(4, regs, slave=1)
        hr = c.read_holding_registers(4, 2, slave=1)
        val = decode_registers(hr.registers, "float32", "big_endian") if not hr.isError() else None
        reg_ok = val is not None and abs(val - 55.0) < 0.01
        c.close()
        print(f"           coil0={rr.bits[0] if not rr.isError() else rr}  "
              f"setpoint={val}")
        res["mb"] = bool(coil_ok and reg_ok)
    except Exception as e:
        print(f"           Modbus 写测试异常: {e}")

    # ---- OPC-UA: write ns=2;s=ValveSetpoint = 123.4 ----
    print("[selftest] -> 写 OPC-UA (ValveSetpoint=123.4)")
    try:
        async with Client(url="opc.tcp://127.0.0.1:4840") as cl:
            node = cl.get_node("ns=2;s=ValveSetpoint")
            await node.write_value(123.4)
            await asyncio.sleep(0.3)
            v = await node.read_value()
            res["opc"] = abs(float(v) - 123.4) < 0.01
            print(f"           ValveSetpoint readback={v}")
    except Exception as e:
        print(f"           OPC-UA 写测试异常: {e}")

    # ---- MQTT: publish sim/target_temp/set {"value":42} -> 订阅 sim/target_temp ----
    print("[selftest] -> 写 MQTT (sim/target_temp/set=42)")
    try:
        got = {}
        def on_connect(cl, u, f, rc, p=None):
            cl.subscribe("sim/target_temp")
        def on_message(cl, u, msg):
            try:
                got["v"] = json.loads(msg.payload.decode()).get("value")
            except Exception:
                pass
        w = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                        client_id="selftest-w", protocol=mqtt.MQTTv311)
        w.on_connect = on_connect
        w.on_message = on_message
        w.connect("127.0.0.1", 1883, 60)
        w.loop_start()
        await asyncio.sleep(0.5)
        w.publish("sim/target_temp/set", json.dumps({"value": 42}), qos=0)
        for _ in range(20):
            if "v" in got:
                break
            await asyncio.sleep(0.5)
        w.loop_stop()
        w.disconnect()
        res["mq"] = got.get("v") == 42
        print(f"           target_temp readback={got.get('v')}")
    except Exception as e:
        print(f"           MQTT 写测试异常: {e}")

    return res["mb"], res["opc"], res["mq"]


async def _main():
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(
        lambda loop, ctx: None
        if isinstance(ctx.get("exception"), asyncio.CancelledError)
        else loop.default_exception_handler(ctx)
    )
    sim = Simulator(load_scenarios(), only=None)
    await sim.start()
    await asyncio.sleep(3)  # let generators push a few samples
    try:
        r_mb = _test_modbus()
        r_opc = await _test_opc()
        r_mq = await _test_mqtt()
        print(f"\n[selftest] 采集(只读)结果: Modbus={'✅' if r_mb else '❌'}  "
              f"OPC-UA={'✅' if r_opc else '❌'}  MQTT={'✅' if r_mq else '❌'}")
        w_mb, w_opc, w_mq = await _test_writes()
        print(f"[selftest] 写入回读结果:   Modbus={'✅' if w_mb else '❌'}  "
              f"OPC-UA={'✅' if w_opc else '❌'}  MQTT={'✅' if w_mq else '❌'}")
    finally:
        await sim.stop()


if __name__ == "__main__":
    asyncio.run(_main())
