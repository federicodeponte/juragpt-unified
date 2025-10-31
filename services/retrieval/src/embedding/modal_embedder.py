"""
ABOUTME: Modal.com GPU-accelerated embedding generation for massive speedup (15-30x faster).
ABOUTME: Uses NVIDIA A10G GPU with large batch sizes for fast embedding generation.
"""

import modal
from typing import List

# Create Modal app
app = modal.App("juragpt-embedder")

# Define GPU-accelerated image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "sentence-transformers==2.3.1",
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "numpy>=1.24.0",
    )
)

# GPU function for batch embedding
@app.function(
    image=image,
    gpu="A10G",  # NVIDIA A10G - $1.10/hour, excellent for embeddings
    timeout=600,  # 10 minutes per batch
    memory=16384,  # 16GB RAM
    container_idle_timeout=300,  # Keep warm for 5 minutes
)
def embed_batch_gpu(
    texts: List[str],
    model_name: str = "intfloat/multilingual-e5-large"
) -> List[List[float]]:
    """
    Embed batch of texts on GPU.

    Args:
        texts: List of text strings to embed
        model_name: SentenceTransformer model name

    Returns:
        List of embedding vectors (each is list of floats)
    """
    from sentence_transformers import SentenceTransformer
    import torch

    # Load model on GPU (cached after first run)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(model_name, device=device)

    # Encode with large batch size (GPU can handle much more than CPU)
    embeddings = model.encode(
        texts,
        batch_size=128,  # 16x larger than CPU (8)
        convert_to_numpy=True,
        normalize_embeddings=True,  # Important for cosine similarity
        show_progress_bar=False,
        device=device,
    )

    # Convert to list for JSON serialization
    return embeddings.tolist()


@app.local_entrypoint()
def test():
    """Test the GPU embedder with sample texts."""
    print("Testing Modal GPU Embedder...")

    # Test texts
    test_texts = [
        "Das Bürgerliche Gesetzbuch regelt das Privatrecht.",
        "Artikel 1 des Grundgesetzes schützt die Menschenwürde.",
        "§823 BGB regelt die Haftung für unerlaubte Handlungen.",
    ]

    print(f"\nEmbedding {len(test_texts)} test texts...")
    embeddings = embed_batch_gpu.remote(test_texts)

    print(f"\n✓ Successfully embedded {len(embeddings)} texts")
    print(f"✓ Embedding dimension: {len(embeddings[0])}")
    print(f"✓ First embedding sample: {embeddings[0][:5]}...")

    return embeddings
