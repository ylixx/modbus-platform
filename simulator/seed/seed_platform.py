"""Auto-import simulator devices/tags into the running platform via REST API.

This is the "导入方式" (import method): it reads scenarios.yaml and creates the
matching devices + tags on the platform, including wiring writable tags to
readback (readback_tag_id = self). Run it while the platform backend is up.

Env / args:
    --base-url   http://127.0.0.1:8000   (default)
    --username   admin                    (default)
    --password   admin123                 (default)
    --dry-run    only print what would be created

Default credentials come from backend/app/main.py (admin / admin123).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # simulator/
import requests

from config import load_scenarios

HEADERS = {"Content-Type": "application/json"}


def _login(base, user, pwd):
    r = requests.post(f"{base}/api/v1/auth/login",
                      json={"username": user, "password": pwd}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def _device_payload(d, defaults):
    p = d["protocol"]
    base = {
        "name": d["name"],
        "description": d.get("description", ""),
        "protocol": p,
        "poll_interval": float(d.get("poll_interval", 5.0)),
        "enabled": True,
    }
    if p == "modbus_tcp":
        base.update({
            "host": defaults.get("modbus_host", "127.0.0.1"),
            "port": int(d.get("port", 502)),
            "slave_id": int(d.get("slave_id", 1)),
        })
    elif p == "opc_ua":
        base.update({
            "opc_endpoint": d.get("opc_endpoint", defaults.get("opc_endpoint")),
            "opc_namespace": int(d.get("opc_namespace", defaults.get("opc_namespace", 2))),
            "opc_security_mode": d.get("opc_security_mode", "None"),
        })
    elif p == "mqtt":
        base.update({
            "mqtt_broker": d.get("mqtt_broker", defaults.get("mqtt_broker", "127.0.0.1")),
            "mqtt_port": int(d.get("mqtt_port", defaults.get("mqtt_port", 1883))),
            "mqtt_topic_prefix": d.get("mqtt_topic_prefix", defaults.get("mqtt_prefix", "sim")),
            "mqtt_payload_format": d.get("mqtt_payload_format", "json"),
        })
    return base


def _tag_payload(t, device_id):
    tp = {
        "device_id": device_id,
        "name": t["name"],
        "description": t.get("description", ""),
        "unit": t.get("unit", ""),
        "writable": bool(t.get("writable", False)),
        "enabled": True,
    }
    if "function_code" in t:
        tp.update({
            "function_code": t["function_code"],
            "address": int(t.get("address", 0)),
            "data_type": t.get("data_type", "uint16"),
            "byte_order": t.get("byte_order", "big_endian"),
        })
    if "opc_node_id" in t:
        tp.update({
            "opc_node_id": t["opc_node_id"],
            "opc_node_type": t.get("opc_node_type", "float64"),
        })
    if "mqtt_json_path" in t:
        tp.update({
            "mqtt_json_path": t["mqtt_json_path"],
            "mqtt_value_type": t.get("mqtt_value_type", "float64"),
        })
    return tp


def run(base, user, pwd, dry_run):
    scenarios = load_scenarios()
    defaults = scenarios.get("defaults", {})
    token = _login(base, user, pwd) if not dry_run else None
    headers = {**HEADERS, "Authorization": f"Bearer {token}"} if token else HEADERS

    # existing devices by name
    existing = {}
    if not dry_run:
        r = requests.get(f"{base}/api/v1/devices/all", headers=headers, timeout=10)
        if r.ok:
            for d in r.json():
                existing[d["name"]] = d["id"]

    for d in scenarios.get("devices", []):
        name = d["name"]
        if dry_run:
            print(f"[dry-run] 设备 {name} ({d['protocol']}) + {len(d.get('tags', []))} 点位")
            continue
        if name in existing:
            dev_id = existing[name]
            print(f"[skip] 设备已存在: {name} (id={dev_id})")
        else:
            r = requests.post(f"{base}/api/v1/devices", json=_device_payload(d, defaults),
                              headers=headers, timeout=10)
            r.raise_for_status()
            dev_id = r.json()["id"]
            print(f"[ok] 创建设备 {name} (id={dev_id})")

        created = {}
        for t in d.get("tags", []):
            r = requests.post(f"{base}/api/v1/devices/tags", json=_tag_payload(t, dev_id),
                              headers=headers, timeout=10)
            if r.ok:
                created[t["name"]] = r.json()["id"]
            else:
                print(f"  [warn] 点位 {t['name']} 创建失败: {r.status_code} {r.text[:120]}")

        # wire readback (writable -> self)
        for t in d.get("tags", []):
            if t.get("writable") and t["name"] in created:
                tid = created[t["name"]]
                requests.put(f"{base}/api/v1/devices/tags/{tid}",
                             json={"readback_tag_id": tid}, headers=headers, timeout=10)
        print(f"[ok] 设备 {name} 点位就绪 ({len(created)})")


def main():
    ap = argparse.ArgumentParser(description="将模拟器设备导入平台")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin123")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.base_url, args.username, args.password, args.dry_run)


if __name__ == "__main__":
    main()
