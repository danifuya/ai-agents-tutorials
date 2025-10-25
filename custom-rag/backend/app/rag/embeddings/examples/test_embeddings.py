#!/usr/bin/env python3
"""
Example usage of the EmbeddingGenerator for RAG pipeline

This script demonstrates:
1. Single text embedding generation
2. Batch embedding generation
3. Different provider usage (OpenAI, Jina, Local)
4. Cost estimation
5. Performance comparison
"""

import os
import sys
import time
from typing import List
import dotenv

dotenv.load_dotenv(".env.dev")

# Add the backend directory to Python path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../"))

from app.rag.embeddings.embedding_generator import EmbeddingGenerator


def test_single_embedding():
    """Test single text embedding generation"""
    print("🔍 TESTING SINGLE EMBEDDING GENERATION")
    print("=" * 60)

    # Test text
    text = "The quick brown fox jumps over the lazy dog."

    # Test with different providers (if available)
    providers_to_test = []

    # Add OpenAI if API key is available
    if os.getenv("OPENAI_API_KEY"):
        providers_to_test.append(("openai", "text-embedding-3-small"))

    # Add Jina if API key is available
    if os.getenv("JINA_API_KEY"):
        providers_to_test.append(("jina", "jina-embeddings-v2-base-en"))

    for provider_name, model in providers_to_test:
        print(f"\n📊 Testing {provider_name.upper()} - {model}")
        print("-" * 50)

        try:
            # Create generator
            api_key = None
            if provider_name == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif provider_name == "jina":
                api_key = os.getenv("JINA_API_KEY")

            generator = EmbeddingGenerator(
                provider=provider_name, api_key=api_key, model=model
            )

            # Generate embedding
            result = generator.embed(text)

            # Display results
            print(f"✅ Success!")
            print(f"   📝 Text: {text[:50]}...")
            print(f"   📏 Embedding dimensions: {len(result.embedding)}")
            print(f"   🔢 Tokens used: {result.tokens_used}")
            print(f"   ⏱️  Processing time: {result.processing_time:.3f}s")
            print(f"   🏷️  Provider: {result.provider}")
            print(f"   📊 First 5 values: {result.embedding[:5]}")

            # Test cost estimation (OpenAI only)
            if provider_name == "openai":
                cost = generator.estimate_cost(text)
                print(f"   💰 Estimated cost: ${cost:.6f}")

        except Exception as e:
            print(f"❌ Failed: {str(e)}")


def test_batch_embedding():
    """Test batch embedding generation"""
    print("\n\n🔍 TESTING BATCH EMBEDDING GENERATION")
    print("=" * 60)

    # Test texts
    texts = [
        "Artificial intelligence is transforming modern society.",
        "Machine learning models require large datasets for training.",
        "Natural language processing enables computers to understand text.",
        "Deep learning networks can recognize patterns in complex data.",
        "Embeddings capture semantic meaning in high-dimensional vectors.",
    ]

    # Test with local provider (always available)
    try:
        print(f"\n📊 Testing LOCAL batch embedding")
        print("-" * 50)

        generator = EmbeddingGenerator(provider="local")

        # Generate batch embeddings
        batch_result = generator.embed_batch(texts)

        # Display results
        print(f"✅ Batch embedding successful!")
        print(f"   📝 Number of texts: {len(texts)}")
        print(f"   📏 Embedding dimensions: {len(batch_result.embeddings[0])}")
        print(f"   🔢 Total tokens: {batch_result.total_tokens}")
        print(f"   ⏱️  Total processing time: {batch_result.processing_time:.3f}s")
        print(
            f"   📊 Average time per text: {batch_result.processing_time / len(texts):.3f}s"
        )
        print(f"   🏷️  Provider: {batch_result.provider}")

        # Show individual results
        print(f"\n📋 Individual Results:")
        for i, result in enumerate(batch_result.individual_results):
            print(
                f"   {i + 1}. {result.input_text[:40]}... -> {result.tokens_used} tokens"
            )

    except Exception as e:
        print(f"❌ Batch embedding failed: {str(e)}")


