"""
Embedding Service - Generates embeddings using sentence-transformers/all-MiniLM-L6-v2
"""

import gc
from typing import Any, List, Optional

# Model name as specified
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Embedding dimension for all-MiniLM-L6-v2 (384 dimensions)
EMBEDDING_DIM = 384

# Singleton model instance
_model = None


def get_embedding_model():
    """
    Get or create the singleton embedding model instance.
    Uses sentence-transformers/all-MiniLM-L6-v2 as specified.
    """
    global _model
    if _model is None:
        # Importing sentence-transformers also imports its ML runtime.  Keep that
        # cost on the first embedding request instead of application startup.
        from sentence_transformers import SentenceTransformer

        print(f"[EMBEDDING] Loading model: {EMBEDDING_MODEL_NAME}")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"[EMBEDDING] Model loaded successfully")
    return _model


def generate_embedding(text: str) -> Optional[Any]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed

    Returns:
        Numpy array of embedding or None if failed
    """
    try:
        model = get_embedding_model()
        embedding = model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embedding
    except Exception as e:
        print(f"[EMBEDDING] Error generating embedding: {e}")
        return None


def generate_embeddings(texts: List[str], show_progress: bool = False) -> List[Any]:
    """
    Generate embeddings for multiple texts.

    Args:
        texts: List of texts to embed
        show_progress: Whether to show progress bar

    Returns:
        List of numpy arrays containing embeddings
    """
    if not texts:
        return []

    try:
        # Kept for compatibility with existing callers; progress is always off
        # to avoid retaining renderer state during uploads.
        _ = show_progress
        model = get_embedding_model()
        embeddings = []
        for text in texts:
            embedding = model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            # Keep one embedding per item without creating a second list copy.
            embeddings.append(embedding)
            del embedding
            gc.collect()
        return embeddings
    except Exception as e:
        print(f"[EMBEDDING] Error generating embeddings: {e}")
        return []


def get_embedding_dimension() -> int:
    """Return the embedding dimension for the model."""
    return EMBEDDING_DIM
