"""为演示设备补一批实时点位（tag），让实时数据表有内容可展示。

仅当某设备没有任何 tag 时才插入（幂等，可重复执行）。
点位：温度(°C) / 压力(MPa) / 运行状态(0/1)，分别挂在保持寄存器 0/1/2。
演示主机不可达时，引擎会将其标记为离线（quality=bad），表格仍能正常展示结构与状态。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag

# device_name -> [(name, unit, data_type, address, writable), ...]
TAGS = [
    ("温度", "°C", "FLOAT32", 0, False),
    ("压力", "MPa", "FLOAT32", 1, False),
    ("运行状态", "", "UINT16", 2, False),
]


def main():
    db = SessionLocal()
    try:
        devices = db.query(Device).all()
        added = 0
        for d in devices:
            have = db.query(DeviceTag).filter(DeviceTag.device_id == d.id).count()
            if have == 0:
                for i, (name, unit, dtype, addr, writable) in enumerate(TAGS):
                    db.add(DeviceTag(
                        device_id=d.id,
                        name=f"{d.name}-{name}",
                        description=name,
                        unit=unit,
                        function_code="holding_register",
                        address=addr,
                        data_type=dtype,
                        scale_factor=1.0,
                        offset=0.0,
                        decimal_places=2,
                        writable=writable,
                        sort_order=i,
                        enabled=True,
                    ))
                added += 1
            # 确保「运行状态」点位可写（演示远程写值用）
            rt = (
                db.query(DeviceTag)
                .filter(DeviceTag.device_id == d.id, DeviceTag.name == f"{d.name}-运行状态")
                .first()
            )
            if rt and not rt.writable:
                rt.writable = True
        db.commit()
        print(
            f"已为 {added} 台设备补点（每台 {len(TAGS)} 个点位）；"
            f"跳过已有 tag 的设备 {len(devices) - added} 台；运行状态点位已置为可写"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