def test_provider_info():
    """Test provider information retrieval"""
    print("\n\n🔍 TESTING PROVIDER INFORMATION")
    print("=" * 60)

    providers = ["local"]  # Always available

    # Add other providers if API keys are available
    if os.getenv("OPENAI_API_KEY"):
        providers.append("openai")
    if os.getenv("JINA_API_KEY"):
        providers.append("jina")

    for provider_name in providers:
        try:
            print(f"\n📊 {provider_name.upper()} Provider Info")
            print("-" * 30)

            api_key = None
            if provider_name == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif provider_name == "jina":
                api_key = os.getenv("JINA_API_KEY")

            generator = EmbeddingGenerator(provider=provider_name, api_key=api_key)
            info = generator.get_provider_info()

            print(f"   🏷️  Provider: {info['provider']}")
            print(f"   🎯 Default model: {info['default_model']}")
            print(f"   📋 Available models: {info['available_models']}")
            print(f"   💾 Caching enabled: {info['caching_enabled']}")
            print(f"   🔄 Max retries: {info['max_retries']}")

        except Exception as e:
            print(f"❌ Failed to get {provider_name} info: {str(e)}")


def test_caching():
    """Test embedding caching functionality"""
    print("\n\n🔍 TESTING CACHING FUNCTIONALITY")
    print("=" * 60)

    text = "This text will be embedded twice to test caching."

    try:
        # Create generator with caching enabled
        generator = EmbeddingGenerator(provider="local", enable_caching=True)

        # First embedding (should generate)
        print("📊 First embedding (generating)...")
        start_time = time.time()
        result1 = generator.embed(text)
        time1 = time.time() - start_time

        # Second embedding (should use cache)
        print("📊 Second embedding (using cache)...")
        start_time = time.time()
        result2 = generator.embed(text)
        time2 = time.time() - start_time

        # Compare results
        print(f"✅ Caching test results:")
        print(f"   ⏱️  First call time: {time1:.4f}s")
        print(f"   ⏱️  Second call time: {time2:.4f}s")
        print(f"   🚀 Speedup: {time1 / time2:.1f}x faster")
        print(f"   ✓ Embeddings match: {result1.embedding == result2.embedding}")

    except Exception as e:
        print(f"❌ Caching test failed: {str(e)}")


def test_with_chunked_documents():
    """Test embedding generation with chunked documents (like from our chunker)"""
    print("\n\n🔍 TESTING WITH CHUNKED DOCUMENTS")
    print("=" * 60)

    # Simulate chunks from markdown chunker
    chunks = [
        "Introduction to Machine Learning\n\nMachine learning is a subset of artificial intelligence that focuses on algorithms.",
        "Types of Machine Learning\n\n1. Supervised Learning\n2. Unsupervised Learning\n3. Reinforcement Learning",
        "Applications\n\n- Image Recognition\n- Natural Language Processing\n- Recommendation Systems",
        "Future Trends\n\nThe future of ML includes explainable AI, automated ML, and edge computing.",
    ]

    try:
        generator = EmbeddingGenerator(provider="local")

        print(f"📊 Processing {len(chunks)} document chunks...")

        # Generate embeddings for all chunks
        start_time = time.time()
        batch_result = generator.embed_batch(chunks, batch_size=2)  # Smaller batches
        processing_time = time.time() - start_time

        print(f"✅ Document chunk embedding completed!")
        print(f"   📝 Chunks processed: {len(chunks)}")
        print(f"   📏 Embedding dimensions: {len(batch_result.embeddings[0])}")
        print(f"   🔢 Total tokens: {batch_result.total_tokens}")
        print(f"   ⏱️  Total time: {processing_time:.3f}s")
        print(f"   📊 Average per chunk: {processing_time / len(chunks):.3f}s")

        # Show chunk details
        print(f"\n📋 Chunk Details:")
        for i, (chunk, result) in enumerate(
            zip(chunks, batch_result.individual_results)
        ):
            preview = chunk.replace("\n", " ")[:50] + "..."
            print(f"   {i + 1}. {preview} -> {result.tokens_used} tokens")

        # This would be where you'd save to vector database
        print(f"\n💾 Ready for vector database storage!")

    except Exception as e:
        print(f"❌ Document chunk embedding failed: {str(e)}")


def main():
    """Run all embedding tests"""
    print("🚀 EMBEDDING GENERATOR TEST SUITE")
    print("=" * 80)

    # Check for API keys
    api_keys_available = []
    if os.getenv("OPENAI_API_KEY"):
        api_keys_available.append("OpenAI")
    if os.getenv("JINA_API_KEY"):
        api_keys_available.append("Jina")

    if api_keys_available:
        print(f"🔑 API keys found for: {', '.join(api_keys_available)}")
    else:
        print("🔑 No API keys found - testing with local models only")
    print(
        "💡 Set OPENAI_API_KEY and/or JINA_API_KEY environment variables for full testing"
    )

    # Run all tests
    test_single_embedding()
    # test_batch_embedding()
    # test_provider_info()
    # test_caching()
    # test_with_chunked_documents()

    print("\n\n✨ All embedding tests completed!")


if __name__ == "__main__":
    main()
