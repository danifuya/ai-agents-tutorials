import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()  # Loads environment variables from .env (if present)

DB_HOST = os.getenv("SUPABASE_DB_HOST", "YOUR_HOST")
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "YOUR_PASSWORD")
DB_PORT = os.getenv("SUPABASE_DB_PORT", "5432")


class SupabaseVectorDB:
    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseVectorDB, cls).__new__(cls)
            cls._instance._connect()
        return cls._instance

    def _connect(self):
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT,
            )
            self._connection.autocommit = True

    def __del__(self):
        if self._connection and not self._connection.closed:
            self._connection.close()

    def search_similar_in_my_embeddings(
        self, query_embedding: list[float], top_k: int = 4
    ):
        """
        Search for similar documents in documents_code using the <-> operator.
        """
        self._connect()  # Ensure connection is active
        dims = 1536
        embedding_str = (
            f"'[{','.join(str(v) for v in query_embedding)}]'::vector({dims})"
        )
        with self._connection.cursor(cursor_factory=RealDictCursor) as cursor:
            sql = f"""
                SELECT
                    id,
                    text_content,
                    metadata,
                    embedding <-> {embedding_str} AS distance
                FROM my_embeddings
                ORDER BY embedding <-> {embedding_str}
                LIMIT {top_k};
            """
            cursor.execute(sql)
            results = cursor.fetchall()
        return results
