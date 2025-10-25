from typing import List, Dict, Any, Optional
from psycopg import AsyncConnection
import json


class DocumentChunksRepository:
    """Repository for document_chunks table operations using psycopg3"""
    
    def __init__(self, connection: AsyncConnection):
        self.connection = connection
    
    async def create_chunk(self, content: str, embedding: List[float], document_id: int,
                    chunk_index: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Create a new document chunk with embedding.
        
        Args:
            content: The text content of the chunk
            embedding: Vector embedding of the content (1024 dimensions)
            document_id: Foreign key to the parent document
            chunk_index: Optional index of this chunk within the document
            metadata: Additional metadata as JSON (optional)
        
        Returns:
            id of the created chunk
        """
        query = """
            INSERT INTO document_chunks 
            (content, embedding, document_id, chunk_index, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        
        async with self.connection.cursor() as cur:
            await cur.execute(
                query, 
                (content, embedding, document_id, chunk_index, 
                 json.dumps(metadata) if metadata else None)
            )
            result = await cur.fetchone()
            await self.connection.commit()
        
        return result[0]
    
    async def create_chunks_batch(self, chunks: List[Dict[str, Any]]) -> List[int]:
        """
        Create multiple chunks in a single transaction.
        
        Args:
            chunks: List of dictionaries with keys: content, embedding, document_id
        
        Returns:
            List of created chunk ids
        """
        query = """
            INSERT INTO document_chunks 
            (content, embedding, document_id)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        
        chunk_ids = []
        async with self.connection.cursor() as cur:
            for chunk in chunks:
                await cur.execute(
                    query,
                    (
                        chunk['content'],
                        chunk['embedding'],
                        chunk['document_id']
                    )
                )
                result = await cur.fetchone()
                chunk_ids.append(result[0])
            
            await self.connection.commit()
        
        return chunk_ids
    
    async def get_chunk_by_id(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """Get chunk by ID"""
        query = """
            SELECT id, content, embedding, document_id
            FROM document_chunks 
            WHERE id = %s
        """
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (chunk_id,))
            result = await cur.fetchone()
        
        if result:
            return {
                'id': result[0],
                'content': result[1],
                'embedding': result[2],
                'document_id': result[3]
            }
        
        return None
    
    async def get_chunks_by_document_id(self, document_id: int) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        query = """
            SELECT id, content, embedding, document_id
            FROM document_chunks 
            WHERE document_id = %s
            ORDER BY id ASC
        """
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (document_id,))
            results = await cur.fetchall()
        
        chunks = []
        for result in results:
            chunks.append({
                'id': result[0],
                'content': result[1],
                'embedding': result[2],
                'document_id': result[3]
            })
        
        return chunks
    
    async def search_chunks_by_similarity(self, query_embedding: List[float], 
                                   document_id: Optional[int] = None, 
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search chunks by embedding similarity using cosine distance
        
        Args:
            query_embedding: The query vector to search against
            document_id: Optional filter by specific document
            limit: Maximum number of results to return
            
        Returns:
            List of chunks ordered by similarity (most similar first)
        """
        if document_id:
            query = """
                SELECT id, content, document_id, chunk_index, metadata,
                       (embedding <=> %s::vector) as distance
                FROM document_chunks 
                WHERE document_id = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            params = (query_embedding, document_id, query_embedding, limit)
        else:
            query = """
                SELECT id, content, document_id, chunk_index, metadata,
                       (embedding <=> %s::vector) as distance
                FROM document_chunks 
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            params = (query_embedding, query_embedding, limit)
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, params)
            results = await cur.fetchall()
        
        chunks = []
        for result in results:
            chunks.append({
                'id': result[0],
                'content': result[1],
                'document_id': result[2],
                'chunk_index': result[3],
                'metadata': json.loads(result[4]) if result[4] else {},
                'similarity_distance': result[5]
            })
        
        return chunks
    
    async def search_chunks_with_document_info(self, query_embedding: List[float], 
                                       limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search chunks by similarity and include parent document information
        
        Args:
            query_embedding: The query vector to search against
            limit: Maximum number of results to return
            
        Returns:
            List of chunks with document info, ordered by similarity
        """
        query = """
            SELECT 
                dc.id, dc.content, dc.document_id, dc.chunk_index, dc.metadata,
                d.title, d.summary, d.authors, d.date, d.type,
                (dc.embedding <=> %s::vector) as distance
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            ORDER BY dc.embedding <=> %s::vector
            LIMIT %s
        """
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (query_embedding, query_embedding, limit))
            results = await cur.fetchall()
        
        chunks = []
        for result in results:
            chunks.append({
                'id': result[0],
                'content': result[1],
                'document_id': result[2],
                'chunk_index': result[3],
                'metadata': json.loads(result[4]) if result[4] else {},
                'document_title': result[5],
                'document_summary': result[6],
                'document_authors': result[7],
                'document_date': result[8],
                'document_type': result[9],
                'similarity_distance': result[10]
            })
        
        return chunks
    
    async def update_chunk_content(self, chunk_id: int, content: str, embedding: List[float]) -> bool:
        """Update chunk content and its embedding"""
        query = """
            UPDATE document_chunks 
            SET content = %s, embedding = %s
            WHERE id = %s
        """
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (content, embedding, chunk_id))
            await self.connection.commit()
            return cur.rowcount == 1
    
    async def delete_chunk(self, chunk_id: int) -> bool:
        """Delete a specific chunk"""
        query = "DELETE FROM document_chunks WHERE id = %s"
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (chunk_id,))
            await self.connection.commit()
            return cur.rowcount == 1
    
    async def delete_chunks_by_document_id(self, document_id: int) -> int:
        """Delete all chunks for a specific document. Returns number of deleted chunks."""
        query = "DELETE FROM document_chunks WHERE document_id = %s"
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (document_id,))
            deleted_count = cur.rowcount
            await self.connection.commit()
            return deleted_count
    
    async def get_chunk_count_by_document_id(self, document_id: int) -> int:
        """Get the number of chunks for a specific document"""
        query = "SELECT COUNT(*) FROM document_chunks WHERE document_id = %s"
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, (document_id,))
            result = await cur.fetchone()
            return result[0] if result else 0
    
    async def get_chunks_paginated(self, offset: int = 0, limit: int = 100, 
                           document_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get chunks with pagination, optionally filtered by document"""
        if document_id:
            query = """
                SELECT id, content, document_id, chunk_index, metadata
                FROM document_chunks 
                WHERE document_id = %s
                ORDER BY chunk_index ASC NULLS LAST, id ASC
                OFFSET %s LIMIT %s
            """
            params = (document_id, offset, limit)
        else:
            query = """
                SELECT id, content, document_id, chunk_index, metadata
                FROM document_chunks 
                ORDER BY document_id, chunk_index ASC NULLS LAST, id ASC
                OFFSET %s LIMIT %s
            """
            params = (offset, limit)
        
        async with self.connection.cursor() as cur:
            await cur.execute(query, params)
            results = await cur.fetchall()
        
        chunks = []
        for result in results:
            chunks.append({
                'id': result[0],
                'content': result[1],
                'document_id': result[2],
                'chunk_index': result[3],
                'metadata': json.loads(result[4]) if result[4] else {}
            })
        
        return chunks