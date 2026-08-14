"""Self-contained Modbus register codec for the simulator.

Mirrors the platform's decode logic (backend/app/engine/modbus_codec.py) so that
values produced here are decoded identically by the platform. No dependency on the
backend app is introduced on purpose — the simulator must run standalone.

Only `encode_registers` (simulator -> wire) is needed at runtime. `decode_registers`
is provided for symmetry / round-trip self-tests.
"""
import struct


def _words_big(b: bytes):
    return [(b[i] << 8) | b[i + 1] for i in range(0, len(b), 2)]


def _words_little(b: bytes):
    return [(b[i + 1] << 8) | b[i] for i in range(0, len(b), 2)]


def _int_to_bcd(value: int) -> int:
    out = 0
    mult = 1
    value = int(value)
    for _ in range(4):
        digit = value % 10
        out += digit * mult
        mult *= 16
        value //= 10
    return out & 0xFFFF


def encode_registers(value, data_type: str, byte_order: str = "big_endian"):
    """Return list of 16-bit register values representing `value`."""
    bo = byte_order or "big_endian"
    swap = "swap" in bo
    little = "little" in bo

    if data_type == "int16":
        return _words_big(struct.pack(">h", int(round(value))))
    if data_type == "uint16":
        return _words_big(struct.pack(">H", int(round(value)) & 0xFFFF))
    if data_type == "bcd":
        return _words_big(struct.pack(">H", _int_to_bcd(int(round(value)))))

    fmt = "<" if little else ">"
    if data_type in ("int32", "uint32"):
        fmt += "i" if data_type == "int32" else "I"
    elif data_type == "float32":
        fmt += "f"
    elif data_type == "float64":
        fmt += "d"
    else:
        return [0]

    b = struct.pack(fmt, value)
    words = _words_little(b) if little else _words_big(b)
    return words[::-1] if swap else words


def decode_registers(raw, data_type: str, byte_order: str = "big_endian"):
    """Inverse of encode_registers (used only for round-trip self-tests)."""
    bo = byte_order or "big_endian"
    swap = "swap" in bo
    little = "little" in bo
    if data_type == "int16":
        v = raw[0]
        return v - 0x10000 if v >= 0x8000 else v
    if data_type == "uint16":
        return raw[0]
    if data_type in ("int32", "uint32", "float32", "float64"):
        if swap:
            raw = list(raw)[::-1]
        order = "<" if little else ">"
        if data_type == "int32":
            return struct.unpack(order + "i", struct.pack(order + "HH", *raw))[0]
        if data_type == "uint32":
            return struct.unpack(order + "I", struct.pack(order + "HH", *raw))[0]
        if data_type == "float32":
            return struct.unpack(order + "f", struct.pack(order + "HH", *raw))[0]
        if data_type == "float64":
            return struct.unpack(order + "d", struct.pack(order + "HHHH", *raw))[0]
    return raw[0]
