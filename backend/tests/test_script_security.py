"""Security regression tests for the script sandbox.

These lock in the hardening from fix #5:
  - dunder attribute traversal (``().__class__.__subclasses__()``) is blocked
  - the ``type`` builtin is no longer exposed to user scripts
  - dangerous call targets (eval/exec/open/...) are rejected
"""
import pytest
from app.engine.script_engine import ScriptEngine


@pytest.fixture
def engine():
    return ScriptEngine()


class TestDunderEscapeBlocked:
    def test_subclasses_escape(self, engine):
        # Classic RCE escape: reach object.__subclasses__() via dunder access.
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    subs = ().__class__.__bases__[0].__subclasses__()\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_class_dunder(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    c = (1).__class__\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_globals_dunder(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    g = globals()\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"


class TestTypeBuiltinRemoved:
    def test_type_not_available(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    return type(raw_value)"
        )
        result = engine.test_execute(code, raw_value=1.0)
        # `type` is no longer in SAFE_BUILTINS -> NameError -> bad quality.
        assert result["quality"] == "bad"


class TestForbiddenCallsBlocked:
    def test_eval_blocked(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    return eval('raw_value * 2')"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_exec_blocked(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    exec('x = 1')\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"

    def test_open_blocked(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    f = open('/etc/passwd')\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["quality"] == "bad"


class TestLegitimateScriptsStillRun:
    def test_simple_still_works(self, engine):
        code = (
            "def process(raw_value, history, tag, context):\n"
            "    return raw_value * 2"
        )
        result = engine.test_execute(code, raw_value=21.0)
        assert result["quality"] == "good"
        assert result["value"] == 42.0

    def test_import_neutralized_not_rejected(self, engine):
        # `import os` should be neutralized (commented out) by _sanitize,
        # but the process() function must still run.
        code = (
            "import os\n"
            "def process(raw_value, history, tag, context):\n"
            "    return raw_value"
        )
        result = engine.test_execute(code, raw_value=1.0)
        assert result["value"] == 1.0
