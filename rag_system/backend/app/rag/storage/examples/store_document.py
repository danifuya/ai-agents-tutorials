#!/usr/bin/env python3
"""
Store Document Example

This script allows you to:
1. List available markdown documents in rag/documents
2. Store all markdown documents at once
3. Store a specific document with chunking and embeddings

Usage:
  # List available documents
  python store_document.py --list

  # Store all markdown documents
  python store_document.py --all

  # Store specific document
  python store_document.py --file transformers.md

  # Store document with custom title
  python store_document.py --file transformers.md --title "Custom Title"
"""

import os
import sys
import argparse
import asyncio
import dotenv
from pathlib import Path
from typing import List, Optional

# Load environment variables and override POSTGRES_HOST for Docker
dotenv.load_dotenv(".env.dev")
os.environ["POSTGRES_HOST"] = "localhost"

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

from app.rag.storage.document_store import DocumentStore
from app.db.connection import DatabaseService


class DocumentStoreInterface:
    """
    Interface for storing documents from the documents folder
    """

    def __init__(self):
        """Initialize the document store interface"""
        # Find the rag/documents directory relative to this script
        rag_dir = Path(__file__).parent.parent.parent
        self.documents_dir = rag_dir / "documents"

    def find_markdown_files(self) -> List[Path]:
        """
        Find all markdown files in the documents directory

        Returns:
            List of markdown file paths
        """
        if not self.documents_dir.exists():
            return []

        # Search for markdown files
        md_files = []
        for md_pattern in ["*.md", "*.MD"]:
            md_files.extend(self.documents_dir.glob(md_pattern))

        return sorted(md_files)

    def list_available_documents(self) -> None:
        """Display all available markdown files"""
        print(f"📁 Available markdown documents in: {self.documents_dir}")
        print("=" * 80)

        md_files = self.find_markdown_files()

        if not md_files:
            print(f"❌ No markdown files found in {self.documents_dir}")
            return

        print(f"✅ Found {len(md_files)} markdown file(s):")
        print("-" * 60)

        for i, md_file in enumerate(md_files, 1):
            file_size = md_file.stat().st_size / 1024  # KB
            print(f"  {i:2d}. 📄 {md_file.name} ({file_size:.1f} KB)")

    async def store_all_documents(self) -> None:
        """
        Store all markdown documents from the documents directory
        """
        md_files = self.find_markdown_files()

        if not md_files:
            print(f"❌ No markdown files found in {self.documents_dir}")
            return

        print(f"🚀 STORING ALL DOCUMENTS")
        print("=" * 80)
        print(f"📁 Found {len(md_files)} document(s) to store")
        print()

        successful = 0
        failed = 0
        failed_files = []

        for i, file_path in enumerate(md_files, 1):
            print(f"\n{'='*80}")
            print(f"📄 [{i}/{len(md_files)}] Processing: {file_path.name}")
            print('='*80)

            try:
                await self.store_document(file_path)
                successful += 1
            except Exception as e:
                failed += 1
                failed_files.append((file_path.name, str(e)))
                print(f"❌ Failed to store {file_path.name}: {e}")

        # Final summary
        print(f"\n\n{'='*80}")
        print(f"📊 BATCH STORAGE SUMMARY")
        print('='*80)
        print(f"✅ Successfully stored: {successful}/{len(md_files)}")
        print(f"❌ Failed: {failed}/{len(md_files)}")

        if failed_files:
            print(f"\n⚠️  Failed files:")
            for filename, error in failed_files:
                print(f"   • {filename}: {error}")

    async def store_document(self, file_path: Path, custom_title: str = None) -> None:
        """
        Store a document in the database with chunking and embeddings

        Args:
            file_path: Path to the markdown file
            custom_title: Optional custom title (uses filename if not provided)
        """
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            return

        print(f"📖 Reading document: {file_path.name}")
        
        import time
        total_start_time = time.time()

        try:
            # Read the markdown content
            read_start = time.time()
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            read_time = time.time() - read_start

            # Determine title
            if custom_title:
                title = custom_title
            else:
                # Use filename without extension as title
                title = file_path.stem.replace("_", " ").replace("-", " ").title()

            print(f"📝 Title: {title}")
            print(f"📄 Content length: {len(content)} characters")
            print(f"⏱️  File read time: {read_time:.3f}s")

            # Initialize database connection
            print("\n🔌 Connecting to database...")
            db_start = time.time()
            db_service = DatabaseService()
            await db_service.initialize()
            
            async with db_service.get_connection() as conn:
                db_time = time.time() - db_start
                print(f"✅ Connected to database ({db_time:.3f}s)")

                # Create document store
                store_start = time.time()
                store = DocumentStore(
                    db_connection=conn,
                    embedding_provider="openai",
                    max_chunk_tokens=512,
                    max_chunk_words=200,
                    use_llm_summary=True,
                    llm_model="gpt-4o-mini",
                )
                store_init_time = time.time() - store_start
                print(f"✅ Initialized DocumentStore ({store_init_time:.3f}s)")

                print("\n📝 Processing document...")
                process_start = time.time()
                
                # Store the document
                result = await store.store_document(
                    title=title, content=content, generate_summary=True
                )
                
                process_time = time.time() - process_start

                total_time = time.time() - total_start_time
                
                print(f"\n🎉 Document stored successfully!")
                print("=" * 60)
                print(f"📄 Document ID: {result.document_id}")
                print(f"📝 Title: {result.title}")
                print(
                    f"📄 Summary: {result.summary[:100]}{'...' if len(result.summary) > 100 else ''}"
                )
                print(f"🔢 Total chunks: {result.total_chunks}")
                print(f"📊 Total tokens: {result.total_tokens}")
                print(
                    f"🆔 Chunk IDs: {result.chunk_ids[:3]}{'...' if len(result.chunk_ids) > 3 else ''}"
                )
                
                print(f"\n⏱️  TIMING")
                print("=" * 40)
                print(f"📝 Chunking + Embeddings + Storage: {process_time:.3f}s")
                print(f"🕒 Total time: {total_time:.3f}s")

                # Get storage stats
                print(f"\n📊 STORAGE STATISTICS")
                print("=" * 40)
                stats = await store.get_storage_stats()
                print(f"📄 Total documents: {stats['total_documents']}")
                print(f"📚 Total chunks: {stats['total_chunks']}")
                print(
                    f"📈 Avg chunks per document: {stats['avg_chunks_per_document']:.1f}"
                )
                print(f"🤖 Embedding provider: {stats['embedding_provider']}")

            await db_service.close()

        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
        except Exception as e:
            print(f"❌ Storage failed: {e}")
            import traceback

            traceback.print_exc()


