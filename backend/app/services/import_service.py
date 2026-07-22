"""Batch import service for devices and tags from Excel/CSV."""
import csv
import io
import json
from datetime import datetime
from loguru import logger
from app.core.database import SessionLocal
from app.models.device import Device, DeviceTag


def import_devices_csv(content: bytes) -> dict:
    """Import devices from CSV content.

    Expected columns:
      name, protocol, host, port, slave_id, poll_interval, factory, workshop, production_line, installation, description
    """
    db = SessionLocal()
    created = 0
    errors = []
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        for i, row in enumerate(reader, start=2):
            try:
                name = row.get("name", "").strip()
                if not name:
                    errors.append(f"Row {i}: missing name")
                    continue

                # Check duplicate
                if db.query(Device).filter(Device.name == name).first():
                    errors.append(f"Row {i}: device '{name}' already exists")
                    continue

                device = Device(
                    name=name,
                    protocol=row.get("protocol", "modbus_tcp").strip() or "modbus_tcp",
                    host=row.get("host", "").strip(),
                    port=int(row.get("port", 502) or 502),
                    slave_id=int(row.get("slave_id", 1) or 1),
                    poll_interval=float(row.get("poll_interval", 5) or 5),
                    factory=row.get("factory", "").strip(),
                    workshop=row.get("workshop", "").strip(),
                    production_line=row.get("production_line", "").strip(),
                    installation=row.get("installation", "").strip(),
                    description=row.get("description", "").strip(),
                    enabled=True,
                )
                db.add(device)
                created += 1
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        db.commit()
        logger.info(f"Imported {created} devices")
        return {"created": created, "errors": errors}

    except Exception as e:
        db.rollback()
        logger.error(f"Import devices error: {e}")
        return {"created": 0, "errors": [str(e)]}
    finally:
        db.close()


def import_tags_csv(content: bytes) -> dict:
    """Import tags from CSV content.

    Expected columns:
      device_name, name, function_code, address, data_type, byte_order, scale_factor, offset, decimal_places, unit, writable, description
    """
    db = SessionLocal()
    created = 0
    errors = []
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        for i, row in enumerate(reader, start=2):
            try:
                device_name = row.get("device_name", "").strip()
                tag_name = row.get("name", "").strip()

                if not device_name or not tag_name:
                    errors.append(f"Row {i}: missing device_name or name")
                    continue

                device = db.query(Device).filter(Device.name == device_name).first()
                if not device:
                    errors.append(f"Row {i}: device '{device_name}' not found")
                    continue

                # Check duplicate
                existing = db.query(DeviceTag).filter(
                    DeviceTag.device_id == device.id,
                    DeviceTag.name == tag_name,
                ).first()
                if existing:
                    errors.append(f"Row {i}: tag '{tag_name}' already exists on device '{device_name}'")
                    continue

                tag = DeviceTag(
                    device_id=device.id,
                    name=tag_name,
                    function_code=row.get("function_code", "holding_register").strip() or "holding_register",
                    address=int(row.get("address", 0) or 0),
                    data_type=row.get("data_type", "uint16").strip() or "uint16",
                    byte_order=row.get("byte_order", "big_endian").strip() or "big_endian",
                    scale_factor=float(row.get("scale_factor", 1) or 1),
                    offset=float(row.get("offset", 0) or 0),
                    decimal_places=int(row.get("decimal_places", 2) or 2),
                    unit=row.get("unit", "").strip(),
                    writable=row.get("writable", "").strip().lower() in ("true", "1", "yes", "是"),
                    description=row.get("description", "").strip(),
                    enabled=True,
                )
                db.add(tag)
                created += 1
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        db.commit()
        logger.info(f"Imported {created} tags")
        return {"created": created, "errors": errors}

    except Exception as e:
        db.rollback()
        logger.error(f"Import tags error: {e}")
        return {"created": 0, "errors": [str(e)]}
    finally:
        db.close()
