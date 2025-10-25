#!/usr/bin/env python3
"""
Example usage of DocumentStore for RAG document storage

This script demonstrates:
1. Connecting to database
2. Storing documents with auto-chunking and embedding
3. Searching for similar documents and chunks
4. Retrieving stored documents
5. Updating document content
6. Storage statistics
"""

import os
import sys
import dotenv
import psycopg

# Load environment variables
dotenv.load_dotenv(".env.dev")

# Add the backend directory to Python path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../"))

from app.rag.storage.document_store import DocumentStore


async def get_db_connection():
    """Create async database connection from environment variables"""
    connection_string = (
        f"host={os.getenv('localhost', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DATABASE', 'panacea')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'password')}"
    )

    try:
        conn = await psycopg.AsyncConnection.connect(connection_string)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure your database is running and .env.dev is configured")
        sys.exit(1)


async def test_document_storage():
    """Test basic document storage functionality"""
    print("🔍 TESTING DOCUMENT STORAGE")
    print("=" * 60)

    # Sample markdown content
    sample_content = """# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that focuses on algorithms and statistical models that computer systems use to perform tasks without explicit instructions.

## Types of Machine Learning

### 1. Supervised Learning
Supervised learning uses labeled training data to learn a mapping function from inputs to outputs.

### 2. Unsupervised Learning
Unsupervised learning finds hidden patterns in data without labeled examples.

### 3. Reinforcement Learning
Reinforcement learning learns through interaction with an environment using rewards and penalties.

## Applications

Machine learning has numerous applications including:
- Image recognition and computer vision
- Natural language processing
- Recommendation systems
- Fraud detection
- Autonomous vehicles

## Future Trends

The future of machine learning includes:
1. **Explainable AI**: Making AI decisions more transparent
2. **AutoML**: Automating machine learning workflows
3. **Edge computing**: Running ML models on edge devices
4. **Federated learning**: Training models across decentralized data
"""

    try:
        # Connect to database
        conn = await get_db_connection()

        # Create document store
        store = DocumentStore(
            db_connection=conn,
            embedding_provider="openai",
            max_chunk_tokens=256,  # Smaller chunks for demo
            max_chunk_words=100,
        )

        print("✅ Connected to database and created DocumentStore")

        # Store the document
        print("\n📝 Storing document...")
        result = await store.store_document(
            title="Introduction to Machine Learning", content=sample_content
        )

        print(f"✅ Document stored successfully!")
        print(f"   📄 Document ID: {result.document_id}")
        print(f"   📝 Title: {result.title}")
        print(f"   📄 Summary: {result.summary[:100]}...")
        print(f"   🔢 Total chunks: {result.total_chunks}")
        print(f"   📊 Total tokens: {result.total_tokens}")
        print(f"   ⏱️ Processing time: {result.processing_time:.3f}s")
        print(f"   🆔 Chunk IDs: {result.chunk_ids}")

        return result.document_id

    except Exception as e:
        print(f"❌ Document storage failed: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_storage_stats():
    """Test storage statistics"""
    print(f"\n\n🔍 TESTING STORAGE STATISTICS")
    print("=" * 60)

    try:
        conn = await get_db_connection()
        store = DocumentStore(conn, embedding_provider="openai")

        stats = await store.get_storage_stats()

        print(f"📊 Storage Statistics:")
        print(f"   📄 Total documents: {stats['total_documents']}")
        print(f"   🔢 Total chunks: {stats['total_chunks']}")
        print(
            f"   📈 Average chunks per document: {stats['avg_chunks_per_document']:.1f}"
        )
        print(f"   🤖 Embedding provider: {stats['embedding_provider']}")

    except Exception as e:
        print(f"❌ Storage stats failed: {e}")


async def main():
    """Run all DocumentStore tests"""
    print("🚀 DOCUMENT STORE TEST SUITE")
    print("=" * 80)

    # Check environment
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️  No database configuration found in .env.dev")
        print(
            "💡 Make sure POSTGRES_HOST, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD are set"
        )
        return

    # Run tests
    document_id = await test_document_storage()

    if document_id:
        await test_storage_stats()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
