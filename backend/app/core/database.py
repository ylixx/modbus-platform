"""Database engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


def _connect_args(url: str) -> dict:
    """SQLite 在多线程采集场景下需要关闭单线程检查，否则后台线程用 Session 会报错。"""
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _apply_sqlite_pragmas(engine):
    """SQLite 启用 WAL + busy_timeout，显著降低 "database is locked" 概率。"""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()


# ── 主关系库 engine（设备/标签/用户/权限/SCADA 配置等）──
engine = create_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,  # 每次取连接先探活，避免 MySQL wait_timeout 后 "server has gone away"
    connect_args=_connect_args(settings.database_url),
    echo=settings.DEBUG,
)
if settings.database_url.startswith("sqlite"):
    _apply_sqlite_pragmas(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── 历史库 engine（聚合 / 长期历史；未配置 HISTORY_DATABASE_URL 时复用主库）──
_history_url = settings.history_database_url
if _history_url:
    history_engine = create_engine(
        _history_url,
        pool_size=20,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
        connect_args=_connect_args(_history_url),
        echo=settings.DEBUG,
    )
    if _history_url.startswith("sqlite"):
        _apply_sqlite_pragmas(history_engine)
    # 配了独立历史库 → 历史读写为独立 session
    HistorySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=history_engine)
else:
    # 未配置 → 历史与主库同一 engine，行为与开发期一致
    history_engine = engine
    HistorySessionLocal = SessionLocal


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_history_db():
    """历史数据专用 session 依赖；未配独立历史库时退化为普通 session。"""
    db = HistorySessionLocal()
    try:
        yield db
    finally:
        db.close()
