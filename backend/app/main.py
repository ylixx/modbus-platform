"""Main FastAPI application."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, users, devices, alarms, sms, history, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")

    _create_default_admin()

    # Start all protocol engines (Modbus + MQTT + OPC-UA)
    from app.engine.protocol_router import protocol_router
    protocol_router.start_all()

    yield

    # Shutdown
    protocol_router.stop_all()
    logger.info("Application stopped")


def _create_default_admin():
    from app.core.database import SessionLocal
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
            logger.info("Default admin user created (admin / admin123)")
    except Exception as e:
        logger.error(f"Create default admin error: {e}")
    finally:
        db.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(users.router, prefix=prefix)
app.include_router(devices.router, prefix=prefix)
app.include_router(alarms.router, prefix=prefix)
app.include_router(sms.router, prefix=prefix)
app.include_router(history.router, prefix=prefix)
app.include_router(dashboard.router, prefix=prefix)


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}
