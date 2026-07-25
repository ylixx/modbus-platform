"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import engine, Base
from app.core.exception_handler import register_exception_handlers
from app.api import (
    auth, users, devices, alarms, sms, history, dashboard,
    audit, exports, websocket, hierarchy, permissions, scada,
    archive, imports, templates, scripts, config_export, orgs,
    lab_data,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.logging_config import setup_logging
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Security: refuse to run with the shipped default secret in production.
    if settings.SECRET_KEY.startswith("change-me"):
        logger.warning(
            "安全警告：正在使用默认 SECRET_KEY，任何人都能伪造 JWT。"
            "请通过环境变量 SECRET_KEY 设置强随机值（openssl rand -hex 32）。"
        )

    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    logger.info("Database tables ensured")

    _create_default_admin()
    _seed_permissions()
    _assign_admin_role()

    # Start all protocol engines
    from app.engine.protocol_router import protocol_router
    protocol_router.start_all()

    # Initialize WebSocket broadcast (Redis pub/sub for multi-worker)
    from app.engine.ws_broadcast import init_redis_broadcast, set_main_loop
    import asyncio
    set_main_loop(asyncio.get_running_loop())
    init_redis_broadcast()

    # Start scheduled tasks
    _start_scheduler()

    yield

    protocol_router.stop_all()
    _stop_scheduler()
    logger.info("Application stopped")


def _migrate_columns():
    """Lightweight SQLite migration: add new columns to existing tables."""
    from sqlalchemy import text
    migrations = [
        ("devices", "org_node_id", "ALTER TABLE devices ADD COLUMN org_node_id INTEGER"),
        ("roles", "data_scope", "ALTER TABLE roles ADD COLUMN data_scope VARCHAR(20) DEFAULT 'all'"),
    ]
    with engine.connect() as conn:
        for table, column, ddl in migrations:
            try:
                cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
                if column not in cols:
                    conn.execute(text(ddl))
                    conn.commit()
                    logger.info(f"Migrated: {table}.{column} added")
            except Exception as e:
                logger.warning(f"Migration {table}.{column} skipped: {e}")


def _create_default_admin():
    from app.core.database import SessionLocal
    from app.models.user import User
    from passlib.context import CryptContext

    # Allow operators to skip the built-in default admin in hardened deployments.
    if settings.DISABLE_DEFAULT_ADMIN:
        logger.info("Default admin creation skipped (DISABLE_DEFAULT_ADMIN=True)")
        return

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin", hashed_password=pwd_context.hash("admin123"),
                display_name="系统管理员", role="admin",
            )
            db.add(admin)
            db.commit()
            logger.warning("Default admin user created (admin / admin123) — CHANGE THE PASSWORD")
    except Exception as e:
        logger.error(f"Create default admin error: {e}")
    finally:
        db.close()


def _seed_permissions():
    from app.services.seed_permissions import seed_permissions
    seed_permissions()


def _assign_admin_role():
    from app.core.database import SessionLocal
    from app.models.user import User
    from app.models.permission import Role, UserRole
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        if admin and admin_role:
            existing = db.query(UserRole).filter(UserRole.user_id == admin.id, UserRole.role_id == admin_role.id).first()
            if not existing:
                db.add(UserRole(user_id=admin.id, role_id=admin_role.id, data_scope="all"))
                db.commit()
    except Exception as e:
        logger.error(f"Assign admin role error: {e}")
    finally:
        db.close()


# ── Scheduled tasks ──

_scheduler = None


def _start_scheduler():
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()

        # Data archival: daily at 3:00 AM
        _scheduler.add_job(_task_archive, 'cron', hour=3, minute=0, id='archive')

        # Alarm escalation check: every 2 minutes
        _scheduler.add_job(_task_escalation, 'interval', minutes=2, id='escalation')

        # Cleanup expired confirmations: every 5 minutes
        _scheduler.add_job(_task_cleanup_confirm, 'interval', minutes=5, id='cleanup_confirm')

        _scheduler.start()
        logger.info("Scheduler started: archive(3:00), escalation(2min), cleanup(5min)")
    except Exception as e:
        logger.error(f"Scheduler start error: {e}")


