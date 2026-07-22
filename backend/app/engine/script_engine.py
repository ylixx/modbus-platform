"""Script engine — sandboxed execution of user-defined data processing scripts.

Pipeline: raw_value → script.process() → processed value → store/alarm/display

Script contract:
    def process(raw_value: float, history: list[float], tag_config: dict, context: dict) -> float | dict

    Parameters:
        raw_value  — the raw value read from device
        history    — list of recent processed values (newest last)
        tag_config — {name, unit, scale_factor, offset, params, ...}
        context    — {device_id, tag_id, timestamp, ...}

    Returns:
        float — processed value (quality=good)
        dict  — {value: float, quality?: str, alarm?: str}
"""
import signal
import traceback
import ast
import hashlib
from typing import Optional
from loguru import logger
from datetime import datetime, timezone

# ── Sandbox: restricted builtins ──

SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "frozenset": frozenset,
    "int": int, "isinstance": isinstance, "len": len, "list": list, "map": map,
    "max": max, "min": min, "pow": pow, "print": print, "range": range,
    "round": round, "set": set, "slice": slice, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "zip": zip,
    "True": True, "False": False, "None": None,
}

# Safe math functions
SAFE_MATH = {
    "abs": abs, "ceil": __import__("math").ceil, "floor": __import__("math").floor,
    "sqrt": __import__("math").sqrt, "log": __import__("math").log,
    "log10": __import__("math").log10, "exp": __import__("math").exp,
    "sin": __import__("math").sin, "cos": __import__("math").cos,
    "tan": __import__("math").tan, "atan": __import__("math").atan,
    "pi": __import__("math").pi, "e": __import__("math").e,
    "isnan": __import__("math").isnan, "isinf": __import__("math").isinf,
}


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("Script execution timed out")


