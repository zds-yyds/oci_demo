from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # JWT
    secret_key: str = "oci-manager-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24h

    # PostgreSQL 连接（完整 URL 或拆分字段二选一）
    database_url: Optional[str] = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "oci"
    db_password: str = "oci123"
    db_name: str = "oci_manager"

    # 用于自动建库的超级用户（本地用 postgres，Docker 用 db_user 本身即可）
    pg_root_user: str = "postgres"
    pg_root_password: str = "postgres"

    # Admin default credentials
    admin_username: str = "admin"
    admin_password: str = "admin123"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_async_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def get_sync_url(self) -> str:
        if self.database_url:
            return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def get_pg_root_url(self) -> str:
        """连接到 postgres 系统库，用于建库建用户"""
        if self.database_url:
            # 把库名替换成 postgres
            import re
            return re.sub(r"/[^/]+$", "/postgres",
                          self.database_url.replace("+asyncpg", "").replace("+psycopg2", ""))
        return f"postgresql://{self.pg_root_user}:{self.pg_root_password}@{self.db_host}:{self.db_port}/postgres"


settings = Settings()
