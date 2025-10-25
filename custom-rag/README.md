# Custom RAG System Tutorial

Production-ready RAG system with hierarchical retrieval, hybrid search (semantic + keyword), and reranking.

## 📺 Video Tutorial

Watch the full tutorial: [https://youtu.be/gFAx75igzcY](https://youtu.be/gFAx75igzcY)

## 🚀 Quick Start

### Prerequisites

1. **Install Docker Desktop**

   - Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Start Docker Desktop

2. **Install uv** (Python package manager)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Setup

1. **Clone and navigate to project**

   ```bash
   cd backend
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env.dev
   ```

   Edit `backend/.env.dev` and add your API keys:

   ```
   OPENAI_API_KEY=sk-proj-your-key-here
   VOYAGE_API_KEY=your-voyage-key-here
   ```

3. **Start Docker services** (PostgreSQL + PGroonga)
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```

## 📚 Usage

### 1. Parse PDFs to Markdown

```bash
# List available PDFs
uv run python3 app/rag/parsers/examples/parse_documents.py --list

# Parse all PDFs
uv run python3 app/rag/parsers/examples/parse_documents.py --all
```

### 2. Store Documents in Database

```bash
# Store all markdown documents
uv run python3 app/rag/storage/examples/store_document.py --all

# Or store specific document
uv run python3 app/rag/storage/examples/store_document.py --file research_paper.md
```

### 3. Interactive Search

```bash
# Start interactive retrieval terminal
uv run python3 app/rag/retrieval/examples/interactive_search.py
```

## 🧪 Testing Components

### Test Chunking

```bash
uv run python3 app/rag/chunking/examples/test_chunker.py transformers.md
```

### Test Embeddings

```bash
uv run python3 app/rag/embeddings/examples/test_embeddings.py
```

### Test Reranker

```bash
uv run app/rag/reranking/examples/test_reranker.py
```

### Test PGroonga Keyword Search

```bash
uv run app/rag/retrieval/examples/interactive_pgroonga_search.py
```

## 🏗️ Architecture

**3-Stage Hierarchical Retrieval:**

1. **Stage 1**: Document filtering using hybrid search on summaries
2. **Stage 2**: Chunk retrieval with hybrid scoring (semantic + keyword)
3. **Stage 3**: Reranking with Voyage AI for final ordering

**Key Features:**

- PGroonga for full-text search with bigram tokenization
- pgvector for semantic similarity
- Voyage AI rerank-2.5 for result optimization
- GFM-aware markdown chunking
- LLM-powered document summarization

## 🔑 API Keys

- **OpenAI**: Get from [platform.openai.com](https://platform.openai.com/api-keys)
- **Voyage AI**: Get from [dash.voyageai.com](https://dash.voyageai.com/)

## 📝 Notes

All commands should be run from the `backend/` directory.
