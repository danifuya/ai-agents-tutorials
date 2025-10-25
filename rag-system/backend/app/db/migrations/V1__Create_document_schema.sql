-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgroonga;
-- Parent level: document metadata and summary
CREATE TABLE documents (
    id bigserial PRIMARY KEY,
    title text NOT NULL,
    summary text NOT NULL,
    summary_embedding vector(1536) NOT NULL
);

-- Child level: document chunks with foreign key
CREATE TABLE document_chunks (
    id bigserial PRIMARY KEY,
    content text NOT NULL,
    embedding vector(1536) NOT NULL,
    document_id bigint REFERENCES documents(id) ON DELETE CASCADE
);
