"""Unit tests for utility functions."""
import pytest
from app.engine.mqtt_utils import cast_value, resolve_json_path, is_thingsboard_format, ts_to_datetime


class TestCastValue:
    def test_float(self):
        assert cast_value("3.14", "float64") == 3.14
        assert cast_value(42, "float32") == 42.0

    def test_int(self):
        assert cast_value("100", "int16") == 100
        assert cast_value(3.7, "uint16") == 3

    def test_bool(self):
        assert cast_value("true", "bool") == 1
        assert cast_value("0", "bool") == 0
        assert cast_value(True, "bool") == 1

    def test_string(self):
        assert cast_value(42, "string") == "42"

    def test_invalid(self):
        assert cast_value("abc", "float64") is None
        assert cast_value(None, "int16") is None


class TestResolveJsonPath:
    def test_simple(self):
        assert resolve_json_path({"a": 42}, "a") == 42

    def test_nested(self):
        obj = {"sensors": {"temperature": 25.5, "humidity": 80}}
        assert resolve_json_path(obj, "sensors.temperature") == 25.5

    def test_missing(self):
        assert resolve_json_path({"a": 1}, "b") is None
        assert resolve_json_path({"a": 1}, "a.b.c") is None

    def test_empty(self):
        assert resolve_json_path({}, "a") is None


class TestIsThingsboardFormat:
    def test_valid(self):
        data = {
            "Device A": [{"ts": 1483228800000, "values": {"temperature": 42}}],
            "Device B": [{"ts": 1483228800000, "values": {"humidity": 80}}],
        }
        assert is_thingsboard_format(data) is True

    def test_invalid(self):
        assert is_thingsboard_format({"temperature": 42}) is False
        assert is_thingsboard_format({}) is False
        assert is_thingsboard_format([]) is False
        assert is_thingsboard_format(None) is False

    def test_nested_non_tb(self):
        assert is_thingsboard_format({"a": {"b": 1}}) is False


class TestTsToDatetime:
    def test_valid(self):
        dt = ts_to_datetime(1483228800000)
        assert dt.year == 2017
        assert dt.month == 1
        assert dt.day == 1

    def test_zero(self):
        dt = ts_to_datetime(0)
        assert dt.year == 1970
