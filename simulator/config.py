"""Load simulator scenario definitions from scenarios.yaml."""
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def load_scenarios(path: str = None) -> dict:
    path = path or os.path.join(HERE, "scenarios.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def device_defaults(scenarios: dict) -> dict:
    return scenarios.get("defaults", {})
