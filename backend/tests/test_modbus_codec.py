"""Unit tests for modbus_codec module."""
import pytest
import struct
from app.engine.modbus_codec import (
    get_register_count, decode_value, decode_32bit, decode_float32,
    decode_float64, bcd_to_int,
)
from app.models.device import DataType, ByteOrder


class TestGetRegisterCount:
    def test_bool(self):
        assert get_register_count(DataType.BOOL) == 1

    def test_int16(self):
        assert get_register_count(DataType.INT16) == 1

    def test_int32(self):
        assert get_register_count(DataType.INT32) == 2

    def test_float32(self):
        assert get_register_count(DataType.FLOAT32) == 2

    def test_float64(self):
        assert get_register_count(DataType.FLOAT64) == 4

    def test_custom_count(self):
        assert get_register_count(DataType.STRING, 10) == 10


class TestDecodeInt16:
    def test_positive(self):
        assert decode_value([100], 0, DataType.INT16, ByteOrder.BIG_ENDIAN, function_code="holding_register") == 100

    def test_negative(self):
        assert decode_value([0xFFFF], 0, DataType.INT16, ByteOrder.BIG_ENDIAN, function_code="holding_register") == -1

    def test_zero(self):
        assert decode_value([0], 0, DataType.INT16, ByteOrder.BIG_ENDIAN, function_code="input_register") == 0


class TestDecodeUint16:
    def test_value(self):
        assert decode_value([65535], 0, DataType.UINT16, ByteOrder.BIG_ENDIAN, function_code="holding_register") == 65535


class TestDecodeBool:
    def test_coil_true(self):
        assert decode_value([True], 0, DataType.BOOL, ByteOrder.BIG_ENDIAN, function_code="coil") == 1

    def test_coil_false(self):
        assert decode_value([False], 0, DataType.BOOL, ByteOrder.BIG_ENDIAN, function_code="coil") == 0

    def test_register_bit(self):
        assert decode_value([0b1010], 0, DataType.BOOL, ByteOrder.BIG_ENDIAN, bit_index=1, function_code="holding_register") == 1

    def test_register_bit_zero(self):
        assert decode_value([0b1010], 0, DataType.BOOL, ByteOrder.BIG_ENDIAN, bit_index=0, function_code="holding_register") == 0


class TestDecodeInt32:
    def test_big_endian(self):
        # 0x00010000 = 65536
        assert decode_value([1, 0], 0, DataType.INT32, ByteOrder.BIG_ENDIAN, function_code="holding_register") == 65536

    def test_little_endian(self):
        # Little endian: reg[0]=low, reg[1]=high
        assert decode_value([0, 1], 0, DataType.INT32, ByteOrder.LITTLE_ENDIAN, function_code="holding_register") == 65536


class TestDecodeFloat32:
    def test_big_endian(self):
        # Encode 3.14 as float32 big endian
        raw = struct.pack(">f", 3.14)
        reg1, reg2 = struct.unpack(">HH", raw)
        result = decode_value([reg1, reg2], 0, DataType.FLOAT32, ByteOrder.BIG_ENDIAN, function_code="holding_register")
        assert abs(result - 3.14) < 0.001


class TestDecodeFloat64:
    def test_big_endian(self):
        raw = struct.pack(">d", 3.141592653589793)
        regs = struct.unpack(">HHHH", raw)
        result = decode_value(list(regs), 0, DataType.FLOAT64, ByteOrder.BIG_ENDIAN, function_code="holding_register")
        assert abs(result - 3.141592653589793) < 1e-10


class TestBcdToInt:
    def test_1234(self):
        # BCD 0x1234 = 1234
        assert bcd_to_int(0x1234) == 1234

    def test_0(self):
        assert bcd_to_int(0x0000) == 0

    def test_invalid_bcd(self):
        # 0xABCD has digits > 9, should return raw
        assert bcd_to_int(0xABCD) == 0xABCD


class TestDecodeString:
    def test_ascii(self):
        # "AB" = 0x4142
        assert decode_value([0x4142], 0, DataType.STRING, ByteOrder.BIG_ENDIAN, function_code="holding_register", register_count=1) == "AB"


class TestEdgeCases:
    def test_none_values(self):
        assert decode_value(None, 0, DataType.INT16, ByteOrder.BIG_ENDIAN) is None

    def test_empty_list(self):
        assert decode_value([], 0, DataType.INT16, ByteOrder.BIG_ENDIAN) is None

    def test_offset_out_of_range(self):
        assert decode_value([100], 5, DataType.INT16, ByteOrder.BIG_ENDIAN, function_code="holding_register") is None


class TestLittleEndian:
    def test_int32_little_endian(self):
        # reg[0]=low, reg[1]=high -> [0, 1] == 65536
        assert decode_value([0, 1], 0, DataType.INT32, ByteOrder.LITTLE_ENDIAN, function_code="holding_register") == 65536

    def test_int32_little_endian_swap(self):
        # LITTLE_SWAP: reg[0]=high, reg[1]=low -> [1, 0] == 65536
        assert decode_value([1, 0], 0, DataType.INT32, ByteOrder.LITTLE_ENDIAN_SWAP, function_code="holding_register") == 65536

    def test_float32_little_endian(self):
        raw = struct.pack("<f", 3.14)
        reg1, reg2 = struct.unpack("<HH", raw)
        result = decode_value([reg1, reg2], 0, DataType.FLOAT32, ByteOrder.LITTLE_ENDIAN, function_code="holding_register")
        assert abs(result - 3.14) < 0.001

    def test_float64_little_endian(self):
        raw = struct.pack("<d", 3.141592653589793)
        r1, r2, r3, r4 = struct.unpack("<HHHH", raw)
        result = decode_value([r1, r2, r3, r4], 0, DataType.FLOAT64, ByteOrder.LITTLE_ENDIAN, function_code="holding_register")
        assert abs(result - 3.141592653589793) < 1e-10

    def test_float32_little_endian_swap(self):
        raw = struct.pack("<f", 3.14)
        # SWAP swaps the two words
        reg2, reg1 = struct.unpack("<HH", raw)
        result = decode_value([reg1, reg2], 0, DataType.FLOAT32, ByteOrder.LITTLE_ENDIAN_SWAP, function_code="holding_register")
        assert abs(result - 3.14) < 0.001