async def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Store markdown documents in the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available documents in rag/documents
  python store_document.py --list

  # Store all markdown documents
  python store_document.py --all

  # Store specific document
  python store_document.py --file transformers.md

  # Store with custom title
  python store_document.py --file transformers.md --title "Attention Mechanism Paper"
        """,
    )

    parser.add_argument(
        "--file",
        "-f",
        help="Specific markdown file to store (must be in rag/documents)",
    )

    parser.add_argument(
        "--title", "-t", help="Custom title for the document (optional)"
    )

    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available markdown files and exit",
    )

    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Store all markdown files from rag/documents directory",
    )

    args = parser.parse_args()

    # Initialize the store interface
    store_interface = DocumentStoreInterface()

    if args.list:
        # List available documents
        store_interface.list_available_documents()
        return

    if args.all:
        # Store all markdown documents
        await store_interface.store_all_documents()
        return

    if args.file:
        # Store specific file
        file_path = Path(args.file)

        # If it's not absolute, look in documents directory
        if not file_path.is_absolute():
            candidate = store_interface.documents_dir / args.file
            if candidate.exists():
                file_path = candidate

        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            print(f"💡 Looked in: {store_interface.documents_dir}")
            return

        print(f"🚀 DOCUMENT STORAGE")
        print("=" * 60)
        await store_interface.store_document(file_path, args.title)
    else:
        # Default to listing if no specific action
        print("💡 Use --file to store a document, --all to store all documents, or --list to see available files")
        store_interface.list_available_documents()


if __name__ == "__main__":
    asyncio.run(main())
