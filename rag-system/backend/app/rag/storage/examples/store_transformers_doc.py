#!/usr/bin/env python3
"""
Example script to store transformers.md document in the database

This script demonstrates:
1. Reading a markdown file from disk
2. Storing it using DocumentStore with auto-chunking and embedding
3. Displaying storage results and statistics
"""

import os
import sys
import dotenv

# Load environment variables and override POSTGRES_HOST for Docker
dotenv.load_dotenv(".env.dev")
os.environ["POSTGRES_HOST"] = "localhost"

# Add the backend directory to Python path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../"))

from app.rag.storage.document_store import DocumentStore
from app.db.connection import DatabaseService


async def store_transformers_document():
    """Store the transformers.md document in the database"""
    print("📄 STORING TRANSFORMERS DOCUMENT")
    print("=" * 60)

    # Path to transformers.md file in rag/documents (relative to this script)
    script_dir = os.path.dirname(__file__)
    transformers_file = os.path.join(script_dir, "../../documents/transformers.md")
    transformers_file = os.path.abspath(transformers_file)  # Convert to absolute path

    try:
        # Read the markdown file
        print(f"📖 Reading file: {transformers_file}")
        with open(transformers_file, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"✅ File loaded: {len(content)} characters")

        # Connect to database
        db_service = DatabaseService()
        await db_service.initialize()

        async with db_service.get_connection() as conn:
            print("✅ Connected to database")

            # Create document store with LLM summarization
            store = DocumentStore(
                db_connection=conn,
                embedding_provider="openai",  # Use OpenAI embeddings
                max_chunk_tokens=512,  # Reasonable chunk size
                max_chunk_words=200,
                llm_model="gpt-4o-mini",  # OpenAI model for summary
                use_llm_summary=True,  # Enable LLM-based summary
            )

            print(
                "✅ Initialized DocumentStore with OpenAI embeddings and gpt-4o-mini summarization"
            )

            # Store the document
            print("\n📝 Storing document...")
            result = await store.store_document(
                title="Attention Is All You Need",
                content=content,
                generate_summary=True,
            )

            print(f"🎉 Document stored successfully!")
            print(f"   📄 Document ID: {result.document_id}")
            print(f"   📝 Title: {result.title}")
            print(f"   📄 Summary: {result.summary[:150]}...")
            print(f"   🔢 Total chunks: {result.total_chunks}")
            print(f"   📊 Total tokens: {result.total_tokens}")
            print(f"   ⏱️  Processing time: {result.processing_time:.3f}s")
            print(
                f"   🆔 Chunk IDs: {result.chunk_ids[:5]}{'...' if len(result.chunk_ids) > 5 else ''}"
            )

            # Get storage stats
            print(f"\n📊 STORAGE STATISTICS")
            print("=" * 40)
            stats = await store.get_storage_stats()
            print(f"📄 Total documents: {stats['total_documents']}")
            print(f"📚 Total chunks: {stats['total_chunks']}")
            print(f"📈 Avg chunks per document: {stats['avg_chunks_per_document']:.1f}")
            print(f"🤖 Embedding provider: {stats['embedding_provider']}")

            return result.document_id

        await db_service.close()

    except FileNotFoundError:
        print(f"❌ File not found: {transformers_file}")
        return None
    except Exception as e:
        print(f"❌ Storage failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def main():
    """Main function to store transformers document"""
    print("🚀 TRANSFORMERS DOCUMENT STORAGE")
    print("=" * 80)

    # Check environment
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️  No database configuration found in .env.dev")
        print(
            "💡 Make sure POSTGRES_HOST, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD are set"
        )
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  No OPENAI_API_KEY found in .env.dev")
        print("💡 Make sure OPENAI_API_KEY is set for embeddings")
        return

    # Store the document
    document_id = await store_transformers_document()

    print(f"\n\n✨ Transformers document storage completed! Document ID: {document_id}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
