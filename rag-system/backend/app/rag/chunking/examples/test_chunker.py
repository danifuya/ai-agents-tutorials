#!/usr/bin/env python3

import os
import sys
import argparse
from pathlib import Path

# Add the backend directory to Python path so we can import from app
# Find the backend directory by looking for the directory containing 'app'
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = script_dir
while backend_dir != "/" and not os.path.exists(os.path.join(backend_dir, "app")):
    backend_dir = os.path.dirname(backend_dir)

if os.path.exists(os.path.join(backend_dir, "app")):
    sys.path.insert(0, backend_dir)
else:
    raise ImportError("Could not find backend directory containing 'app' module")

from app.rag.chunking.markdown_chunker import GFMContextPathChunker, ChunkerOptions


def load_document_content(file_path: str) -> tuple[str, str]:
    """
    Load document content from file

    Args:
        file_path: Path to the document file

    Returns:
        tuple: (content, title) where title is derived from filename
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Use filename without extension as title
    title = path.stem.replace("_", " ").replace("-", " ").title()

    return content, title


def test_chunker_with_file(file_path: str, output_dir: str = None):
    """
    Test chunker with a specific document file

    Args:
        file_path: Path to the document file to process
        output_dir: Directory to save results (optional)
    """
    # Create a chunker with custom options
    options = ChunkerOptions(
        max_tokens_per_chunk=512,
        max_words_per_chunk=200,
        max_words_header=30,
        path_separator=" > ",
    )

    chunker = GFMContextPathChunker(options)

    # Load document content
    try:
        content, title = load_document_content(file_path)
        print(f"📖 Loaded document: {file_path}")
        print(f"📝 Document title: {title}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return None

    # Test chunking with detailed output
    print("🚀 Testing Advanced Markdown Chunker")
    print("=" * 80)
    print(f"📄 Document length: {len(content)} characters")
    print(f"📊 Total words: {chunker.count_words(content)}")
    print(f"🔢 Estimated tokens: {chunker.estimate_jina_token_count(content)}")
    print("=" * 80)

    chunks = chunker.chunk(content, title)

    print(f"\n✅ Successfully generated {len(chunks)} semantic chunks")
    print("=" * 80)

    for i, chunk in enumerate(chunks, 1):
        print(f"\n📝 CHUNK {i:02d}")
        print("─" * 60)
        print(chunk)
        print("─" * 60)
        words = chunker.count_words(chunk)
        tokens = chunker.estimate_jina_token_count(chunk)
        lines = len(chunk.split("\n"))

        print(f"📊 Stats: {words:3d} words | {tokens:3d} tokens | {lines:2d} lines")

        # Analyze chunk content type
        content_type = analyze_chunk_type(chunk)
        print(f"🏷️  Type: {content_type}")
        print()

    # Test token-limited batching
    print("\n🔄 Testing Token-Limited Batching")
    print("=" * 80)

    batches = chunker.chunk_within_token_limit(
        content, title, max_tokens_per_batch=512, overlap=1
    )

    print(f"📦 Created {len(batches)} batches with max 512 tokens each")
    print("─" * 60)

    for i, batch in enumerate(batches, 1):
        total_tokens = sum(chunker.estimate_jina_token_count(chunk) for chunk in batch)
        total_words = sum(chunker.count_words(chunk) for chunk in batch)
        print(
            f"Batch {i:2d}: {len(batch):2d} chunks | {total_tokens:3d} tokens | {total_words:3d} words"
        )

    print("\n✨ Chunking test completed successfully!")

    # Determine output file path
    if output_dir:
        output_path = Path(output_dir) / f"{Path(file_path).stem}_chunker_output.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Default to outputs directory relative to script
        script_dir = Path(__file__).parent
        output_dir = script_dir.parent / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{Path(file_path).stem}_chunker_output.txt"

    # Write detailed results to file for analysis
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("🚀 MARKDOWN CHUNKER TEST RESULTS\n")
        f.write("=" * 80 + "\n")
        f.write(f"📄 Document: {file_path}\n")
        f.write(f"📝 Title: {title}\n")
        f.write(f"📄 Document length: {len(content)} characters\n")
        f.write(f"📊 Total words: {chunker.count_words(content)}\n")
        f.write(f"🔢 Estimated tokens: {chunker.estimate_jina_token_count(content)}\n")
        f.write("=" * 80 + "\n")
        f.write(f"\n✅ Successfully generated {len(chunks)} semantic chunks\n")
        f.write("=" * 80 + "\n")

        for i, chunk in enumerate(chunks, 1):
            f.write(f"\n📝 CHUNK {i:02d}\n")
            f.write("─" * 60 + "\n")
            f.write(chunk + "\n")
            f.write("─" * 60 + "\n")
            words = chunker.count_words(chunk)
            tokens = chunker.estimate_jina_token_count(chunk)
            lines = len(chunk.split("\n"))

            f.write(
                f"📊 Stats: {words:3d} words | {tokens:3d} tokens | {lines:2d} lines\n"
            )

            content_type = analyze_chunk_type(chunk)
            f.write(f"🏷️  Type: {content_type}\n")
            f.write("\n")

        # Write batching info
        f.write("\n🔄 TOKEN-LIMITED BATCHING RESULTS\n")
        f.write("=" * 80 + "\n")
        f.write(f"📦 Created {len(batches)} batches with max 512 tokens each\n")
        f.write("─" * 60 + "\n")

        for i, batch in enumerate(batches, 1):
            total_tokens = sum(
                chunker.estimate_jina_token_count(chunk) for chunk in batch
            )
            total_words = sum(chunker.count_words(chunk) for chunk in batch)
            f.write(
                f"Batch {i:2d}: {len(batch):2d} chunks | {total_tokens:3d} tokens | {total_words:3d} words\n"
            )

        f.write(f"\n✨ Results written to {output_path.name}\n")

    print(f"📄 Results written to {output_path}")
    return output_path


def analyze_chunk_type(chunk: str) -> str:
    """Analyze what type of content the chunk contains"""
    content = chunk.lower()

    if "```" in chunk:
        return "🔧 Code Block"
    elif "|" in chunk and "---" in chunk:
        return "📋 Table"
    elif chunk.startswith(("- ", "* ", "1. ", "2. ")):
        return "📝 List"
    elif chunk.startswith("#"):
        return "📚 Heading"
    elif ">" in chunk and chunk.strip().startswith(">"):
        return "💡 Quote"
    elif any(
        keyword in content for keyword in ["issue", "solution", "error", "problem"]
    ):
        return "🚨 Troubleshooting"
    elif any(keyword in content for keyword in ["api", "method", "class", "function"]):
        return "🔌 API Reference"
    elif any(
        keyword in content
        for keyword in ["configure", "setting", "parameter", "option"]
    ):
        return "⚙️  Configuration"
    else:
        return "📄 Content"


def get_default_documents_folder() -> Path:
    """Get the default documents folder path"""
    script_dir = Path(__file__).parent
    return script_dir.parent.parent / "documents"


def list_available_documents() -> list[Path]:
    """List all available documents in the documents folder"""
    docs_dir = get_default_documents_folder()
    if not docs_dir.exists():
        return []

    # Look for markdown files
    return list(docs_dir.glob("*.md"))


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Test the GFM Context Path Chunker with document files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process the transformers.md document
  python test_chunker.py transformers.md
  
  # Process with custom output directory
  python test_chunker.py transformers.md --output-dir ./results
  
  # Process with absolute file path
  python test_chunker.py /path/to/document.md
  
  # List available documents
  python test_chunker.py --list
        """,
    )

    parser.add_argument(
        "document", nargs="?", help="Document file to process (filename or full path)"
    )

    parser.add_argument("--output-dir", "-o", help="Directory to save chunking results")

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available documents in the documents folder",
    )

    args = parser.parse_args()

    # List available documents
    if args.list:
        print("📁 Available documents in documents folder:")
        print("=" * 50)
        docs = list_available_documents()
        if docs:
            for doc in docs:
                print(f"  📄 {doc.name}")
        else:
            docs_dir = get_default_documents_folder()
            print(f"  ❌ No documents found in {docs_dir}")
        return

    # Require document argument
    if not args.document:
        print("❌ Error: Document file is required")
        print("💡 Use --list to see available documents or provide a file path")
        parser.print_help()
        return

    # Determine file path
    document_path = Path(args.document)

    # If it's just a filename, look in documents folder
    if not document_path.is_absolute() and not document_path.exists():
        docs_dir = get_default_documents_folder()
        candidate = docs_dir / args.document
        if candidate.exists():
            document_path = candidate
        else:
            print(f"❌ Error: Document not found: {args.document}")
            print(f"💡 Looked in: {candidate}")
            print("💡 Use --list to see available documents")
            return

    # Process the document
    try:
        output_path = test_chunker_with_file(str(document_path), args.output_dir)
        print(f"\n🎉 Processing completed successfully!")
        print(f"📄 Results saved to: {output_path}")
    except Exception as e:
        print(f"❌ Error processing document: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
