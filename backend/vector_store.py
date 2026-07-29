"""
Vector Store Service - ChromaDB management for RAG embeddings
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings

# ChromaDB storage directory
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# Collection name
COLLECTION_NAME = "lekhantra_documents"

# ChromaDB client singleton
_client = None


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Get or create the ChromaDB persistent client.
    Stores data in backend/chroma_db/ directory.
    """
    global _client
    if _client is None:
        print(f"[VECTOR STORE] Initializing ChromaDB at: {CHROMA_DB_DIR}")
        os.makedirs(CHROMA_DB_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=CHROMA_DB_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        print(f"[VECTOR STORE] ChromaDB initialized successfully")
    return _client


def get_collection():
    """
    Get the documents collection, creating it if necessary.
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
        print(f"[VECTOR STORE] Using existing collection: {COLLECTION_NAME}")
    except Exception:
        print(f"[VECTOR STORE] Creating new collection: {COLLECTION_NAME}")
        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Lekhantra RAG document chunks"}
        )
    return collection


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file for duplicate detection.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def check_document_exists(file_hash: str, user_id: str) -> Optional[str]:
    """
    Check if a document with the same hash already exists for this user.

    Returns:
        Document ID if exists, None otherwise
    """
    try:
        collection = get_collection()
        results = collection.get(
            where={"user_id": user_id},
            include=["metadatas"]
        )

        for i, metadata in enumerate(results.get("metadatas", [])):
            if metadata.get("file_hash") == file_hash:
                return results["ids"][i]
        return None
    except Exception as e:
        print(f"[VECTOR STORE] Error checking document exists: {e}")
        return None


def add_document_chunks(
    document_id: str,
    user_id: str,
    filename: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    file_hash: str
) -> bool:
    """
    Add document chunks to the vector store.

    Args:
        document_id: Unique document identifier
        user_id: User who owns the document
        filename: Original filename
        chunks: List of chunk dictionaries with text, page_number, chunk_index
        embeddings: List of embedding vectors
        file_hash: SHA256 hash of the original file

    Returns:
        True if successful, False otherwise
    """
    try:
        collection = get_collection()

        # Prepare IDs, metadatas, and documents
        ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "filename": filename,
                "file_hash": file_hash,
                "page_number": chunk.get("page_number", 1),
                "chunk_index": chunk.get("chunk_index", i),
                "total_chunks": len(chunks)
            }
            for i, chunk in enumerate(chunks)
        ]
        documents = [chunk["text"] for chunk in chunks]

        # Add to ChromaDB
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

        print(f"[VECTOR STORE] Added {len(chunks)} chunks for document: {document_id}")
        return True

    except Exception as e:
        print(f"[VECTOR STORE] Error adding document chunks: {e}")
        return False


def similarity_search(
    query_embedding: List[float],
    user_id: str,
    top_k: int = 5,
    document_ids: Optional[List[str]] = None,
    min_similarity: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Perform similarity search on document chunks.

    Args:
        query_embedding: Embedding of the query question
        user_id: User performing the search
        top_k: Number of results to return
        document_ids: Optional list of document IDs to filter (for conversation-specific docs)
        min_similarity: Minimum similarity score (0-1)

    Returns:
        List of matching chunks with their metadata and similarity scores
    """
    try:
        collection = get_collection()

        # Build where clause for filtering
        where_clause = {"user_id": user_id}
        if document_ids:
            where_clause["document_id"] = {"$in": document_ids}

        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )

        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            doc_id = results["ids"][0][i]
            distance = results["distances"][0][i]
            # Convert distance to similarity score (ChromaDB uses L2 distance)
            similarity = 1 / (1 + distance)

            if similarity >= min_similarity:
                formatted_results.append({
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity": round(similarity, 4),
                    "distance": round(distance, 4)
                })

        print(f"[VECTOR STORE] Found {len(formatted_results)} relevant chunks")
        return formatted_results

    except Exception as e:
        print(f"[VECTOR STORE] Error performing similarity search: {e}")
        return []


def get_document_chunks(document_id: str, user_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a specific document.

    Args:
        document_id: Document to retrieve chunks for
        user_id: User who owns the document

    Returns:
        List of chunks with metadata
    """
    try:
        collection = get_collection()
        results = collection.get(
            where={
                "document_id": document_id,
                "user_id": user_id
            },
            include=["documents", "metadatas"]
        )

        chunks = []
        for i in range(len(results["ids"])):
            chunks.append({
                "id": results["ids"][i],
                "text": results["documents"][i],
                "metadata": results["metadatas"][i]
            })

        return chunks

    except Exception as e:
        print(f"[VECTOR STORE] Error getting document chunks: {e}")
        return []


def delete_document_chunks(document_id: str, user_id: str) -> bool:
    """
    Delete all chunks for a specific document.

    Args:
        document_id: Document to delete chunks for
        user_id: User who owns the document

    Returns:
        True if successful, False otherwise
    """
    try:
        collection = get_collection()
        collection.delete(
            where={
                "document_id": document_id,
                "user_id": user_id
            }
        )
        print(f"[VECTOR STORE] Deleted chunks for document: {document_id}")
        return True

    except Exception as e:
        print(f"[VECTOR_STORE] Error deleting document chunks: {e}")
        return False


def get_user_documents(user_id: str) -> List[Dict[str, Any]]:
    """
    Get list of all documents for a user with chunk counts.

    Args:
        user_id: User to get documents for

    Returns:
        List of document info dictionaries
    """
    try:
        collection = get_collection()
        results = collection.get(
            where={"user_id": user_id},
            include=["metadatas"]
        )

        # Deduplicate by document_id
        documents = {}
        for i, metadata in enumerate(results.get("metadatas", [])):
            doc_id = metadata.get("document_id")
            if doc_id and doc_id not in documents:
                documents[doc_id] = {
                    "document_id": doc_id,
                    "filename": metadata.get("filename"),
                    "file_hash": metadata.get("file_hash"),
                    "chunk_count": 0
                }
            if doc_id:
                documents[doc_id]["chunk_count"] += 1

        return list(documents.values())

    except Exception as e:
        print(f"[VECTOR_STORE] Error getting user documents: {e}")
        return []


def get_collection_stats() -> Dict[str, int]:
    """
    Get statistics about the vector store.

    Returns:
        Dictionary with collection statistics
    """
    try:
        collection = get_collection()
        count = collection.count()
        return {
            "total_chunks": count,
            "collection_name": COLLECTION_NAME,
            "storage_dir": CHROMA_DB_DIR
        }
    except Exception as e:
        print(f"[VECTOR STORE] Error getting stats: {e}")
        return {"error": str(e)}
