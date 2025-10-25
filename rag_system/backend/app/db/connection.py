# app/services/database_service.py
import os
import logging
from psycopg_pool import AsyncConnectionPool
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE")
POSTGRES_SSLMODE = os.getenv("POSTGRES_SSLMODE", "require")


class DatabaseService:
    """Database service using POSTGRES Session Pooler with psycopg3"""

    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None
        self._initialized = False

    async def initialize(self, max_size: int = 5):
        """Initialize database connection pool"""
        if self._initialized:
            return

        try:
            # Use the same configuration that worked in test_db_connection.py

            # Validate required parameters
            if not POSTGRES_PASSWORD:
                logger.error("❌ POSTGRES_PASSWORD is required")
                raise Exception("POSTGRES_PASSWORD is required")

            # Log connection details (without sensitive info)
            logger.info(f"Connecting to POSTGRES database:")
            logger.info(f"  Host: {POSTGRES_HOST}")
            logger.info(f"  Port: {POSTGRES_PORT}")
            logger.info(f"  User: {POSTGRES_USER}")
            logger.info(f"  Database: {POSTGRES_DATABASE}")

            # Build connection string
            CONNECTION_STRING = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}?sslmode={POSTGRES_SSLMODE}"

            # Create the connection pool
            self._pool = AsyncConnectionPool(
                CONNECTION_STRING, min_size=1, max_size=max_size, open=False
            )

            # Open the pool
            await self._pool.open()
            logger.info("🔗 Connection pool opened")
            async with self._pool.connection() as conn:
                if not await self.test_connection(conn):
                    raise Exception("Database connection test failed.")

            self._initialized = True
            logger.info("✅ Database service initialized successfully")

        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            self._initialized = False
            raise

    @asynccontextmanager
    async def get_connection(self):
        """Provides a connection from the pool."""
        if not self._pool:
            raise ConnectionError("Database pool is not initialized.")
        conn = None
        try:
            async with self._pool.connection() as conn:
                yield conn
        except Exception as e:
            logger.error(f"Failed to get connection from pool: {e}")
            raise

    @staticmethod
    async def test_connection(conn) -> bool:
        """Test database connection"""
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT version()")
                version = await cursor.fetchone()
                logger.info(f"✅ Connected successfully! PostgreSQL: {version[0]}")
                return True
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False

    def get_pool_stats(self) -> Optional[Dict[str, Any]]:
        """Get connection pool statistics."""
        if self._pool:
            return self._pool.get_stats()
        return None

    @staticmethod
    async def fetch_one(conn, query: str, params: tuple = None) -> Optional[Dict]:
        """Fetch a single row from the database"""
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            if row:
                return dict(zip([desc[0] for desc in cursor.description], row))
            return None

    @staticmethod
    async def fetch_all(conn, query: str, params: tuple = None) -> List[Dict]:
        """Fetch all rows from the database"""
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [
                dict(zip([desc[0] for desc in cursor.description], row)) for row in rows
            ]

    @staticmethod
    async def fetch_val(conn, query: str, params: tuple = None) -> Any:
        """Fetch a single value from the database"""
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row else None

    @staticmethod
    async def execute(conn, query: str, params: tuple = None) -> None:
        """Execute a query without returning results"""
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)

    async def close(self):
        """Close database connection pool"""
        if self._pool:
            await self._pool.close()
            self._initialized = False
            logger.info("🔌 Database connection pool closed")

    def is_available(self) -> bool:
        """Check if database is available"""
        return self._initialized and self._pool is not None
