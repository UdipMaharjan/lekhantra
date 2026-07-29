"""
PDF Service - Enhanced PDF processing with text extraction, chunking, and page tracking
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Chunking configuration
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters for context continuity
MIN_CHUNK_LENGTH = 50  # Minimum characters to keep a chunk
MAX_CHUNK_LENGTH = 1000  # Maximum characters per chunk


@dataclass
class ExtractedPage:
    """Represents text extracted from a single page."""
    page_number: int
    text: str


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""
    text: str
    page_number: int
    chunk_index: int
    start_char: int
    end_char: int


class PDFProcessingError(Exception):
    """Custom exception for PDF processing errors."""
    pass


class EmptyPDFError(PDFProcessingError):
    """Raised when PDF contains no extractable text."""
    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when PDF cannot be read."""
    pass


def extract_text_with_pages(file_path: str) -> List[ExtractedPage]:
    """
    Extract text from PDF with page number tracking.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of ExtractedPage objects containing text and page numbers

    Raises:
        CorruptedPDFError: If PDF cannot be opened
        EmptyPDFError: If PDF has no extractable text
    """
    pages = []

    try:
        pdf_document = fitz.open(file_path)

        if pdf_document.page_count == 0:
            pdf_document.close()
            raise EmptyPDFError("PDF has no pages")

        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            text = page.get_text()

            pages.append(ExtractedPage(
                page_number=page_num + 1,  # 1-indexed for humans
                text=text.strip()
            ))

        pdf_document.close()

        # Check if any text was extracted
        total_chars = sum(len(p.text) for p in pages)
        if total_chars < 10:
            raise EmptyPDFError(
                "PDF appears to be scanned or image-based with no extractable text"
            )

        print(f"[PDF SERVICE] Extracted {len(pages)} pages, {total_chars} total characters")
        return pages

    except EmptyPDFError:
        raise
    except Exception as e:
        raise CorruptedPDFError(f"Cannot read PDF: {str(e)}")


def clean_text(text: str) -> str:
    """
    Clean extracted text for better chunking.

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove very short lines that are likely artifacts
    lines = text.split('. ')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if len(line) > 2:  # Keep meaningful content
            cleaned_lines.append(line)

    return '. '.join(cleaned_lines)


def split_into_chunks(
    pages: List[ExtractedPage],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    min_chunk_length: int = MIN_CHUNK_LENGTH
) -> List[Chunk]:
    """
    Split extracted text into chunks using RecursiveCharacterTextSplitter.

    Args:
        pages: List of ExtractedPage objects
        chunk_size: Target size for each chunk in characters
        chunk_overlap: Overlap between chunks for context continuity
        min_chunk_length: Minimum length to keep a chunk

    Returns:
        List of Chunk objects with metadata
    """
    # Create text splitter with specified parameters
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=False
    )

    all_chunks = []

    for page in pages:
        if not page.text or len(page.text.strip()) < min_chunk_length:
            continue

        # Clean the text
        cleaned_text = clean_text(page.text)

        # Split the page text into chunks
        texts = text_splitter.split_text(cleaned_text)

        for idx, chunk_text in enumerate(texts):
            # Skip very short chunks
            if len(chunk_text.strip()) < min_chunk_length:
                continue

            # Track character positions
            start_char = sum(len(p.text) for p in pages[:page.page_number - 1])
            end_char = start_char + len(chunk_text)

            all_chunks.append(Chunk(
                text=chunk_text.strip(),
                page_number=page.page_number,
                chunk_index=idx,
                start_char=start_char,
                end_char=end_char
            ))

    print(f"[PDF SERVICE] Created {len(all_chunks)} chunks from {len(pages)} pages")
    return all_chunks


def process_pdf(file_path: str) -> Tuple[str, List[Chunk]]:
    """
    Complete PDF processing pipeline: extract text and create chunks.

    Args:
        file_path: Path to the PDF file

    Returns:
        Tuple of (full_text, chunks)

    Raises:
        PDFProcessingError: If processing fails
    """
    # Extract text with page tracking
    pages = extract_text_with_pages(file_path)

    # Combine all text for legacy compatibility
    full_text = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)

    # Create chunks
    chunks = split_into_chunks(pages)

    if not chunks:
        raise EmptyPDFError("No valid content chunks could be created from the PDF")

    return full_text, chunks


def get_page_count(file_path: str) -> int:
    """
    Get the number of pages in a PDF.

    Args:
        file_path: Path to the PDF file

    Returns:
        Number of pages
    """
    try:
        pdf_document = fitz.open(file_path)
        count = pdf_document.page_count
        pdf_document.close()
        return count
    except Exception:
        return 0


def get_text_preview(text: str, max_chars: int = 500) -> str:
    """
    Get a preview of text content.

    Args:
        text: Full text
        max_chars: Maximum characters to return

    Returns:
        Truncated text preview
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


# Legacy function for backward compatibility
def extract_text_from_pdf_legacy(file_path: str) -> str:
    """
    Legacy function to extract all text from PDF (no page tracking).
    Used for backward compatibility with existing endpoints.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text
    """
    pages = extract_text_with_pages(file_path)
    return "\n\n".join(p.text for p in pages)
