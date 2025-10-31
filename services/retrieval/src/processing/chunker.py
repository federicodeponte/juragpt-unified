"""
ABOUTME: Text chunking utilities for legal documents.
ABOUTME: Splits documents into semantically coherent chunks for embedding and retrieval.
"""

import os
import logging
import json
from typing import List, Dict, Any, Generator, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextChunker:
    """Chunks legal documents into optimal sizes for embedding."""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        output_dir: str = None,
    ):
        """
        Initialize text chunker.

        Args:
            chunk_size: Target chunk size in characters (defaults to env or 800)
            chunk_overlap: Overlap between chunks (defaults to env or 100)
            output_dir: Directory to save processed chunks
        """
        self.chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "800"))
        self.chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "100"))
        self.output_dir = Path(output_dir or "data/processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Legal document section markers
        self.section_markers = [
            r"§\s*\d+",  # § 823
            r"Art\.\s*\d+",  # Art. 1
            r"Absatz\s*\d+",  # Absatz 1
            r"Abs\.\s*\d+",  # Abs. 1
            r"\(\d+\)",  # (1)
        ]

    def chunk_text(self, text: str, preserve_paragraphs: bool = True) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: Text to chunk
            preserve_paragraphs: Try to keep paragraphs intact

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # If text is shorter than chunk size, return as-is
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []

        if preserve_paragraphs:
            # Split by paragraphs first
            paragraphs = text.split("\n\n")
            chunks = self._chunk_paragraphs(paragraphs)
        else:
            # Simple sliding window
            chunks = self._sliding_window_chunk(text)

        return chunks

    def _chunk_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """
        Chunk text while preserving paragraph boundaries.

        Args:
            paragraphs: List of paragraphs

        Returns:
            List of chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # If single paragraph exceeds chunk size, split it
            if para_size > self.chunk_size:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Split long paragraph
                sub_chunks = self._sliding_window_chunk(para)
                chunks.extend(sub_chunks)
                continue

            # Check if adding this paragraph exceeds chunk size
            if current_size + para_size + 2 > self.chunk_size:  # +2 for "\n\n"
                # Save current chunk
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Keep last paragraph for overlap
                    current_chunk = [current_chunk[-1], para]
                    current_size = len(current_chunk[-2]) + para_size + 2
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                # Add to current chunk
                current_chunk.append(para)
                current_size += para_size + 2

        # Add final chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _sliding_window_chunk(self, text: str) -> List[str]:
        """
        Simple sliding window chunking with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of chunks
        """
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self.chunk_size

            # Try to break at sentence or word boundary
            if end < text_len:
                # Look for sentence end
                break_point = self._find_break_point(text, start, end)
                if break_point > start:
                    end = break_point

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start with overlap
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end

        return chunks

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find optimal break point near target position.

        Args:
            text: Full text
            start: Start position
            end: Target end position

        Returns:
            Optimal break position
        """
        # Look for sentence ending within last 20% of chunk
        search_start = end - int(self.chunk_size * 0.2)
        search_region = text[search_start:end]

        # Sentence endings
        for delimiter in [".\n", ". ", ".\n\n", "!", "?"]:
            pos = search_region.rfind(delimiter)
            if pos != -1:
                return search_start + pos + len(delimiter)

        # Fall back to word boundary
        last_space = text[:end].rfind(" ")
        if last_space > start:
            return last_space + 1

        # No good break point found
        return end

    def chunk_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk a document and create chunk dictionaries.

        Args:
            doc: Document dictionary with 'text' field

        Returns:
            List of chunk dictionaries with metadata
        """
        text = doc.get("text", "")
        chunks_text = self.chunk_text(text)

        chunk_docs = []
        for idx, chunk_text in enumerate(chunks_text):
            chunk_doc = {
                "chunk_id": f"{doc.get('doc_id', 'unknown')}_chunk_{idx}",
                "text": chunk_text,
                "chunk_index": idx,
                "total_chunks": len(chunks_text),
                # Inherit metadata from parent document
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "type": doc.get("type"),
                "jurisdiction": doc.get("jurisdiction"),
                "law": doc.get("law"),
                "court": doc.get("court"),
                "section": doc.get("section"),
                "date": doc.get("date"),
                "case_id": doc.get("case_id"),
            }
            chunk_docs.append(chunk_doc)

        return chunk_docs

    def chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk multiple documents.

        Args:
            documents: List of document dictionaries

        Returns:
            List of all chunk dictionaries

        Note:
            For large datasets (>5000 documents), use chunk_documents_batched()
            to avoid memory issues.
        """
        if len(documents) > 5000:
            logger.warning(
                f"Processing {len(documents)} documents at once may cause memory issues. "
                "Consider using chunk_documents_batched() instead."
            )

        logger.info(f"Chunking {len(documents)} documents (chunk_size={self.chunk_size})...")

        all_chunks = []
        for doc in documents:
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)

        logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
        if len(documents) > 0:
            logger.info(f"Average chunks per document: {len(all_chunks) / len(documents):.1f}")

        return all_chunks

    def chunk_documents_batched(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 1000,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Chunk documents in batches to avoid memory issues.

        This is a production-grade streaming approach that processes documents
        in configurable batches, yielding chunks incrementally rather than
        accumulating everything in memory.

        Benefits:
        - Memory efficient: O(batch_size) instead of O(total_documents)
        - Progress tracking: Logs after each batch
        - Fault tolerant: Can checkpoint after each batch
        - Scalable: Works with millions of documents

        Args:
            documents: Full list of document dictionaries
            batch_size: Number of documents to process per batch

        Yields:
            Batches of chunk dictionaries

        Example:
            >>> chunker = TextChunker()
            >>> for chunk_batch in chunker.chunk_documents_batched(docs, batch_size=1000):
            ...     # Process batch (e.g., save, embed, etc.)
            ...     save_chunks(chunk_batch)
        """
        total_docs = len(documents)
        total_batches = (total_docs + batch_size - 1) // batch_size  # Ceiling division

        logger.info(
            f"Chunking {total_docs} documents in {total_batches} batches "
            f"(batch_size={batch_size}, chunk_size={self.chunk_size})"
        )

        total_chunks_created = 0

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_docs)
            batch_docs = documents[start_idx:end_idx]

            # Chunk this batch
            batch_chunks = []
            for doc in batch_docs:
                chunks = self.chunk_document(doc)
                batch_chunks.extend(chunks)

            total_chunks_created += len(batch_chunks)

            # Log progress
            logger.info(
                f"Batch {batch_num + 1}/{total_batches}: "
                f"Processed docs {start_idx + 1}-{end_idx}/{total_docs}, "
                f"created {len(batch_chunks)} chunks "
                f"(total: {total_chunks_created} chunks)"
            )

            yield batch_chunks

        # Final summary
        logger.info(
            f"Chunking complete: {total_docs} documents → "
            f"{total_chunks_created} chunks "
            f"(avg: {total_chunks_created / total_docs:.1f} chunks/doc)"
        )

    def save_chunks(self, chunks: List[Dict[str, Any]], filename: str = "chunks.jsonl"):
        """
        Save chunks to JSONL file.

        Args:
            chunks: List of chunk dictionaries
            filename: Output filename
        """
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(chunks)} chunks to {output_path}")

    def load_chunks(self, filename: str = "chunks.jsonl") -> List[Dict[str, Any]]:
        """
        Load chunks from JSONL file.

        Args:
            filename: Input filename

        Returns:
            List of chunk dictionaries
        """
        input_path = self.output_dir / filename

        if not input_path.exists():
            logger.warning(f"File not found: {input_path}")
            return []

        chunks = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))

        logger.info(f"Loaded {len(chunks)} chunks from {input_path}")
        return chunks


def main():
    """Test chunker functionality."""
    chunker = TextChunker(chunk_size=200, chunk_overlap=50)

    # Test text
    test_text = """
    § 823 Schadensersatzpflicht

    (1) Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit,
    die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt,
    ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.

    (2) Die gleiche Verpflichtung trifft denjenigen, welcher gegen ein den Schutz
    eines anderen bezweckendes Gesetz verstößt. Ist nach dem Inhalt des Gesetzes
    ein Verstoß gegen dieses auch ohne Verschulden möglich, so tritt die
    Ersatzpflicht nur im Falle des Verschuldens ein.
    """

    # Create test document
    test_doc = {
        "doc_id": "BGB-823",
        "title": "§ 823 BGB - Schadensersatzpflicht",
        "text": test_text,
        "type": "statute",
        "law": "BGB",
    }

    # Chunk document
    chunks = chunker.chunk_document(test_doc)

    print(f"=== Chunking Test ===")
    print(f"Original text length: {len(test_text)} characters")
    print(f"Number of chunks: {len(chunks)}\n")

    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i} ({len(chunk['text'])} chars):")
        print(chunk["text"][:100] + "...")
        print()


if __name__ == "__main__":
    main()
