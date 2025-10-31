"""
ABOUTME: Embedding generation for legal text using multilingual-e5-large.
ABOUTME: Handles batched encoding with GPU support and progress tracking.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegalTextEmbedder:
    """Embedder for legal text using multilingual-e5-large."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        """
        Initialize embedder.

        Args:
            model_name: Embedding model name (defaults to env or multilingual-e5-large)
            device: Device to use (defaults to env or auto-detect)
            batch_size: Batch size for encoding (defaults to env or 32)
        """
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "intfloat/multilingual-e5-large"
        )
        self.batch_size = batch_size or int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

        # Determine device
        if device is None:
            device = os.getenv("EMBEDDING_DEVICE", "auto")

        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Loading embedding model: {self.model_name}")
        logger.info(f"Using device: {self.device}")

        # Load model
        try:
            self.model = SentenceTransformer(self.model_name, device=self.device)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def encode_texts(
        self, texts: List[str], show_progress: bool = True
    ) -> List[List[float]]:
        """
        Encode texts into embeddings.

        Args:
            texts: List of text strings
            show_progress: Show progress bar

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.info(f"Encoding {len(texts)} texts (batch_size={self.batch_size})...")

        try:
            # Encode with progress bar
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=True,  # Normalize for cosine similarity
            )

            # Convert to list of lists
            embeddings_list = embeddings.tolist()

            logger.info(f"Encoded {len(embeddings_list)} texts")
            return embeddings_list

        except Exception as e:
            logger.error(f"Error encoding texts: {e}")
            raise

    def encode_query(self, query: str) -> List[float]:
        """
        Encode a single query text.

        Args:
            query: Query string

        Returns:
            Query embedding vector
        """
        # For e5 models, prepend "query: " for better retrieval
        if "e5" in self.model_name.lower():
            query = f"query: {query}"

        embedding = self.model.encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def encode_document(self, document: str) -> List[float]:
        """
        Encode a single document text.

        Args:
            document: Document string

        Returns:
            Document embedding vector
        """
        # For e5 models, prepend "passage: " for better retrieval
        if "e5" in self.model_name.lower():
            document = f"passage: {document}"

        embedding = self.model.encode(
            document,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def encode_chunks(
        self, chunks: List[Dict[str, Any]], text_field: str = "text"
    ) -> List[List[float]]:
        """
        Encode chunks from document dictionaries.

        Args:
            chunks: List of chunk dictionaries
            text_field: Field name containing text to embed

        Returns:
            List of embedding vectors
        """
        # Extract texts
        texts = [chunk.get(text_field, "") for chunk in chunks]

        # Filter empty texts
        valid_indices = [i for i, text in enumerate(texts) if text.strip()]
        valid_texts = [texts[i] for i in valid_indices]

        if len(valid_texts) < len(texts):
            logger.warning(
                f"Filtered out {len(texts) - len(valid_texts)} chunks with empty text"
            )

        # Prepend "passage: " for e5 models
        if "e5" in self.model_name.lower():
            valid_texts = [f"passage: {text}" for text in valid_texts]

        # Encode
        embeddings = self.encode_texts(valid_texts)

        # Create full embeddings list with None for invalid indices
        full_embeddings = [None] * len(texts)
        for idx, emb_idx in enumerate(valid_indices):
            full_embeddings[emb_idx] = embeddings[idx]

        # Filter out None values and return
        return [emb for emb in full_embeddings if emb is not None]

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.

        Returns:
            Model information dictionary
        """
        return {
            "model_name": self.model_name,
            "embedding_dim": self.embedding_dim,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_seq_length": self.model.max_seq_length,
        }


def main():
    """Test embedder functionality."""
    # Initialize embedder
    embedder = LegalTextEmbedder(batch_size=8)

    # Print model info
    info = embedder.get_model_info()
    print("=== Model Information ===")
    for key, value in info.items():
        print(f"{key}: {value}")
    print()

    # Test texts
    test_texts = [
        "§ 823 BGB regelt die Schadensersatzpflicht bei unerlaubten Handlungen.",
        "Das Bundesverfassungsgericht hat in seinem Urteil entschieden...",
        "Die Voraussetzungen für eine ordentliche Kündigung sind...",
    ]

    # Encode documents
    print("=== Encoding Documents ===")
    doc_embeddings = [embedder.encode_document(text) for text in test_texts]
    print(f"Encoded {len(doc_embeddings)} documents")
    print(f"Embedding shape: {len(doc_embeddings[0])} dimensions")
    print(f"Sample embedding (first 5 values): {doc_embeddings[0][:5]}")
    print()

    # Encode query
    print("=== Encoding Query ===")
    query = "Wann haftet jemand nach BGB?"
    query_embedding = embedder.encode_query(query)
    print(f"Query: {query}")
    print(f"Embedding shape: {len(query_embedding)} dimensions")
    print(f"Sample embedding (first 5 values): {query_embedding[:5]}")


if __name__ == "__main__":
    main()
