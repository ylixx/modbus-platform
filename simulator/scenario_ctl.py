"""Scenario control CLI for a running simulator.

Writes a command file into the simulator's control directory; run_simulator.py
picks it up within ~1s and applies it. No direct connection to the simulator
process is required.

Examples:
    python scenario_ctl.py fault SIM_MODBUS_PLC temperature spike
    python scenario_ctl.py fault SIM_OPC_TANK tank_level drop 60
    python scenario_ctl.py set   SIM_MQTT_SENSOR target_temp 25
    python scenario_ctl.py clear SIM_MODBUS_PLC temperature
    python scenario_ctl.py stop  SIM_MQTT_SENSOR
    python scenario_ctl.py start SIM_MQTT_SENSOR
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL_DIR = os.path.join(HERE, "control")
VALID_FAULTS = ("spike", "drop", "freeze", "drift")


def _send(cmd: dict):
    os.makedirs(CONTROL_DIR, exist_ok=True)
    path = os.path.join(CONTROL_DIR, f"cmd_{int(time.time()*1000)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cmd, f)
    print(f"[scenario_ctl] 已发送: {cmd}")


def main():
    ap = argparse.ArgumentParser(description="模拟器场景控制")
    sub = ap.add_subparsers(dest="action", required=True)

    p = sub.add_parser("fault")
    p.add_argument("device"); p.add_argument("tag")
    p.add_argument("mode", choices=VALID_FAULTS)
    p.add_argument("duration", nargs="?", type=int, default=30)
    p.add_argument("--level", type=float, default=None)

    p = sub.add_parser("clear")
    p.add_argument("device"); p.add_argument("tag")

    p = sub.add_parser("set")
    p.add_argument("device"); p.add_argument("tag"); p.add_argument("value", type=float)
    p.add_argument("duration", nargs="?", type=int, default=3600)

    p = sub.add_parser("stop"); p.add_argument("device")
    p = sub.add_parser("start"); p.add_argument("device")

    args = ap.parse_args()
    if args.action == "fault":
        _send({"device": args.device, "tag": args.tag, "action": "fault",
               "mode": args.mode, "duration": args.duration, "level": args.level})
    elif args.action == "clear":
        _send({"device": args.device, "tag": args.tag, "action": "clear"})
    elif args.action == "set":
        _send({"device": args.device, "tag": args.tag, "action": "set",
               "value": args.value, "duration": args.duration})
    elif args.action in ("stop", "start"):
        _send({"device": args.device, "action": args.action})


if __name__ == "__main__":
    main()
