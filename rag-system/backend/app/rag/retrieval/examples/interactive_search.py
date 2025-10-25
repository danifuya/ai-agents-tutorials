#!/usr/bin/env python3
"""
Interactive retrieval terminal for testing search queries

This script provides an interactive terminal where you can:
1. Enter search queries continuously 
2. See detailed retrieval results and performance metrics
3. Test different query types and see how the system performs
4. Exit when done testing
"""

import os
import sys
import dotenv
import asyncio

# Load environment variables and override POSTGRES_HOST for Docker
dotenv.load_dotenv(".env.dev")
os.environ['POSTGRES_HOST'] = 'localhost'

# Add the backend directory to Python path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../"))

from app.rag.retrieval.hierarchical_retrieval import HierarchicalRetrieval
from app.rag.retrieval.query_processing import QueryProcessor
from app.rag.chunking.markdown_chunker import GFMContextPathChunker, ChunkerOptions
from app.db.connection import DatabaseService


class InteractiveRetrieval:
    """Interactive retrieval system for terminal-based testing"""
    
    def __init__(self):
        self.db_service = None
        self.query_processor = None
        self.retrieval_engine = None
        self.connection = None
        self.query_count = 0
        
        # Initialize chunker for token counting
        chunker_options = ChunkerOptions()
        self.chunker = GFMContextPathChunker(chunker_options)
        
    async def initialize(self):
        """Initialize database connection and retrieval components"""
        print("🔄 Initializing retrieval system...")
        
        # Connect to database
        self.db_service = DatabaseService()
        await self.db_service.initialize()
        self.connection = await self.db_service.get_connection().__aenter__()
        
        # Initialize components
        self.query_processor = QueryProcessor(embedding_provider="openai")
        self.retrieval_engine = HierarchicalRetrieval(
            db_connection=self.connection,
            stage1_similarity_threshold=0.3,
            stage1_document_limit=10,
            stage2_chunk_limit=5
        )
        
        print("✅ System initialized successfully!")
        
        # Show system stats
        await self._show_system_stats()
    
    async def cleanup(self):
        """Cleanup database connections"""
        if self.connection:
            await self.connection.__aexit__(None, None, None)
        if self.db_service:
            await self.db_service.close()
    
    async def _show_system_stats(self):
        """Display system statistics"""
        print("\n📊 SYSTEM STATISTICS")
        print("=" * 50)
        
        stats = await self.retrieval_engine.get_retrieval_stats()
        print(f"📄 Total documents: {stats['total_documents']}")
        print(f"📚 Total chunks: {stats['total_chunks']}")
        print(f"📈 Avg chunks per document: {stats['avg_chunks_per_document']:.1f}")
        print(f"🎯 Stage 1 threshold: {stats['stage1_threshold']}")
        print(f"📊 Stage 1 doc limit: {stats['stage1_document_limit']}")
        print(f"🔍 Stage 2 chunk limit: {stats['stage2_chunk_limit']}")
        
        # Get embedding provider info from query processor
        embedding_info = self.query_processor.get_embedding_info()
        print(f"🤖 Embedding provider: {embedding_info['provider']}")
        print(f"🔬 Search space reduction: {stats['search_space_reduction']}")
    
    def _format_performance_metrics(self, processed_query, retrieval_result):
        """Format performance metrics for display"""
        total_time = processed_query.processing_time + retrieval_result.total_time

        print(f"\n⏱️  PERFORMANCE METRICS")
        print("=" * 40)
        print(f"🔤 Query processing: {processed_query.processing_time:.3f}s")
        print(f"📄 Stage 1 (docs): {retrieval_result.stage1_time:.3f}s")
        print(f"📚 Stage 2 (chunks): {retrieval_result.stage2_time:.3f}s")
        if retrieval_result.reranked:
            print(f"🔄 Stage 3 (rerank): {retrieval_result.rerank_time:.3f}s")
        print(f"🎯 Total retrieval: {retrieval_result.total_time:.3f}s")
        print(f"⚡ Total end-to-end: {total_time:.3f}s")
        print(f"🧠 Tokens used: {processed_query.tokens_used}")
        print(f"📊 Embedding dims: {len(processed_query.embedding)}")
        if retrieval_result.reranked:
            print(f"✨ Reranking: enabled (Voyage AI)")
    
    def _format_retrieval_stats(self, retrieval_result):
        """Format retrieval statistics"""
        print(f"\n📈 RETRIEVAL STATISTICS")
        print("=" * 40)
        print(f"📄 Documents searched: {retrieval_result.total_documents_searched}")
        print(f"📚 Chunks found: {retrieval_result.total_chunks_found}")
        
        if retrieval_result.total_documents_searched > 0:
            avg_chunks = retrieval_result.total_chunks_found / retrieval_result.total_documents_searched
            print(f"📊 Avg chunks per doc: {avg_chunks:.1f}")
        
        if retrieval_result.document_candidates:
            doc_scores = [doc.get('similarity_score', 0) for doc in retrieval_result.document_candidates]
            if doc_scores:
                print(f"🎯 Best doc score: {max(doc_scores):.3f}")
                print(f"📉 Worst doc score: {min(doc_scores):.3f}")
                print(f"📊 Avg doc score: {sum(doc_scores)/len(doc_scores):.3f}")
    
    def _format_results(self, retrieval_result):
        """Format and display search results"""
        if not retrieval_result.chunks:
            print(f"\n❌ No results found")
            return
        
        # Calculate token counts
        total_tokens = 0
        chunk_tokens = []
        
        for chunk in retrieval_result.chunks:
            content = chunk['content']
            tokens = self.chunker.estimate_jina_token_count(content)
            chunk_tokens.append(tokens)
            total_tokens += tokens
        
        print(f"\n🎯 TOP RESULTS ({len(retrieval_result.chunks)} found)")
        print(f"📊 Total tokens retrieved: {total_tokens}")
        print("=" * 60)
        
        for i, chunk in enumerate(retrieval_result.chunks):
            # Get all available scores
            similarity_score = chunk.get('similarity_score', 0)
            semantic_score = chunk.get('semantic_score', similarity_score)  # fallback to similarity_score
            keyword_score = chunk.get('keyword_score', 0)
            hybrid_score = chunk.get('hybrid_score', similarity_score)  # fallback to similarity_score
            rerank_score = chunk.get('rerank_score', None)
            distance = chunk.get('distance', 1.0)
            doc_title = chunk.get('document_title', 'Unknown')
            full_content = chunk['content']
            tokens = chunk_tokens[i]

            # Determine primary score for relevance (use rerank if available)
            primary_score = rerank_score if rerank_score is not None else hybrid_score

            # Add relevance indicator based on primary score
            if primary_score >= 0.8:
                relevance = "🔥 HIGH"
            elif primary_score >= 0.6:
                relevance = "🟡 MED"
            elif primary_score >= 0.4:
                relevance = "🔵 LOW"
            else:
                relevance = "⚪ VERY LOW"

            # Keyword match indicator
            keyword_indicator = "🎯 MATCH" if keyword_score > 0 else "❌ NO MATCH"

            # Header line with rerank score if available
            if rerank_score is not None:
                print(f"\n{i+1}. {relevance} | 🔄 Rerank: {rerank_score:.3f} | Hybrid: {hybrid_score:.3f}")
            else:
                print(f"\n{i+1}. {relevance} | Hybrid: {hybrid_score:.3f} | Distance: {distance:.3f}")

            # Score details line
            if rerank_score is not None:
                print(f"   🧠 Semantic: {semantic_score:.3f} | 🔍 Keyword: {keyword_score:.2f} | {keyword_indicator} | Distance: {distance:.3f}")
            else:
                print(f"   🧠 Semantic: {semantic_score:.3f} | 🔍 Keyword: {keyword_score:.2f} | {keyword_indicator}")

            print(f"   📄 Document: {doc_title}")
            print(f"   🆔 Chunk ID: {chunk.get('chunk_id', 'N/A')}")
            print(f"   📊 Tokens: {tokens}")
            print(f"   📝 Full Content:")
            print("   " + "─" * 60)
            # Print full content with proper indentation
            for line in full_content.split('\n'):
                print(f"   {line}")
            print("   " + "─" * 60)
    
    async def run_interactive_session(self):
        """Run the interactive retrieval session"""
        print("\n" + "="*80)
        print("🚀 INTERACTIVE RETRIEVAL TERMINAL")
        print("="*80)
        print("💡 Enter your search queries below")
        print("💡 Type 'quit', 'exit', or 'q' to stop")
        print("💡 Type 'stats' to see system statistics")
        print("💡 Type 'help' for tips")
        print("="*80)
        
        while True:
            try:
                # Get user input
                query = input(f"\n[Query #{self.query_count + 1}] Enter search query: ").strip()
                
                # Handle special commands
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Thanks for testing the retrieval system.")
                    break
                
                if query.lower() == 'stats':
                    await self._show_system_stats()
                    continue
                
                if query.lower() == 'help':
                    self._show_help()
                    continue
                
                if not query:
                    print("⚠️  Please enter a query or 'quit' to exit")
                    continue
                
                # Process the query
                print(f"\n🔍 Processing: '{query}'")
                print("-" * 60)
                
                self.query_count += 1
                
                # Step 1: Process query
                print("1️⃣ Processing query...")
                processed_query = self.query_processor.process_query(query)
                print(f"   ✅ Query processed in {processed_query.processing_time:.3f}s")
                
                # Step 2: Run retrieval
                print("2️⃣ Running hierarchical search...")
                retrieval_result = await self.retrieval_engine.search(
                    processed_query.embedding,
                    processed_query.cleaned_text
                )
                print(f"   ✅ Search completed in {retrieval_result.total_time:.3f}s")
                
                # Step 3: Display comprehensive results
                self._format_performance_metrics(processed_query, retrieval_result)
                self._format_retrieval_stats(retrieval_result)
                self._format_results(retrieval_result)
                
            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error processing query: {e}")
                continue
    
    def _show_help(self):
        """Show help information"""
        print("\n💡 SEARCH TIPS")
        print("=" * 40)
        print("🔍 Try different query types:")
        print("   • Specific terms: 'attention mechanism'")
        print("   • Questions: 'how do transformers work?'")
        print("   • Concepts: 'neural network architecture'")
        print("   • Technical terms: 'self-attention layers'")
        print("\n📊 Scoring explanation:")
        print("   • Rerank score: 0-1 (Voyage AI relevance)")
        print("   • Hybrid score: 0-1 (semantic + keyword)")
        print("   • Semantic score: 0-1 (embedding similarity)")
        print("   • Keyword score: 0+ (PGroonga text matching)")
        print("   • Distance: 0-1 (lower = more similar)")
        print("\n🔄 Three-stage retrieval:")
        print("   • Stage 1: Document filtering by summary")
        print("   • Stage 2: Hybrid chunk retrieval within docs")
        print("   • Stage 3: Reranking with Voyage AI (if enabled)")
        print("\n⚡ Performance tips:")
        print("   • Longer queries often get better results")
        print("   • Technical terms work well with embeddings")
        print("   • Reranking improves final ordering quality")
        print("   • Try variations of your query")


async def main():
    """Main function to run interactive retrieval"""
    # Check environment
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️  No database configuration found in .env.dev")
        print("💡 Make sure POSTGRES_HOST, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD are set")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  No OPENAI_API_KEY found in .env.dev")
        print("💡 Make sure OPENAI_API_KEY is set for embeddings")
        return
    
    # Initialize and run interactive session
    interactive_retrieval = InteractiveRetrieval()
    
    try:
        await interactive_retrieval.initialize()
        await interactive_retrieval.run_interactive_session()
    except Exception as e:
        print(f"❌ System error: {e}")
    finally:
        await interactive_retrieval.cleanup()
    
    print(f"\n📊 Session Summary:")
    print(f"   🔍 Total queries processed: {interactive_retrieval.query_count}")
    print(f"   ✨ Thanks for testing the retrieval system!")


if __name__ == "__main__":
    asyncio.run(main())