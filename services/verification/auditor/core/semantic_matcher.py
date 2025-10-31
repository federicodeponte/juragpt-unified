"""
ABOUTME: Semantic similarity matching using embeddings for verification
ABOUTME: Implements caching for performance and supports batch processing
"""

import hashlib
from typing import List, Dict, Any, Tuple, Optional
from functools import lru_cache
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util


class SemanticMatcher:
    """
    Matches sentences against source snippets using semantic embeddings.
    Implements caching for improved performance on repeated sources.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-large",
        device: str = "cpu",
        cache_enabled: bool = True,
        cache_size: int = 1000,
    ):
        """
        Initialize semantic matcher with embedding model.

        Args:
            model_name: Sentence transformer model name
            device: Device for computation ("cpu" or "cuda")
            cache_enabled: Whether to cache embeddings
            cache_enabled: Whether to cache embeddings
            cache_size: Maximum number of cached embeddings
        """
        self.model_name = model_name
        self.device = device
        self.cache_enabled = cache_enabled
        self.cache_size = cache_size

        # Lazy load model
        self._model: Optional[SentenceTransformer] = None

        # In-memory embedding cache
        self._embedding_cache: Dict[str, np.ndarray] = {}

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load sentence transformer model"""
        if self._model is None:
            print(f"Loading model: {self.model_name}...")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            print(f"Model loaded on {self.device}")
        return self._model

    def _hash_text(self, text: str) -> str:
        """Create hash of text for caching"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _get_cached_embedding(self, text: str) -> Optional[np.ndarray]:
        """Retrieve embedding from cache"""
        if not self.cache_enabled:
            return None

        text_hash = self._hash_text(text)
        return self._embedding_cache.get(text_hash)

    def _cache_embedding(self, text: str, embedding: np.ndarray) -> None:
        """Store embedding in cache"""
        if not self.cache_enabled:
            return

        # Simple LRU: remove oldest if cache full
        if len(self._embedding_cache) >= self.cache_size:
            # Remove first item (oldest in dict)
            first_key = next(iter(self._embedding_cache))
            del self._embedding_cache[first_key]

        text_hash = self._hash_text(text)
        self._embedding_cache[text_hash] = embedding

    def encode(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Encode single text to embedding.

        Args:
            text: Input text
            use_cache: Whether to use cached embedding if available

        Returns:
            Embedding vector (numpy array)
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_embedding(text)
            if cached is not None:
                return cached

        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)

        # Cache result
        if use_cache:
            self._cache_embedding(text, embedding)

        return embedding

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Encode multiple texts in batch.

        Args:
            texts: List of texts
            batch_size: Batch size for encoding

        Returns:
            2D array of embeddings (num_texts x embedding_dim)
        """
        embeddings = []

        for text in texts:
            # Check cache for each text
            cached = self._get_cached_embedding(text)
            if cached is not None:
                embeddings.append(cached)
            else:
                # Encode and cache
                emb = self.model.encode(text, convert_to_numpy=True)
                self._cache_embedding(text, emb)
                embeddings.append(emb)

        return np.array(embeddings)

    def compute_similarity(
        self,
        text1: str,
        text2: str,
        use_cache: bool = True,
    ) -> float:
        """
        Compute cosine similarity between two texts.

        Args:
            text1: First text
            text2: Second text
            use_cache: Whether to use embedding cache

        Returns:
            Similarity score (0-1)
        """
        emb1 = self.encode(text1, use_cache=use_cache)
        emb2 = self.encode(text2, use_cache=use_cache)

        # Cosine similarity
        similarity = util.cos_sim(emb1, emb2).item()

        return float(similarity)

    def find_best_match(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 1,
    ) -> List[Tuple[int, float]]:
        """
        Find best matching candidates for a query.

        Args:
            query: Query text
            candidates: List of candidate texts
            top_k: Number of top matches to return

        Returns:
            List of (index, score) tuples sorted by score descending
        """
        if not candidates:
            return []

        # Encode query
        query_emb = self.encode(query)

        # Encode all candidates (with caching)
        candidate_embs = self.encode_batch(candidates)

        # Compute similarities
        similarities = util.cos_sim(query_emb, candidate_embs)[0]

        # Get top-k
        top_results = torch.topk(similarities, k=min(top_k, len(candidates)))

        results = [
            (int(idx), float(score))
            for idx, score in zip(top_results.indices, top_results.values)
        ]

        return results

    def verify_sentence(
        self,
        sentence: str,
        sources: List[str],
        threshold: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Verify a single sentence against source snippets.

        Args:
            sentence: Sentence to verify
            sources: List of source text snippets
            threshold: Similarity threshold for verification

        Returns:
            Dict with:
                - verified: bool
                - max_score: highest similarity score
                - best_match_idx: index of best matching source
                - best_match_text: text of best matching source
                - all_scores: list of all scores
        """
        if not sources:
            return {
                "verified": False,
                "max_score": 0.0,
                "best_match_idx": None,
                "best_match_text": None,
                "all_scores": [],
            }

        # Find best match
        matches = self.find_best_match(sentence, sources, top_k=len(sources))

        best_idx, max_score = matches[0]
        verified = max_score >= threshold

        return {
            "verified": verified,
            "max_score": max_score,
            "best_match_idx": best_idx,
            "best_match_text": sources[best_idx],
            "all_scores": [score for _, score in matches],
        }

    def verify_answer(
        self,
        sentences: List[str],
        sources: List[str],
        sentence_threshold: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Verify all sentences in an answer against sources.

        Args:
            sentences: List of sentences from answer
            sources: List of source snippets
            sentence_threshold: Threshold for sentence-level verification

        Returns:
            Dict with:
                - verified_count: number of verified sentences
                - total_count: total sentences
                - verification_rate: ratio of verified sentences
                - sentences: list of verification results per sentence
                - overall_confidence: average of all max scores
        """
        if not sentences:
            return {
                "verified_count": 0,
                "total_count": 0,
                "verification_rate": 0.0,
                "sentences": [],
                "overall_confidence": 0.0,
            }

        sentence_results = []

        for sentence in sentences:
            result = self.verify_sentence(sentence, sources, sentence_threshold)
            result["sentence_text"] = sentence
            sentence_results.append(result)

        verified_count = sum(1 for r in sentence_results if r["verified"])
        total_count = len(sentences)

        # Calculate overall confidence as average of max scores
        overall_confidence = (
            sum(r["max_score"] for r in sentence_results) / total_count
            if total_count > 0
            else 0.0
        )

        return {
            "verified_count": verified_count,
            "total_count": total_count,
            "verification_rate": verified_count / total_count if total_count > 0 else 0.0,
            "sentences": sentence_results,
            "overall_confidence": overall_confidence,
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_enabled": self.cache_enabled,
            "cache_size": len(self._embedding_cache),
            "cache_limit": self.cache_size,
            "cache_usage_pct": (
                len(self._embedding_cache) / self.cache_size * 100
                if self.cache_size > 0
                else 0.0
            ),
        }

    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self._embedding_cache.clear()


def main() -> None:
    """Demo usage of semantic matcher"""
    print("🧠 Semantic Matcher Demo\n")

    matcher = SemanticMatcher(device="cpu", cache_enabled=True)

    # Test sentence
    sentence = "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht."

    # Source snippets
    sources = [
        "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt, ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.",
        "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten, sofern nicht ein anderes bestimmt ist.",
        "Durch den Kaufvertrag wird der Verkäufer verpflichtet, dem Käufer die Sache zu übergeben.",
    ]

    print("Sentence to verify:")
    print(f"  {sentence}\n")

    print("Sources:")
    for i, src in enumerate(sources):
        print(f"  [{i}] {src[:80]}...")

    print("\n" + "=" * 60 + "\n")

    # Verify
    result = matcher.verify_sentence(sentence, sources, threshold=0.75)

    print(f"✓ Verified: {result['verified']}")
    print(f"📊 Max Score: {result['max_score']:.3f}")
    print(f"🎯 Best Match: Source [{result['best_match_idx']}]")
    print(f"   {result['best_match_text'][:100]}...")
    print(f"\n📈 All Scores: {[f'{s:.3f}' for s in result['all_scores']]}")

    # Cache stats
    print("\n" + "=" * 60)
    stats = matcher.get_cache_stats()
    print(f"\n💾 Cache Stats:")
    print(f"   Enabled: {stats['cache_enabled']}")
    print(f"   Size: {stats['cache_size']}/{stats['cache_limit']}")
    print(f"   Usage: {stats['cache_usage_pct']:.1f}%")


if __name__ == "__main__":
    main()
