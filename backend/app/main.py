import sys, os
# 兼容直接运行 main.py 的场景（如 PyCharm Run）
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging

from app.database import init_db, AsyncSessionLocal
from app import models
from app.auth import hash_password
from app.config import settings
from app.routers import auth, users, tenants, instances, snipe, bills, notify, regions, oci_users, terminal, ssh_credentials

logger = logging.getLogger(__name__)


def ensure_db_exists():
    """
    用 psycopg2 连接到 postgres 系统库，
    检查目标用户和数据库是否存在，不存在则创建。
    本地和 Docker 都适用。
    """
    try:
        conn = psycopg2.connect(settings.get_pg_root_url())
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # 检查并创建用户
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (settings.db_user,))
        if not cur.fetchone():
            cur.execute(
                f"CREATE USER {settings.db_user} WITH PASSWORD %s",
                (settings.db_password,)
            )
            logger.info(f"已创建数据库用户: {settings.db_user}")
        else:
            logger.info(f"数据库用户已存在: {settings.db_user}")

        # 检查并创建数据库
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.db_name,))
        if not cur.fetchone():
            cur.execute(
                f'CREATE DATABASE {settings.db_name} OWNER {settings.db_user}'
            )
            logger.info(f"已创建数据库: {settings.db_name}")
        else:
            logger.info(f"数据库已存在: {settings.db_name}")

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"自动建库跳过（可能已存在或无 superuser 权限）: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 自动建库建用户（不存在才建）
    ensure_db_exists()

    # 2. 建表
    await init_db()

    # 2.1 自动迁移：确保新字段存在（create_all 不会修改已有表）
    async with AsyncSessionLocal() as db:
        try:
            await db.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS default_ssh_public_key TEXT"
            ))
            await db.commit()
        except Exception:
            await db.rollback()

    # 3. 创建默认管理员
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(models.User).where(models.User.username == settings.admin_username)
        )
        if not result.scalar_one_or_none():
            admin = models.User(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            logger.info(f"已创建默认管理员: {settings.admin_username}")

    # 4. 初始化区域字典表
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(models.Region))
        if not result.scalars().first():
            _init_regions = [
                ("eu-amsterdam-1", "Netherlands Northwest (Amsterdam)", "AMS"),
                ("eu-stockholm-1", "Sweden Central (Stockholm)", "ARN"),
                ("me-abudhabi-1", "UAE Central (Abu Dhabi)", "AUH"),
                ("sa-bogota-1", "Colombia Central (Bogota)", "BOG"),
                ("ap-mumbai-1", "India West (Mumbai)", "BOM"),
                ("eu-paris-1", "France Central (Paris)", "CDG"),
                ("uk-cardiff-1", "UK West (Newport)", "CWL"),
                ("me-dubai-1", "UAE East (Dubai)", "DXB"),
                ("eu-frankfurt-1", "Germany Central (Frankfurt)", "FRA"),
                ("sa-saopaulo-1", "Brazil East (Sao Paulo)", "GRU"),
                ("ap-batam-1", "Indonesia North (Batam)", "HSG"),
                ("ap-hyderabad-1", "India South (Hyderabad)", "HYD"),
                ("us-ashburn-1", "US East (Ashburn)", "IAD"),
                ("ap-seoul-1", "South Korea Central (Seoul)", "ICN"),
                ("ap-kulai-2", "Malaysia West 2 (Kulai)", "JBP"),
                ("me-jeddah-1", "Saudi Arabia West (Jeddah)", "JED"),
                ("af-johannesburg-1", "South Africa Central (Johannesburg)", "JNB"),
                ("ap-osaka-1", "Japan Central (Osaka)", "KIX"),
                ("af-casablanca-1", "Morocco West (Casablanca)", "LEJ"),
                ("uk-london-1", "UK South (London)", "LHR"),
                ("eu-milan-1", "Italy Northwest (Milan)", "LIN"),
                ("eu-madrid-1", "Spain Central (Madrid)", "MAD"),
                ("ap-melbourne-1", "Australia Southeast (Melbourne)", "MEL"),
                ("eu-marseille-1", "France South (Marseille)", "MRS"),
                ("mx-monterrey-1", "Mexico Northeast (Monterrey)", "MTY"),
                ("il-jerusalem-1", "Israel Central (Jerusalem)", "MTZ"),
                ("eu-turin-1", "Italy North (Turin)", "NRQ"),
                ("ap-tokyo-1", "Japan East (Tokyo)", "NRT"),
                ("us-chicago-1", "US Midwest (Chicago)", "ORD"),
                ("eu-madrid-3", "Spain Central (Madrid 3)", "ORF"),
                ("us-phoenix-1", "US West (Phoenix)", "PHX"),
                ("mx-queretaro-1", "Mexico Central (Queretaro)", "QRO"),
                ("me-riyadh-1", "Saudi Arabia Central (Riyadh)", "RUH"),
                ("sa-santiago-1", "Chile Central (Santiago)", "SCL"),
                ("ap-singapore-1", "Singapore (Singapore)", "SIN"),
                ("us-sanjose-1", "US West (San Jose)", "SJC"),
                ("ap-sydney-1", "Australia East (Sydney)", "SYD"),
                ("sa-valparaiso-1", "Chile West (Valparaiso)", "VAP"),
                ("sa-vinhedo-1", "Brazil Southeast (Vinhedo)", "VCP"),
                ("ap-singapore-2", "Singapore West (Singapore)", "XSP"),
                ("ap-chuncheon-1", "South Korea North (Chuncheon)", "YNY"),
                ("ca-montreal-1", "Canada Southeast (Montreal)", "YUL"),
                ("ca-toronto-1", "Canada Southeast (Toronto)", "YYZ"),
                ("eu-zurich-1", "Switzerland North (Zurich)", "ZRH"),
            ]
            for identifier, name, key in _init_regions:
                db.add(models.Region(identifier=identifier, name=name, key=key))
            await db.commit()
            logger.info(f"已初始化 {len(_init_regions)} 个 OCI 区域")

    # 5. 恢复因重启而中断的抢机任务（不发通知）
    from app.snipe_worker import resume_running_tasks
    resume_running_tasks()

    yield


app = FastAPI(
    title="OCI Manager",
    description="Oracle Cloud Infrastructure 多租户管理平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tenants.router)
app.include_router(instances.router)
app.include_router(snipe.router)
app.include_router(bills.router)
app.include_router(notify.router)
app.include_router(regions.router)
app.include_router(oci_users.router)
app.include_router(terminal.router)
app.include_router(ssh_credentials.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
