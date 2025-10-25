# Markdown Chunker

A sophisticated chunker for converting markdown documents into semantic chunks for RAG (Retrieval-Augmented Generation) pipelines.

## Structure

```
app/rag/chunking/
├── markdown_chunker.py          # Main implementation
├── examples/                    # Example scripts & demos
│   ├── chunk_transformers.py    # Chunk academic papers
│   ├── test_chunker.py          # Basic chunker demo
│   └── debug/                   # Debugging utilities
│       ├── debug_nested.py      # Debug nested list structures
│       └── debug_tokens.py      # Debug token parsing
└── outputs/                     # Generated results
    ├── chunker_output.txt       # Test results
    ├── transformers_chunks.txt  # Academic paper chunks
    └── token_debug.txt          # Debug output
```

## Core Features

- **Semantic chunking** with context preservation
- **Numbered list support** with proper hierarchy
- **Nested structure preservation** for complex markdown
- **Code block detection** with syntax highlighting
- **Table handling** with intelligent splitting
- **Header path tracking** for document context
- **Token estimation** for Jina embeddings

## Usage Examples

### Basic Usage
```bash
cd examples
uv run python test_chunker.py
```

### Chunk Academic Papers
```bash
cd examples  
uv run python chunk_transformers.py
```

### Debug Token Parsing
```bash
cd examples/debug
uv run python debug_tokens.py
uv run python debug_nested.py
```

## Configuration

The chunker supports various options:
- `max_tokens_per_chunk`: Maximum tokens per chunk (default: 512)
- `max_words_per_chunk`: Maximum words per chunk (default: 200) 
- `max_words_header`: Maximum words in header paths (default: 30)
- `path_separator`: Separator for header paths (default: ' > ')

## Output Format

Each chunk includes:
- **Content**: The actual text content
- **Context path**: Hierarchical header path
- **Statistics**: Word count, token count, line count
- **Content type**: Categorized content type (code, table, etc.)