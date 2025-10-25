docker compose -f docker-compose.dev.yml up --build

Parsing (PDF → Markdown)

# List available PDFs

uv run python3 app/rag/parsers/examples/parse_documents.py --list

# Parse specific PDF to markdown

uv run python3 app/rag/parsers/examples/parse_documents.py --file transformers.pdf

# Parse all PDFs

uv run python3 app/rag/parsers/examples/parse_documents.py --all

Chunking (Test Markdown Processing)

# List available markdown documents

uv run python3 app/rag/chunking/examples/test_chunker.py --list

# Test chunking on specific document

uv run python3 app/rag/chunking/examples/test_chunker.py transformers.md

# Test chunking with custom output directory

uv run python3 app/rag/chunking/examples/test_chunker.py transformers.md --output-dir ./results

Embeddings (Test Embedding Generation)

# Test embeddings with OpenAI

uv run python3 app/rag/embeddings/examples/test_embeddings.py

Storage (Store in Database)

# List available markdown documents

uv run python3 app/rag/storage/examples/store_document.py --list

# Store specific document

uv run python3 app/rag/storage/examples/store_document.py --file state_of_ai.md

# Store with custom title

uv run python3 app/rag/storage/examples/store_document.py --file transformers.md --title "Attention Is All You Need"

Retrieval (Search Documents)

# Interactive search terminal

uv run python3 app/rag/retrieval/examples/interactive_search.py

# Test reranker standalone

uv run app/rag/reranking/examples/test_reranker.py

Complete Workflow Example

# 1. Parse PDF to markdown

uv run python3 app/rag/parsers/examples/parse_documents.py --file research_paper.pdf

# 2. Test chunking (optional)

uv run python3 app/rag/chunking/examples/test_chunker.py research_paper.md

# 3. Store in database

uv run python3 app/rag/storage/examples/store_document.py --file research_paper.md

# Store all documents

uv run python3 app/rag/storage/examples/store_document.py --all

# 4. Search/retrieve

uv run python3 app/rag/retrieval/examples/interactive_search.py

Note: All commands should be run from the /Users/danifuya/Documents/Dani/AIagency/panacea/backend/ directory.
