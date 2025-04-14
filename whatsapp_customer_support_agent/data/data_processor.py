import csv
import json
import os

import openai
import psycopg2
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

# Postgres connection info
POSTGRES_HOST = os.getenv("SUPABASE_DB_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("SUPABASE_DB_PORT", 5432))
POSTGRES_DB = os.getenv("SUPABASE_DB_NAME", "postgres")
POSTGRES_USER = os.getenv("SUPABASE_DB_USER", "postgres")
POSTGRES_PASS = os.getenv("SUPABASE_DB_PASSWORD", "")

# The name/path to your CSV file
CSV_FILE_PATH = "data/data.csv"

# Dimension for the chosen embedding model (OpenAI text-embedding-ada-002)
EMBED_DIMENSION = 1536


###############################################################################
# 1) Helper functions
###############################################################################
def connect_to_postgres():
    """Connect to Postgres and return a connection."""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASS,
    )
    return conn


def create_table_if_not_exists(conn):
    """
    Create the my_embeddings table if it doesn't exist.
    Assumes pgvector extension is already installed and enabled.
    """
    create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS my_embeddings (
            id            SERIAL PRIMARY KEY,
            source_id     TEXT,
            chunk_index   INT,
            text_content  TEXT,
            metadata      JSONB,
            embedding     VECTOR({EMBED_DIMENSION})
        );
    """
    create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_my_embeddings_embedding
            ON my_embeddings
            USING ivfflat (embedding vector_l2_ops)
            WITH (lists = 100);
    """

    with conn.cursor() as cur:
        cur.execute(create_table_sql)
        cur.execute(create_index_sql)
        conn.commit()


def chunk_text(text, max_chars=2000):
    """
    Simple utility to split a long text into chunks of roughly max_chars length.
    This helps keep chunk sizes manageable for embedding and retrieval.
    Adjust `max_chars` as appropriate for your use case.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        chunks.append(chunk)
        start = end
    return chunks


def get_embedding(text):
    """
    Use OpenAI API to get an embedding vector.
    Replace with your own embedding model or provider as needed.
    """
    response = openai.Embedding.create(model="text-embedding-ada-002", input=text)
    # Extract embeddings (returns a list of floats)
    vector = response["data"][0]["embedding"]
    return vector


def insert_embedding_row(
    conn, source_id, chunk_idx, text_content, metadata_dict, embedding_vector
):
    """
    Insert a single row (one chunk + embedding) into my_embeddings table.
    """
    insert_query = """
        INSERT INTO my_embeddings (source_id, chunk_index, text_content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s);
    """
    with conn.cursor() as cur:
        cur.execute(
            insert_query,
            (
                source_id,
                chunk_idx,
                text_content,
                json.dumps(metadata_dict),
                embedding_vector,
            ),
        )


###############################################################################
# 2) Main CSV ingestion
###############################################################################
def process_csv_and_store_embeddings(csv_file_path):
    """
    Read CSV with headers, embed text from each row, chunk if needed,
    and store results in my_embeddings table.
    """
    conn = connect_to_postgres()
    create_table_if_not_exists(conn)
    csv_file_path = CSV_FILE_PATH
    with open(csv_file_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")  # Use semicolon as delimiter
        for idx, row in enumerate(reader):
            # Use row index as the source_id
            source_id = str(idx)

            # Build a structured text string with clear labels matching the English CSV columns
            structured_text = (
                f"ROBOT MODEL: {row.get('ROBOT_MODEL', '').strip()}\n"
                f"ISSUE CATEGORY: {row.get('ISSUE_CATEGORY', '').strip()}\n"
                f"INCIDENT SUMMARY: {row.get('INCIDENT_SUMMARY', '').strip()}\n"
                f"DESCRIPTION: {row.get('DESCRIPTION', '').strip()}\n"
                f"PRIORITY: {row.get('PRIORITY', '').strip()}\n\n"
                "Steps to follow:\n"
                f"Step 1: {row.get('STEP_1', '').strip()}\n"
                f"Step 2: {row.get('STEP_2', '').strip()}\n"
                f"Step 3: {row.get('STEP_3', '').strip()}\n"
                f"Step 4: {row.get('STEP_4', '').strip()}\n"
            )

            # Build a metadata dictionary containing the original row.
            # Optionally, you can remove the fields that have been embedded to avoid duplication.
            metadata_dict = dict(row)
            for key in [
                "INCIDENT_SUMMARY",
                "DESCRIPTION",
                "STEP_1",
                "STEP_2",
                "STEP_3",
                "STEP_4",
            ]:
                metadata_dict.pop(key, None)

            # If the text is very large, chunk it into manageable pieces
            text_chunks = chunk_text(structured_text, max_chars=2000)

            # For each text chunk, generate an embedding and insert it into the database
            for i, chunk in enumerate(text_chunks):
                client = openai.OpenAI()
                response = client.embeddings.create(
                    model="text-embedding-3-small", input=chunk
                )
                embedding_vector = response.data[0].embedding
                insert_embedding_row(
                    conn,
                    source_id=source_id,
                    chunk_idx=i,
                    text_content=chunk,
                    metadata_dict=metadata_dict,
                    embedding_vector=embedding_vector,
                )

        conn.commit()

    conn.close()


###############################################################################
# 3) Run the script
###############################################################################
if __name__ == "__main__":
    process_csv_and_store_embeddings(CSV_FILE_PATH)
    print("CSV data successfully processed and embeddings stored.")
