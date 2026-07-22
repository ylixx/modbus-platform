"""Unit tests for script_engine module."""
import pytest
from app.engine.script_engine import ScriptEngine


@pytest.fixture
def engine():
    return ScriptEngine()


class TestScriptExecution:
    def test_simple_return(self, engine):
        code = "def process(raw_value, history, tag, context):\n    return raw_value * 2"
        result = engine.test_execute(code, raw_value=50.0)
        assert result["success"] is True
        assert result["value"] == 100.0
        assert result["quality"] == "good"

    def test_with_history(self, engine):
        code = "def process(raw_value, history, tag, context):\n    if history:\n        return (history[-1] + raw_value) / 2\n    return raw_value"
        result = engine.test_execute(code, raw_value=60.0, history=[40.0, 50.0])
        assert result["success"] is True
        assert result["value"] == 55.0

    def test_with_params(self, engine):
        code = "def process(raw_value, history, tag, context):\n    a = tag.get('params', {}).get('a', 1.0)\n    b = tag.get('params', {}).get('b', 0.0)\n    return raw_value * a + b"
        result = engine.test_execute(
            code, raw_value=100.0,
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"a": 0.5, "b": 10}},
        )
        assert result["value"] == 60.0

    def test_dict_return(self, engine):
        code = "def process(raw_value, history, tag, context):\n    return {'value': raw_value, 'quality': 'good', 'alarm': None}"
        result = engine.test_execute(code, raw_value=42.0)
        assert result["value"] == 42.0
        assert result["quality"] == "good"

    def test_alarm_return(self, engine):
        code = "def process(raw_value, history, tag, context):\n    if raw_value > 100:\n        return {'value': raw_value, 'quality': 'bad', 'alarm': 'Too high'}\n    return raw_value"
        result = engine.test_execute(code, raw_value=150.0)
        assert result["value"] == 150.0
        assert result["quality"] == "bad"
        assert result["alarm"] == "Too high"


class TestScriptSanitization:
    def test_blocks_os_import(self, engine):
        code = "import os\ndef process(raw_value, history, tag, context):\n    return raw_value"
        result = engine.test_execute(code, raw_value=1.0)
        # Should still work (import is blocked, but process function exists)
        assert result["value"] == 1.0

    def test_blocks_open(self, engine):
        code = "def process(raw_value, history, tag, context):\n    f = open('/etc/passwd')\n    return raw_value"
        result = engine.test_execute(code, raw_value=1.0)
        # open is blocked in builtins, should fail gracefully
        assert result["quality"] == "bad"


class TestScriptTemplates:
    def test_linear_calibration(self, engine):
        code = "def process(raw_value, history, tag, context):\n    a = tag.get('params', {}).get('a', 1.0)\n    b = tag.get('params', {}).get('b', 0.0)\n    return raw_value * a + b"
        result = engine.test_execute(
            code, raw_value=100.0,
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"a": 0.1, "b": 5}},
        )
        assert result["value"] == 15.0

    def test_moving_average(self, engine):
        code = "def process(raw_value, history, tag, context):\n    window = tag.get('params', {}).get('window', 10)\n    values = history[-(window-1):] + [raw_value]\n    return sum(values) / len(values)"
        result = engine.test_execute(
            code, raw_value=30.0, history=[10.0, 20.0],
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"window": 3}},
        )
        assert result["value"] == 20.0

    def test_dead_band(self, engine):
        code = "def process(raw_value, history, tag, context):\n    deadband = tag.get('params', {}).get('deadband', 1.0)\n    if history and abs(raw_value - history[-1]) < deadband:\n        return history[-1]\n    return raw_value"
        # Within deadband
        result = engine.test_execute(
            code, raw_value=100.5, history=[100.0],
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"deadband": 1.0}},
        )
        assert result["value"] == 100.0  # kept previous

        # Outside deadband
        result = engine.test_execute(
            code, raw_value=102.0, history=[100.0],
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"deadband": 1.0}},
        )
        assert result["value"] == 102.0  # new value

    def test_range_mapper(self, engine):
        code = "def process(raw_value, history, tag, context):\n    p = tag.get('params', {})\n    in_min = p.get('in_min', 4)\n    in_max = p.get('in_max', 20)\n    out_min = p.get('out_min', 0)\n    out_max = p.get('out_max', 100)\n    if in_max == in_min:\n        return out_min\n    return (raw_value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min"
        # 4-20mA -> 0-100%, input 12mA should be 50%
        result = engine.test_execute(
            code, raw_value=12.0,
            tag_config={"name": "test", "unit": "", "scale_factor": 1, "offset": 0, "params": {"in_min": 4, "in_max": 20, "out_min": 0, "out_max": 100}},
        )
        assert abs(result["value"] - 50.0) < 0.01


class TestScriptErrors:
    def test_syntax_error(self, engine):
        code = "def process(raw_value, history, tag, context):\n    return raw_value +"
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_no_process_function(self, engine):
        code = "x = 1 + 1"
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_division_by_zero(self, engine):
        code = "def process(raw_value, history, tag, context):\n    return raw_value / 0"
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"