class ScriptEngine:
    """Executes user scripts in a sandboxed environment."""

    def __init__(self):
        # Cache compiled scripts: script_id -> (code_object, source_hash)
        self._cache: dict[int, tuple] = {}

    def execute(
        self,
        script_id: int,
        code: str,
        raw_value: float,
        history: list,
        tag_config: dict,
        context: dict,
        timeout_ms: int = 1000,
    ) -> tuple[Optional[float], str, Optional[str]]:
        """Execute a script and return (value, quality, alarm_message).

        Returns:
            (processed_value, quality, alarm_msg) on success
            (None, 'bad', error_msg) on failure
        """
        try:
            # Compile and cache
            compiled = self._get_compiled(script_id, code)

            # Prepare sandbox namespace
            namespace = {
                "__builtins__": SAFE_BUILTINS,
                "math": type("MathModule", (), SAFE_MATH)(),
                "raw_value": raw_value,
                "history": history[-(tag_config.get("max_history", 100)):],
                "tag": tag_config,
                "context": context,
                "datetime": datetime,
            }

            # Execute with timeout (Unix only via signal)
            try:
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000.0)
            except (AttributeError, ValueError):
                pass  # Windows — no SIGALRM support

            exec(compiled, namespace)

            try:
                signal.alarm(0)
            except (AttributeError, ValueError):
                pass

            # Get the process function
            process_fn = namespace.get("process")
            if not process_fn or not callable(process_fn):
                return None, "bad", "Script must define: def process(raw_value, history, tag, context)"

            # Call process()
            result = process_fn(raw_value, history, tag_config, context)

            # Parse result
            if isinstance(result, dict):
                value = result.get("value")
                quality = result.get("quality", "good")
                alarm = result.get("alarm")
                return value, quality, alarm
            elif isinstance(result, (int, float)):
                return float(result), "good", None
            else:
                return None, "bad", f"Script must return float or dict, got {type(result).__name__}"

        except TimeoutError:
            logger.warning(f"Script {script_id} timed out after {timeout_ms}ms")
            return None, "bad", f"脚本执行超时 ({timeout_ms}ms)"
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.warning(f"Script {script_id} error: {error_msg}")
            return None, "bad", error_msg

    def test_execute(
        self,
        code: str,
        raw_value: float = 0.0,
        history: list = None,
        tag_config: dict = None,
        timeout_ms: int = 1000,
    ) -> dict:
        """Test execute a script with sample data. Returns full result info."""
        context = {"device_id": 0, "tag_id": 0, "timestamp": datetime.now(timezone.utc).isoformat()}
        tag = tag_config or {"name": "test", "unit": "", "scale_factor": 1.0, "offset": 0, "params": {}}
        hist = history or []

        value, quality, alarm = self.execute(
            script_id=0, code=code, raw_value=raw_value,
            history=hist, tag_config=tag, context=context,
            timeout_ms=timeout_ms,
        )

        return {
            "success": quality != "bad" or alarm is None,
            "value": value,
            "quality": quality,
            "alarm": alarm,
            "input": {"raw_value": raw_value, "history": hist},
        }

    # Names whose invocation is never allowed in user scripts.
    FORBIDDEN_NAMES = {
        "eval", "exec", "open", "__import__", "compile",
        "globals", "locals", "vars", "getattr", "setattr",
        "delattr", "memoryview", "breakpoint",
    }

    def _validate_ast(self, code: str) -> None:
        """Parse user code and reject constructs that could escape the sandbox.

        The namespace already restricts builtins, but instance attribute
        traversal (e.g. ``().__class__.__bases__[0].__subclasses__()``)
        can still reach dangerous objects, so dunder attribute access
        and dangerous call targets are blocked here.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ValueError(f"脚本语法错误：{e}")

        for node in ast.walk(tree):
            # NOTE: top-level imports are neutralized (commented out) by
            # _sanitize(), so they are intentionally NOT rejected here — that
            # would break legit scripts that write `import math` and rely on
            # the namespace. We only hard-block the actual escape vectors.
            if isinstance(node, ast.Attribute):
                # Block dunder access: __class__, __subclasses__, __bases__, __globals__ ...
                if node.attr.startswith("__") or node.attr.endswith("__"):
                    raise ValueError(f"脚本不允许访问特殊属性：{node.attr}")
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in self.FORBIDDEN_NAMES:
                    raise ValueError(f"脚本不允许调用：{func.id}")
                if isinstance(func, ast.Attribute) and func.attr in self.FORBIDDEN_NAMES:
                    raise ValueError(f"脚本不允许调用：{func.attr}")

    def _get_compiled(self, script_id: int, code: str):
        """Get compiled code object, using cache if available."""
        # Reject unsafe constructs up-front (RCE hardening).
        self._validate_ast(code)

        # Stable, process-independent hash for the cache key.
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        cached = self._cache.get(script_id)
        if cached and cached[1] == code_hash:
            return cached[0]

        # Remove script-level imports and dangerous statements
        safe_code = self._sanitize(code)
        compiled = compile(safe_code, f"<script_{script_id}>", "exec")
        self._cache[script_id] = (compiled, code_hash)
        return compiled

    def _sanitize(self, code: str) -> str:
        """Basic sanitization — block dangerous imports and statements."""
        dangerous = ["import os", "import sys", "import io", "import subprocess",
                     "import shutil", "import socket", "import http", "import urllib",
                     "open(", "exec(", "eval(", "__import__", "globals()",
                     "os.system", "os.popen", "os.remove", "os.rmdir"]
        lines = code.split("\n")
        safe_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip dangerous lines
            if any(d in stripped for d in dangerous):
                safe_lines.append(f"# BLOCKED: {stripped}")
                continue
            # Skip import statements (we provide math via namespace)
            if stripped.startswith("import ") or stripped.startswith("from "):
                safe_lines.append(f"# BLOCKED: {stripped}")
                continue
            safe_lines.append(line)
        return "\n".join(safe_lines)

    def invalidate_cache(self, script_id: int):
        """Clear cached compilation for a script."""
        self._cache.pop(script_id, None)


# Global instance
script_engine = ScriptEngine()
