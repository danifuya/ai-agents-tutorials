#!/usr/bin/env python3
"""
Test Voyage AI Reranker

Simple test script to verify reranker functionality
"""

import os
import sys
import dotenv
import asyncio

# Load environment variables
dotenv.load_dotenv(".env.dev")

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../"))

from app.rag.reranking.voyage_reranker import VoyageReranker


async def test_reranker():
    """Test the reranker with sample data"""
    print("🔄 Testing Voyage AI Reranker")
    print("=" * 60)

    # Sample query
    query = "What are transformers in machine learning?"

    # Sample chunks (simulating retrieval results)
    chunks = [
        {
            "chunk_id": 1,
            "content": "Transformers are a type of neural network architecture that uses self-attention mechanisms.",
            "semantic_score": 0.75,
            "keyword_score": 3,
            "hybrid_score": 0.72,
        },
        {
            "chunk_id": 2,
            "content": "The weather today is sunny with a chance of rain in the afternoon.",
            "semantic_score": 0.45,
            "keyword_score": 0,
            "hybrid_score": 0.32,
        },
        {
            "chunk_id": 3,
            "content": "Deep learning models like transformers have revolutionized natural language processing.",
            "semantic_score": 0.82,
            "keyword_score": 2,
            "hybrid_score": 0.80,
        },
        {
            "chunk_id": 4,
            "content": "The transformer architecture was introduced in the paper 'Attention is All You Need'.",
            "semantic_score": 0.88,
            "keyword_score": 4,
            "hybrid_score": 0.85,
        },
    ]

    print(f"📝 Query: {query}")
    print(f"📚 Testing with {len(chunks)} chunks")
    print()

    try:
        # Initialize reranker
        reranker = VoyageReranker(model="rerank-2.5")
        print("✅ Reranker initialized")
        print(f"🤖 Model: {reranker.model}")
        print()

        # Show original order
        print("📊 ORIGINAL ORDER (by hybrid score):")
        print("-" * 60)
        for i, chunk in enumerate(chunks, 1):
            print(
                f"{i}. [Chunk {chunk['chunk_id']}] Hybrid: {chunk['hybrid_score']:.3f}"
            )
            print(f"   {chunk['content'][:80]}...")
            print()

        # Rerank chunks
        print("🔄 Reranking chunks...")
        result = await reranker.rerank(query=query, chunks=chunks, top_k=None)
        print(f"✅ Reranking completed in {result.rerank_time:.3f}s")
        print()

        # Show reranked order
        print("🎯 RERANKED ORDER (by Voyage AI):")
        print("-" * 60)
        for i, chunk in enumerate(result.reranked_chunks, 1):
            original_pos = (
                chunks.index(
                    [c for c in chunks if c["chunk_id"] == chunk["chunk_id"]][0]
                )
                + 1
            )
            print(
                f"{i}. [Chunk {chunk['chunk_id']}] Rerank: {chunk['rerank_score']:.3f} | Hybrid: {chunk['hybrid_score']:.3f} | Was #{original_pos}"
            )
            print(f"   {chunk['content'][:80]}...")
            print()

        # Summary
        print("📈 SUMMARY")
        print("-" * 60)
        print(f"Original count: {result.original_count}")
        print(f"Reranked count: {result.reranked_count}")
        print(f"Rerank time: {result.rerank_time:.3f}s")
        print(f"Model used: {result.model}")

    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("💡 Make sure VOYAGE_API_KEY is set in your .env.dev")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_reranker())
