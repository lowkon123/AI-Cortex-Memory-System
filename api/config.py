"""Database configuration for Cortex Memory API."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    port: int
    database: str
    user: str
    password: str
    vector_dim: int = 1024

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "cortex_memory"),
            user=os.getenv("DB_USER", "cortex_user"),
            password=os.getenv("DB_PASSWORD", "cortex_pass"),
            vector_dim=int(os.getenv("VECTOR_DIM", "1024")),
        )

    @property
    def asyncpg_kwargs(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
        }


db_config = DatabaseConfig.from_env()
