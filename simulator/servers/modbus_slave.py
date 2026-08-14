"""Modbus-TCP slave (simulated device) using pymodbus.

Each simulated Modbus device runs its own TCP server in a dedicated daemon thread
(classic pymodbus threaded pattern — stable across 3.x). Register/coil values are
updated from the simulator's generators via the shared datastore. Writable
registers honour an external write latch: when the platform writes a value, the
generator stops overwriting it for a hold period so the round-trip
(write -> readback) can be observed.
"""
import asyncio
import threading
import time

from pymodbus.datastore import (
    ModbusServerContext,
    ModbusSlaveContext,
    ModbusSequentialDataBlock,
)
from pymodbus.server import StartAsyncTcpServer

from modbus_codec_local import encode_registers

FC_CODE = {
    "coil": 1,
    "discrete_input": 2,
    "input_register": 4,
    "holding_register": 3,
}
HOLD_SECONDS = 30  # keep platform-written value for this long before generator resumes


class ModbusSimDevice:
    def __init__(self, spec: dict):
        self.spec = spec
        self.name = spec["name"]
        self.port = int(spec.get("port", 502))
        self.slave_id = int(spec.get("slave_id", 1))
        self.tags = spec.get("tags", [])
        self.last_regs = {}
        self.latch_until = {}
        self._thread = None
        self._loop = None
        self._task = None
        self._build_context()

    def _build_context(self):
        size = 256
        self._slave = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [False] * size),
            co=ModbusSequentialDataBlock(0, [False] * size),
            hr=ModbusSequentialDataBlock(0, [0] * size),
            ir=ModbusSequentialDataBlock(0, [0] * size),
        )
        # single=False: slaves dict maps unit_id -> slave context (must NOT be re-wrapped)
        self.context = ModbusServerContext(slaves={self.slave_id: self._slave}, single=False)

    def set_value(self, tag: dict, value):
        fc = tag["function_code"]
        addr = int(tag["address"])
        code = FC_CODE[fc]
        key = (fc, addr)
        if fc in ("coil", "discrete_input"):
            bv = [bool(value)]
            if tag.get("writable"):
                cur = self._slave.getValues(code, addr, 1)
                if cur and cur != self.last_regs.get(key):
                    self.latch_until[key] = time.time() + HOLD_SECONDS
                if time.time() < self.latch_until.get(key, 0):
                    self.last_regs[key] = cur
                    return
            self._slave.setValues(code, addr, bv)
            self.last_regs[key] = bv
        else:
            regs = encode_registers(value, tag["data_type"], tag.get("byte_order", "big_endian"))
            if tag.get("writable"):
                cur = self._slave.getValues(code, addr, len(regs))
                if cur and cur != self.last_regs.get(key):
                    self.latch_until[key] = time.time() + HOLD_SECONDS
                if time.time() < self.latch_until.get(key, 0):
                    self.last_regs[key] = cur
                    return
            self._slave.setValues(code, addr, regs)
            self.last_regs[key] = regs

    def start(self):
        self._loop = asyncio.new_event_loop()

        def _run():
            asyncio.set_event_loop(self._loop)
            self._task = self._loop.create_task(self._serve())
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    async def _serve(self):
        try:
            await StartAsyncTcpServer(context=self.context, address=("0.0.0.0", self.port))
        except asyncio.CancelledError:
            pass

    def stop(self):
        if getattr(self, "_loop", None) and self._task:
            fut = asyncio.run_coroutine_threadsafe(self._do_stop(), self._loop)
            try:
                fut.result(timeout=5)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)

    async def _do_stop(self):
        self._task.cancel()
        self._loop.call_soon(self._loop.stop)
