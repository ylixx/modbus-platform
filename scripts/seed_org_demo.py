"""插入一批分层明确的演示设备，用于展示组织架构「关联列表框」。

层级：厂区 → 班 → 站 → 位置 → 设备名称
仅当 devices 表为空时插入，可重复执行（幂等）。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
from app.core.database import SessionLocal
from app.models.device import Device

DEMO = [
    # 厂区, 班, 站, 位置, 设备名, host
    ("一工厂", "甲班", "1号站", "东厂区", "空压机A", "192.168.1.101"),
    ("一工厂", "甲班", "1号站", "东厂区", "冷却水泵A", "192.168.1.102"),
    ("一工厂", "甲班", "1号站", "西厂区", "空压机B", "192.168.1.103"),
    ("一工厂", "甲班", "2号站", "主控室", "PLC主控", "192.168.1.110"),
    ("一工厂", "甲班", "2号站", "主控室", "温度传感器", "192.168.1.111"),
    ("一工厂", "乙班", "3号站", "锅炉房", "锅炉压力", "192.168.1.120"),
    ("一工厂", "乙班", "3号站", "锅炉房", "给水泵", "192.168.1.121"),
    ("二工厂", "丙班", "4号站", "生产线", "包装机", "192.168.2.130"),
    ("二工厂", "丙班", "4号站", "生产线", "封口机", "192.168.2.131"),
    ("二工厂", "丙班", "4号站", "生产线", "贴标机", "192.168.2.132"),
]


def main():
    db = SessionLocal()
    try:
        if db.query(Device).count() > 0:
            print("devices 已存在，跳过演示数据插入")
            return
        for factory, line, station, loc, name, host in DEMO:
            db.add(Device(
                name=name, protocol="modbus_tcp",
                host=host, port=502, slave_id=1,
                factory=factory, workshop=station, production_line=line,
                installation=loc, poll_interval=10, enabled=True,
                description=f"{factory}/{line}/{station}/{loc}",
            ))
        db.commit()
        print(f"已插入 {len(DEMO)} 个演示设备")
    finally:
        db.close()


if __name__ == "__main__":
    main()