def _stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _task_archive():
    from app.services.archive_service import run_full_archive
    run_full_archive()


def _task_escalation():
    from app.services.alarm_escalation import check_escalations
    check_escalations()


def _task_cleanup_confirm():
    from app.services.confirm_service import cleanup_expired
    cleanup_expired()


# ── App setup ──

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description="""
## Modbus 数据采集平台 API

通用工业设备数据采集、监控、报警预警及短信推送平台。

### 支持协议
- **Modbus TCP**: FC01-16, 9种数据类型, 4种字节序
- **MQTT**: 标准JSON / ThingsBoard遥测 / 网关模式
- **OPC-UA**: 匿名/用户名密码认证

### 认证方式
所有API需要Bearer Token认证，通过 `/api/v1/auth/login` 获取。

### 主要模块
- `/devices` - 设备管理 (CRUD/分组/标签/远程控制)
- `/alarms` - 报警管理 (规则/记录/确认/升级)
- `/sms` - 短信管理 (联系人/推送规则/发送记录)
- `/history` - 历史数据 (查询/聚合)
- `/scripts` - 脚本算法 (自定义数据处理)
- `/scada` - SCADA画面 (编辑器/图元)
- `/rbac` - 权限管理 (角色/权限/用户分配)
- `/archive` - 数据归档 (策略配置/手动清理)
- `/import` - 批量导入 (设备/点位CSV)
- `/templates` - 设备模板 (预定义设备一键创建)
- `/config` - 配置导出/导入 (平台配置迁移)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "认证", "description": "登录/登出/Token管理"},
        {"name": "设备管理", "description": "设备CRUD/分组/标签/远程控制/实时数据"},
        {"name": "报警管理", "description": "报警规则/报警记录/确认/消除/升级"},
        {"name": "短信管理", "description": "联系人/推送规则/发送记录/测试"},
        {"name": "历史数据", "description": "时序数据查询/聚合/趋势"},
        {"name": "脚本算法", "description": "自定义数据处理脚本/测试运行/模板"},
        {"name": "SCADA", "description": "画面编辑器/自定义图元/运行查看"},
        {"name": "权限管理", "description": "角色/权限点/用户角色分配/数据范围"},
        {"name": "操作审计", "description": "操作日志查询"},
        {"name": "数据导出", "description": "CSV/JSON导出/日报"},
        {"name": "数据归档", "description": "归档策略配置/手动清理/数据量统计"},
        {"name": "批量导入", "description": "CSV批量导入设备/点位"},
        {"name": "设备模板", "description": "预定义设备模板一键创建"},
        {"name": "配置导出", "description": "平台配置整体导出/导入"},
        {"name": "层级配置", "description": "自定义拓扑层级结构"},
        {"name": "仪表盘", "description": "汇总统计/报警趋势"},
        {"name": "用户管理", "description": "用户CRUD(管理员)"},
        {"name": "WebSocket", "description": "实时数据推送(ws://host/ws?token=JWT)"},
    ],
)

# CORS: explicit origin allowlist only. Wildcard + credentials is unsafe,
# so we derive the list from settings instead of "*".
ALLOWED_ORIGINS = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Register global exception handlers
register_exception_handlers(app)

# Rate limiting
from app.core.rate_middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(users.router, prefix=prefix)
app.include_router(devices.router, prefix=prefix)
app.include_router(alarms.router, prefix=prefix)
app.include_router(sms.router, prefix=prefix)
app.include_router(history.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)
app.include_router(audit.router, prefix=prefix)
app.include_router(exports.router, prefix=prefix)
app.include_router(hierarchy.router, prefix=prefix)
app.include_router(orgs.router, prefix=prefix)
app.include_router(permissions.router, prefix=prefix)
app.include_router(scada.router, prefix=prefix)
app.include_router(archive.router, prefix=prefix)
app.include_router(imports.router, prefix=prefix)
app.include_router(templates.router, prefix=prefix)
app.include_router(scripts.router, prefix=prefix)
app.include_router(config_export.router, prefix=prefix)
app.include_router(lab_data.router, prefix=prefix)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
