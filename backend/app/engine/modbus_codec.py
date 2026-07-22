"""Modbus codec — register encoding/decoding functions.

Extracted from modbus_engine.py for readability and reuse.
Supports all data types and byte orders defined in the platform.
"""
import struct
from loguru import logger
from app.models.device import DataType, ByteOrder


def get_register_count(data_type: str, register_count: int = 1) -> int:
    """How many 16-bit registers a data type occupies."""
    if register_count > 1:
        return register_count
    if data_type in (DataType.INT32, DataType.UINT32, DataType.FLOAT32):
        return 2
    elif data_type == DataType.FLOAT64:
        return 4
    elif data_type == DataType.STRING:
        return register_count
    return 1


def decode_value(raw_values, offset: int, data_type: str, byte_order: str,
                 bit_index: int = None, register_count: int = 1, function_code: str = ""):
    """Decode a value from raw register/coil values.

    Args:
        raw_values: list of register values or coil bits
        offset: position in the raw_values list
        data_type: target data type
        byte_order: byte ordering for multi-register types
        bit_index: bit position for BOOL types
        register_count: number of registers for STRING
        function_code: coil/discrete_input/input_register/holding_register

    Returns:
        Decoded value or None on error
    """
    try:
        if function_code in ("coil", "discrete_input"):
            if isinstance(raw_values, list) and offset < len(raw_values):
                return 1 if raw_values[offset] else 0
            return None

        if not isinstance(raw_values, list):
            return None

        if data_type == DataType.BOOL:
            if offset < len(raw_values):
                bit = bit_index or 0
                return 1 if (raw_values[offset] >> bit) & 1 else 0

        elif data_type == DataType.INT16:
            if offset < len(raw_values):
                val = raw_values[offset]
                return val - 0x10000 if val >= 0x8000 else val

        elif data_type == DataType.UINT16:
            if offset < len(raw_values):
                return raw_values[offset]

        elif data_type == DataType.BCD:
            if offset < len(raw_values):
                return bcd_to_int(raw_values[offset])

        elif data_type in (DataType.INT32, DataType.UINT32):
            if offset + 1 < len(raw_values):
                return decode_32bit(raw_values[offset], raw_values[offset + 1], data_type, byte_order)

        elif data_type == DataType.FLOAT32:
            if offset + 1 < len(raw_values):
                return decode_float32(raw_values[offset], raw_values[offset + 1], byte_order)

        elif data_type == DataType.FLOAT64:
            if offset + 3 < len(raw_values):
                return decode_float64(
                    raw_values[offset], raw_values[offset + 1],
                    raw_values[offset + 2], raw_values[offset + 3], byte_order,
                )

        elif data_type == DataType.STRING:
            count = register_count
            if offset + count <= len(raw_values):
                raw_bytes = b""
                for i in range(count):
                    raw_bytes += raw_values[offset + i].to_bytes(2, byteorder="big")
                return raw_bytes.rstrip(b"\x00").decode("ascii", errors="replace")

    except Exception as e:
        logger.error(f"Decode error: {e}")
    return None


def decode_32bit(reg1: int, reg2: int, data_type: str, byte_order: str) -> int | None:
    if byte_order == ByteOrder.BIG_ENDIAN:
        raw = struct.pack(">HH", reg1, reg2)
    elif byte_order == ByteOrder.LITTLE_ENDIAN:
        # reg1 = low word, reg2 = high word (little-endian byte order)
        raw = struct.pack("<HH", reg1, reg2)
    elif byte_order == ByteOrder.BIG_ENDIAN_SWAP:
        raw = struct.pack(">HH", reg2, reg1)
    elif byte_order == ByteOrder.LITTLE_ENDIAN_SWAP:
        raw = struct.pack("<HH", reg2, reg1)
    else:
        raw = struct.pack("<HH", reg1, reg2)

    if data_type == DataType.INT32:
        return struct.unpack(">i", raw)[0] if byte_order in (ByteOrder.BIG_ENDIAN, ByteOrder.BIG_ENDIAN_SWAP) else struct.unpack("<i", raw)[0]
    else:
        return struct.unpack(">I", raw)[0] if byte_order in (ByteOrder.BIG_ENDIAN, ByteOrder.BIG_ENDIAN_SWAP) else struct.unpack("<I", raw)[0]


def decode_float32(reg1: int, reg2: int, byte_order: str) -> float | None:
    if byte_order == ByteOrder.BIG_ENDIAN:
        raw = struct.pack(">HH", reg1, reg2)
        return struct.unpack(">f", raw)[0]
    elif byte_order == ByteOrder.LITTLE_ENDIAN:
        # reg1 = low word, reg2 = high word (little-endian byte order)
        raw = struct.pack("<HH", reg1, reg2)
        return struct.unpack("<f", raw)[0]
    elif byte_order == ByteOrder.BIG_ENDIAN_SWAP:
        raw = struct.pack(">HH", reg2, reg1)
        return struct.unpack(">f", raw)[0]
    elif byte_order == ByteOrder.LITTLE_ENDIAN_SWAP:
        raw = struct.pack("<HH", reg2, reg1)
        return struct.unpack("<f", raw)[0]
    else:
        raw = struct.pack("<HH", reg1, reg2)
        return struct.unpack("<f", raw)[0]


def decode_float64(r1: int, r2: int, r3: int, r4: int, byte_order: str) -> float | None:
    if byte_order == ByteOrder.BIG_ENDIAN:
        raw = struct.pack(">HHHH", r1, r2, r3, r4)
        return struct.unpack(">d", raw)[0]
    elif byte_order == ByteOrder.LITTLE_ENDIAN:
        # r1 = low word ... r4 = high word (little-endian byte order)
        raw = struct.pack("<HHHH", r1, r2, r3, r4)
        return struct.unpack("<d", raw)[0]
    elif byte_order == ByteOrder.BIG_ENDIAN_SWAP:
        raw = struct.pack(">HHHH", r2, r1, r4, r3)
        return struct.unpack(">d", raw)[0]
    elif byte_order == ByteOrder.LITTLE_ENDIAN_SWAP:
        raw = struct.pack("<HHHH", r4, r3, r2, r1)
        return struct.unpack("<d", raw)[0]
    else:
        raw = struct.pack("<HHHH", r1, r2, r3, r4)
        return struct.unpack("<d", raw)[0]


def bcd_to_int(value: int) -> int:
    result = 0
    multiplier = 1
    for _ in range(4):
        digit = value & 0x0F
        if digit > 9:
            return value
        result += digit * multiplier
        multiplier *= 10
        value >>= 4
    return result
