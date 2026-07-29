"""
RAG Service - Retrieval-Augmented Generation pipeline
"""

import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from embedding_service import generate_embedding, generate_embeddings
from vector_store import (
    add_document_chunks,
    similarity_search,
    check_document_exists,
    compute_file_hash,
    delete_document_chunks
)
from pdf_service import process_pdf, get_page_count, PDFProcessingError
from ai_utils import generate_ai_response

# RAG configuration
DEFAULT_TOP_K = 5  # Number of chunks to retrieve
MIN_SIMILARITY = 0.3  # Minimum similarity score
MAX_CONTEXT_CHARS = 10000  # Maximum characters for context


@dataclass
class SourceReference:
    """Represents a source reference for an answer."""
    text: str
    page_number: int
    chunk_id: str
    filename: str
    similarity: float


@dataclass
class RAGResponse:
    """Response from RAG pipeline."""
    answer: str
    sources: List[SourceReference]
    context_used: str


def process_and_index_document(
    file_path: str,
    user_id: str,
    filename: str
) -> Dict[str, Any]:
    """
    Process a PDF document and index it in the vector store.

    Args:
        file_path: Path to the uploaded PDF
        user_id: ID of the user uploading the document
        filename: Original filename

    Returns:
        Dictionary with processing results
    """
    document_id = str(uuid.uuid4())

    try:
        # Compute file hash for duplicate detection
        file_hash = compute_file_hash(file_path)
        print(f"[RAG] File hash: {file_hash[:16]}...")

        # Check for duplicates
        existing_doc = check_document_exists(file_hash, user_id)
        if existing_doc:
            print(f"[RAG] Document already exists: {existing_doc}")
            return {
                "status": "exists",
                "document_id": existing_doc,
                "message": "Document already uploaded",
                "is_duplicate": True
            }

        # Process PDF (extract text and create chunks)
        full_text, chunks = process_pdf(file_path)
        print(f"[RAG] Processed {len(chunks)} chunks from PDF")

        # Generate embeddings for all chunks
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = generate_embeddings(chunk_texts, show_progress=True)

        if not embeddings or len(embeddings) != len(chunks):
            raise Exception("Failed to generate embeddings for chunks")

        # Prepare chunk data for vector store
        chunk_data = [
            {
                "text": chunk.text,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index
            }
            for chunk in chunks
        ]

        # Add to vector store
        success = add_document_chunks(
            document_id=document_id,
            user_id=user_id,
            filename=filename,
            chunks=chunk_data,
            embeddings=embeddings,
            file_hash=file_hash
        )

        if not success:
            raise Exception("Failed to store document chunks")

        # Get page count
        page_count = get_page_count(file_path)

        return {
            "status": "success",
            "document_id": document_id,
            "filename": filename,
            "page_count": page_count,
            "chunk_count": len(chunks),
            "total_characters": len(full_text),
            "is_duplicate": False
        }

    except PDFProcessingError as e:
        return {
            "status": "error",
            "error_type": "processing_error",
            "message": str(e)
        }
    except Exception as e:
        print(f"[RAG] Error processing document: {e}")
        return {
            "status": "error",
            "error_type": "unknown",
            "message": str(e)
        }


def retrieve_relevant_chunks(
    question: str,
    user_id: str,
    top_k: int = DEFAULT_TOP_K,
    document_ids: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], List[SourceReference]]:
    """
    Retrieve relevant chunks for a question using semantic search.

    Args:
        question: User's question
        user_id: ID of the user
        top_k: Number of chunks to retrieve
        document_ids: Optional filter for specific documents

    Returns:
        Tuple of (chunks, source_references)
    """
    # Generate embedding for the question
    query_embedding = generate_embedding(question)

    if query_embedding is None:
        print("[RAG] Failed to generate query embedding")
        return [], []

    # Convert to list if numpy array
    if hasattr(query_embedding, 'tolist'):
        query_embedding = query_embedding.tolist()

    # Perform similarity search
    results = similarity_search(
        query_embedding=query_embedding,
        user_id=user_id,
        top_k=top_k,
        document_ids=document_ids,
        min_similarity=MIN_SIMILARITY
    )

    # Build source references
    sources = []
    for result in results:
        sources.append(SourceReference(
            text=result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"],
            page_number=result["metadata"].get("page_number", 1),
            chunk_id=result["id"],
            filename=result["metadata"].get("filename", "unknown"),
            similarity=result["similarity"]
        ))

    return results, sources


def build_context(chunks: List[Dict[str, Any]], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Build context string from retrieved chunks.

    Args:
        chunks: Retrieved chunks with text and metadata
        max_chars: Maximum characters for context

    Returns:
        Context string for the LLM
    """
    context_parts = []
    total_chars = 0

    for chunk in chunks:
        chunk_text = chunk["text"]
        page_num = chunk["metadata"].get("page_number", "?")

        # Format chunk with page reference
        formatted_chunk = f"[Page {page_num}]: {chunk_text}"

        # Check if adding this chunk would exceed limit
        if total_chars + len(formatted_chunk) > max_chars:
            # If we haven't added anything yet, add at least one chunk truncated
            if not context_parts:
                context_parts.append(formatted_chunk[:max_chars - 50] + "... (truncated)")
            break

        context_parts.append(formatted_chunk)
        total_chars += len(formatted_chunk)

    return "\n\n---\n\n".join(context_parts)


def generate_rag_answer(
    question: str,
    user_id: str,
    document_ids: Optional[List[str]] = None
) -> RAGResponse:
    """
    Generate an answer using RAG pipeline.

    Args:
        question: User's question
        user_id: ID of the user
        document_ids: Optional list of document IDs to search

    Returns:
        RAGResponse with answer and source references
    """
    # Step 1: Retrieve relevant chunks
    chunks, sources = retrieve_relevant_chunks(
        question=question,
        user_id=user_id,
        top_k=DEFAULT_TOP_K,
        document_ids=document_ids
    )

    if not chunks:
        return RAGResponse(
            answer="I couldn't find any relevant information in the uploaded documents to answer your question. Please try rephrasing or upload additional documents.",
            sources=[],
            context_used=""
        )

    # Step 2: Build context from chunks
    context = build_context(chunks)

    # Step 3: Generate answer with context
    prompt = f"""You are Lekhantra, an AI study assistant. Answer the user's question using ONLY the provided context from the document.

Rules:
- Use only the information from the provided context
- If the answer is in the context, explain it clearly and thoroughly
- If the answer is not in the context, say: "I could not find this information in the uploaded documents."
- Be specific and cite which page(s) the information comes from when relevant
- Keep the answer student-friendly and well-structured

Context from documents:
{context}

User question: {question}

Answer:"""

    answer = generate_ai_response(prompt)

    return RAGResponse(
        answer=answer,
        sources=sources,
        context_used=context
    )


def delete_document(document_id: str, user_id: str) -> bool:
    """
    Delete a document and its embeddings.

    Args:
        document_id: Document to delete
        user_id: User who owns the document

    Returns:
        True if successful
    """
    return delete_document_chunks(document_id, user_id)
