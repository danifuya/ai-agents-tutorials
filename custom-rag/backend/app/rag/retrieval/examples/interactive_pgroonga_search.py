#!/usr/bin/env python3
"""
Interactive PGroonga-only search terminal for testing keyword matching

This script provides an interactive terminal where you can:
1. Test PGroonga keyword matching directly on chunks
2. See keyword scores without semantic similarity
3. Understand how PGroonga scoring works
4. Test different query patterns and tokenization
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

from app.db.connection import DatabaseService
from app.rag.chunking.markdown_chunker import GFMContextPathChunker, ChunkerOptions


class PGroongaSearch:
    """PGroonga-only search for testing keyword matching"""

    def __init__(self):
        self.db_service = None
        self.connection = None
        self.query_count = 0

        # Initialize chunker for token counting
        chunker_options = ChunkerOptions()
        self.chunker = GFMContextPathChunker(chunker_options)

    async def initialize(self):
        """Initialize database connection"""
        print("🔄 Initializing PGroonga search system...")

        # Connect to database
        self.db_service = DatabaseService()
        await self.db_service.initialize()
        self.connection = await self.db_service.get_connection().__aenter__()

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

        # Get chunk count
        query = "SELECT COUNT(*) FROM document_chunks"
        async with self.connection.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchone()
            total_chunks = result[0]

        # Get document count
        query = "SELECT COUNT(*) FROM documents"
        async with self.connection.cursor() as cur:
            await cur.execute(query)
            result = await cur.fetchone()
            total_docs = result[0]

        print(f"📄 Total documents: {total_docs}")
        print(f"📚 Total chunks: {total_chunks}")
        print(f"📈 Avg chunks per document: {total_chunks/total_docs:.1f}")
        print(f"🔍 Search mode: PGroonga keyword matching only")
        print(f"🎯 Operator: &@~ (full-text search)")

    async def search_chunks(self, query_text: str, limit: int = 10):
        """
        Search chunks using PGroonga keyword matching only

        Args:
            query_text: Text query for keyword matching
            limit: Maximum results to return

        Returns:
            List of matching chunks with scores
        """
        import time

        start_time = time.time()

        query = """
            SELECT
                dc.id,
                dc.content,
                dc.document_id,
                d.title,
                pgroonga_score(dc.tableoid, dc.ctid) AS keyword_score
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE dc.content &@~ %s
            ORDER BY keyword_score DESC
            LIMIT %s
        """

        async with self.connection.cursor() as cur:
            await cur.execute(query, (query_text, limit))
            results = await cur.fetchall()

        search_time = time.time() - start_time

        # Format results
        chunks = []
        for result in results:
            chunks.append({
                'chunk_id': result[0],
                'content': result[1],
                'document_id': result[2],
                'document_title': result[3],
                'keyword_score': result[4],
            })

        return chunks, search_time

    def _format_results(self, chunks, query_text):
        """Format and display search results"""
        if not chunks:
            print(f"\n❌ No results found for '{query_text}'")
            return

        # Calculate token counts
        total_tokens = 0
        chunk_tokens = []

        for chunk in chunks:
            content = chunk['content']
            tokens = self.chunker.estimate_jina_token_count(content)
            chunk_tokens.append(tokens)
            total_tokens += tokens

        print(f"\n🎯 KEYWORD MATCHES ({len(chunks)} found)")
        print(f"📊 Total tokens retrieved: {total_tokens}")
        print("=" * 80)

        for i, chunk in enumerate(chunks):
            keyword_score = chunk['keyword_score']
            doc_title = chunk['document_title']
            full_content = chunk['content']
            tokens = chunk_tokens[i]

            # Add relevance indicator based on keyword score
            if keyword_score >= 10:
                relevance = "🔥 VERY HIGH"
            elif keyword_score >= 5:
                relevance = "🟡 HIGH"
            elif keyword_score >= 2:
                relevance = "🔵 MEDIUM"
            else:
                relevance = "⚪ LOW"

            print(f"\n{i+1}. {relevance} | Keyword Score: {keyword_score:.2f}")
            print(f"   📄 Document: {doc_title}")
            print(f"   🆔 Chunk ID: {chunk['chunk_id']}")
            print(f"   📊 Tokens: {tokens}")
            print(f"   📝 Full Content:")
            print("   " + "─" * 76)
            # Print full content with proper indentation
            for line in full_content.split('\n'):
                print(f"   {line}")
            print("   " + "─" * 76)

    async def run_interactive_session(self):
        """Run the interactive search session"""
        print("\n" + "="*80)
        print("🚀 INTERACTIVE PGROONGA SEARCH TERMINAL")
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
                    print("\n👋 Goodbye! Thanks for testing PGroonga search.")
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
                print(f"\n🔍 Searching: '{query}'")
                print("-" * 60)

                self.query_count += 1

                # Run PGroonga search
                print("🔎 Running PGroonga keyword search...")
                chunks, search_time = await self.search_chunks(query, limit=5)
                print(f"   ✅ Search completed in {search_time:.3f}s")

                # Display results
                self._format_results(chunks, query)

                # Show timing
                print(f"\n⏱️  PERFORMANCE")
                print("=" * 40)
                print(f"⚡ Total search time: {search_time:.3f}s")
                print(f"📊 Results returned: {len(chunks)}")

            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error processing query: {e}")
                import traceback
                traceback.print_exc()
                continue

    def _show_help(self):
        """Show help information"""
        print("\n💡 PGROONGA SEARCH TIPS")
        print("=" * 40)
        print("🔍 Query syntax:")
        print("   • Simple word: 'GeForce'")
        print("   • Multiple words: 'GeForce RTX'")
        print("   • Wildcards: '*Force*' (if supported)")
        print("   • Phrases: '\"exact phrase\"'")
        print("\n📊 Scoring explanation:")
        print("   • Keyword score = Term Frequency (TF)")
        print("   • Score counts word-level occurrences")
        print("   • Higher score = more keyword matches")
        print("   • Case sensitivity depends on normalizer")
        print("\n⚙️ Current configuration:")
        print("   • Tokenizer: TokenNgram(n=2) - bigram")
        print("   • Normalizer: NormalizerNFKC130(remove_symbol=true)")
        print("   • Fuzzy matching: 0.34 max distance ratio")
        print("   • Operator: &@~ (full-text search)")
        print("\n⚡ Testing tips:")
        print("   • Test exact words from your content")
        print("   • Try different cases to test normalization")
        print("   • Compare scores across different queries")
        print("   • Look for patterns in scoring behavior")


async def main():
    """Main function to run interactive PGroonga search"""
    # Check environment
    if not os.getenv("POSTGRES_HOST"):
        print("⚠️  No database configuration found in .env.dev")
        print("💡 Make sure POSTGRES_HOST, POSTGRES_DATABASE, POSTGRES_USER, POSTGRES_PASSWORD are set")
        return

    # Initialize and run interactive session
    pgroonga_search = PGroongaSearch()

    try:
        await pgroonga_search.initialize()
        await pgroonga_search.run_interactive_session()
    except Exception as e:
        print(f"❌ System error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pgroonga_search.cleanup()

    print(f"\n📊 Session Summary:")
    print(f"   🔍 Total queries processed: {pgroonga_search.query_count}")
    print(f"   ✨ Thanks for testing PGroonga search!")


if __name__ == "__main__":
    asyncio.run(main())
