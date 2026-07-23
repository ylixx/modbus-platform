"""Database initialization script.

Creates all tables, seeds default data (admin user, permissions, roles),
and inserts sample device templates.

Usage:
    python scripts/init_db.py              # Full init
    python scripts/init_db.py --reset      # Drop all tables and recreate
    python scripts/init_db.py --seed-only  # Only seed data (tables exist)
"""
import sys
import os
import argparse

# Add backend dir to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from app.core.database import engine, Base, SessionLocal
from app.core.config import settings
from loguru import logger


def create_tables():
    """Create all database tables."""
    logger.info("Creating tables...")
    # Import all models to register them
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    logger.info(f"Tables created: {', '.join(Base.metadata.tables.keys())}")


def drop_tables():
    """Drop all database tables."""
    logger.warning("Dropping ALL tables...")
    import app.models  # noqa
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


def seed_admin():
    """Create default admin user."""
    from app.models.user import User
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                hashed_password=pwd_context.hash("admin123"),
                display_name="系统管理员",
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin created: admin / admin123")
        else:
            logger.info("Admin user already exists, skipping")
    finally:
        db.close()


def seed_permissions():
    """Seed default permissions and roles."""
    from app.services.seed_permissions import seed_permissions
    seed_permissions()


def assign_admin_role():
    """Assign admin role to admin user."""
    from app.models.user import User
    from app.models.permission import Role, UserRole

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        if admin and admin_role:
            existing = db.query(UserRole).filter(
                UserRole.user_id == admin.id,
                UserRole.role_id == admin_role.id,
            ).first()
            if not existing:
                db.add(UserRole(user_id=admin.id, role_id=admin_role.id, data_scope="all"))
                db.commit()
                logger.info("Admin role assigned to admin user")
            else:
                logger.info("Admin already has admin role, skipping")
    finally:
        db.close()


def seed_sample_devices():
    """Create sample devices for demo/testing."""
    from app.models.device import Device, DeviceTag

    db = SessionLocal()
    try:
        if db.query(Device).count() > 0:
            logger.info("Devices already exist, skipping sample data")
            return

        # Sample Modbus device
        d1 = Device(
            name="示例-温湿度传感器", protocol="modbus_tcp",
            host="192.168.1.100", port=502, slave_id=1,
            factory="示例厂级", workshop="A区级", production_line="1号线",
            poll_interval=10, enabled=False,
            description="示例设备，请修改连接信息后启用",
        )
        db.add(d1)
        db.flush()

        for tag_def in [
            {"name": "温度", "function_code": "input_register", "address": 0, "data_type": "float32", "scale_factor": 0.1, "unit": "°C"},
            {"name": "湿度", "function_code": "input_register", "address": 2, "data_type": "float32", "scale_factor": 0.1, "unit": "%RH"},
            {"name": "报警标志", "function_code": "coil", "address": 0, "data_type": "bool", "unit": ""},
        ]:
            db.add(DeviceTag(device_id=d1.id, enabled=True, **tag_def))

        # Sample alarm rule
        from app.models.alarm import AlarmRule
        db.add(AlarmRule(
            name="温度超限报警", device_id=d1.id, tag_id=None,
            alarm_type="threshold_high", alarm_level="warning",
            high_limit=80, deadband=2, delay_seconds=10,
            enabled=False, description="示例报警规则",
        ))

        db.commit()
        logger.info("Sample device and alarm rule created (disabled)")
    except Exception as e:
        logger.error(f"Seed sample error: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Database initialization")
    parser.add_argument("--reset", action="store_true", help="Drop all tables and recreate")
    parser.add_argument("--seed-only", action="store_true", help="Only seed data, skip table creation")
    parser.add_argument("--no-sample", action="store_true", help="Skip sample data")
    args = parser.parse_args()

    logger.info(f"Database: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

    if args.reset:
        drop_tables()

    if not args.seed_only:
        create_tables()

    seed_admin()
    seed_permissions()
    assign_admin_role()

    if not args.no_sample:
        seed_sample_devices()

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    main()
