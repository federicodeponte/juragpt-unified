"""
ABOUTME: Checkpoint manager for resumable ETL pipeline execution with data persistence.
ABOUTME: Implements atomic file operations and saves intermediate pipeline data for true resume capability.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.models.document import IngestionState, LegalDocument, DocumentChunk
from src.exceptions import (
    CheckpointSaveError,
    CheckpointLoadError,
    CheckpointCorruptedError,
)

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoint state and data persistence for resumable ETL pipelines.

    Directory structure per run:
        data/checkpoints/2025-10-28T22-42-23/
        ├── state.json           # Pipeline state metadata
        ├── documents.jsonl      # Fetched documents
        ├── normalized.jsonl     # Normalized documents
        └── chunks.jsonl         # Document chunks

    Features:
    - Atomic file writes using temp file + rename pattern
    - Full data persistence for true resume capability
    - Type-safe using TypedDict models
    - JSONL format for large datasets

    Usage:
        manager = CheckpointManager()

        # Save state and data
        manager.save_checkpoint(state)
        manager.save_documents(run_id, documents)

        # Resume from checkpoint
        state = manager.load_checkpoint(run_id)
        documents = manager.load_documents(run_id)
    """

    def __init__(self, checkpoint_dir: Path = Path("data/checkpoints")):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Root directory for all checkpoints
        """
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CheckpointManager initialized: {self.checkpoint_dir}")

    def _get_run_dir(self, run_id: str) -> Path:
        """Get checkpoint directory for specific run."""
        return self.checkpoint_dir / run_id

    def _get_state_path(self, run_id: str) -> Path:
        """Get state.json path for run."""
        return self._get_run_dir(run_id) / "state.json"

    def _get_documents_path(self, run_id: str) -> Path:
        """Get documents.jsonl path for run."""
        return self._get_run_dir(run_id) / "documents.jsonl"

    def _get_normalized_path(self, run_id: str) -> Path:
        """Get normalized.jsonl path for run."""
        return self._get_run_dir(run_id) / "normalized.jsonl"

    def _get_chunks_path(self, run_id: str) -> Path:
        """Get chunks.jsonl path for run."""
        return self._get_run_dir(run_id) / "chunks.jsonl"

    # ===== STATE MANAGEMENT =====

    def save_checkpoint(self, state: IngestionState) -> None:
        """
        Save checkpoint state atomically.

        Creates run directory if it doesn't exist and saves state.json
        using temp file + rename for atomicity.

        Args:
            state: Current ingestion state

        Raises:
            CheckpointSaveError: If save fails
        """
        run_id = state["run_id"]
        run_dir = self._get_run_dir(run_id)
        state_file = self._get_state_path(run_id)
        temp_file = state_file.with_suffix(".tmp")

        try:
            # Create run directory
            run_dir.mkdir(parents=True, exist_ok=True)

            # Update timestamp
            state["last_updated"] = datetime.now().isoformat()

            # Write to temp file
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.rename(state_file)

            logger.info(
                f"Checkpoint saved: {run_id} "
                f"(docs={state['documents_fetched']}, "
                f"chunks={state['chunks_created']}, "
                f"vectors={state['vectors_uploaded']})"
            )

        except (OSError, TypeError, ValueError) as e:
            raise CheckpointSaveError(str(state_file), reason=str(e)) from e
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

    def load_checkpoint(self, run_id: str) -> Optional[IngestionState]:
        """
        Load checkpoint state from disk.

        Args:
            run_id: Run identifier

        Returns:
            Checkpoint state or None if not found

        Raises:
            CheckpointLoadError: If file exists but cannot be read
            CheckpointCorruptedError: If JSON is invalid
        """
        state_file = self._get_state_path(run_id)

        if not state_file.exists():
            logger.info(f"No checkpoint found for run_id={run_id}")
            return None

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # Validate required fields
            required = ["run_id", "start_time", "status", "documents_fetched"]
            if not all(field in state for field in required):
                raise CheckpointCorruptedError(str(state_file))

            logger.info(f"Checkpoint loaded: {run_id} (status={state['status']})")
            return state

        except json.JSONDecodeError as e:
            raise CheckpointCorruptedError(str(state_file)) from e
        except OSError as e:
            raise CheckpointLoadError(str(state_file), reason=str(e)) from e

    # ===== DATA PERSISTENCE =====

    def save_documents(self, run_id: str, documents: List[LegalDocument]) -> None:
        """
        Save fetched documents to JSONL.

        Args:
            run_id: Run identifier
            documents: List of legal documents

        Raises:
            CheckpointSaveError: If save fails
        """
        self._save_jsonl(self._get_documents_path(run_id), documents, "documents")

    def load_documents(self, run_id: str) -> List[LegalDocument]:
        """
        Load fetched documents from JSONL.

        Args:
            run_id: Run identifier

        Returns:
            List of legal documents (empty if file doesn't exist)
        """
        return self._load_jsonl(self._get_documents_path(run_id), "documents")

    def save_normalized(self, run_id: str, normalized: List[LegalDocument]) -> None:
        """
        Save normalized documents to JSONL.

        Args:
            run_id: Run identifier
            normalized: List of normalized documents

        Raises:
            CheckpointSaveError: If save fails
        """
        self._save_jsonl(self._get_normalized_path(run_id), normalized, "normalized documents")

    def load_normalized(self, run_id: str) -> List[LegalDocument]:
        """
        Load normalized documents from JSONL.

        Args:
            run_id: Run identifier

        Returns:
            List of normalized documents (empty if file doesn't exist)
        """
        return self._load_jsonl(self._get_normalized_path(run_id), "normalized documents")

    def save_chunks(self, run_id: str, chunks: List[DocumentChunk]) -> None:
        """
        Save document chunks to JSONL.

        Args:
            run_id: Run identifier
            chunks: List of document chunks

        Raises:
            CheckpointSaveError: If save fails
        """
        self._save_jsonl(self._get_chunks_path(run_id), chunks, "chunks")

    def load_chunks(self, run_id: str) -> List[DocumentChunk]:
        """
        Load document chunks from JSONL.

        Args:
            run_id: Run identifier

        Returns:
            List of document chunks (empty if file doesn't exist)
        """
        return self._load_jsonl(self._get_chunks_path(run_id), "chunks")

    def append_chunks(self, run_id: str, chunks: List[DocumentChunk]) -> None:
        """
        Append chunks to existing chunks file (for batched processing).

        This method supports incremental saving during batched chunking,
        allowing checkpoints after each batch without loading all chunks
        into memory.

        Args:
            run_id: Run identifier
            chunks: List of document chunks to append

        Raises:
            CheckpointSaveError: If append fails
        """
        chunks_path = self._get_chunks_path(run_id)

        try:
            # Ensure parent directory exists
            chunks_path.parent.mkdir(parents=True, exist_ok=True)

            # Append to file
            with open(chunks_path, "a", encoding="utf-8") as f:
                for chunk in chunks:
                    f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

            logger.debug(f"Appended {len(chunks)} chunks to {chunks_path.name}")

        except (OSError, TypeError, ValueError) as e:
            raise CheckpointSaveError(str(chunks_path), reason=str(e)) from e

    # ===== INTERNAL HELPERS =====

    def _save_jsonl(self, file_path: Path, data: List[Dict[str, Any]], data_type: str) -> None:
        """
        Save data to JSONL file (one JSON object per line).

        Args:
            file_path: Output file path
            data: List of dictionaries to save
            data_type: Data type for logging (e.g., "documents", "chunks")

        Raises:
            CheckpointSaveError: If save fails
        """
        temp_file = file_path.with_suffix(".tmp")

        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file
            with open(temp_file, "w", encoding="utf-8") as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")

            # Atomic rename
            temp_file.rename(file_path)

            logger.info(f"Saved {len(data)} {data_type} to {file_path.name}")

        except (OSError, TypeError, ValueError) as e:
            raise CheckpointSaveError(str(file_path), reason=str(e)) from e
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

    def _load_jsonl(self, file_path: Path, data_type: str) -> List[Dict[str, Any]]:
        """
        Load data from JSONL file.

        Args:
            file_path: Input file path
            data_type: Data type for logging

        Returns:
            List of dictionaries (empty if file doesn't exist)
        """
        if not file_path.exists():
            logger.debug(f"No {data_type} file found: {file_path}")
            return []

        try:
            data = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data.append(json.loads(line))

            logger.info(f"Loaded {len(data)} {data_type} from {file_path.name}")
            return data

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Error loading {data_type}: {e}")
            return []

    # ===== CHECKPOINT MANAGEMENT =====

    def can_resume(self, run_id: str) -> bool:
        """
        Check if a run can be resumed.

        Args:
            run_id: Run identifier

        Returns:
            True if checkpoint exists with status "running" or "failed"
        """
        try:
            state = self.load_checkpoint(run_id)
            if not state:
                return False
            return state["status"] in ("running", "failed")
        except Exception as e:
            logger.warning(f"Error checking resume status for {run_id}: {e}")
            return False

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all available checkpoints.

        Returns:
            List of checkpoint info dictionaries
        """
        checkpoints = []

        for run_dir in sorted(self.checkpoint_dir.iterdir()):
            if not run_dir.is_dir():
                continue

            state_file = run_dir / "state.json"
            if not state_file.exists():
                continue

            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                checkpoints.append({
                    "run_id": state.get("run_id", "unknown"),
                    "status": state.get("status", "unknown"),
                    "start_time": state.get("start_time", "unknown"),
                    "last_updated": state.get("last_updated", "unknown"),
                    "documents_fetched": state.get("documents_fetched", 0),
                    "chunks_created": state.get("chunks_created", 0),
                    "vectors_uploaded": state.get("vectors_uploaded", 0),
                })
            except Exception as e:
                logger.warning(f"Error reading checkpoint {run_dir}: {e}")
                continue

        logger.info(f"Found {len(checkpoints)} checkpoints")
        return checkpoints

    def delete_checkpoint(self, run_id: str) -> bool:
        """
        Delete a checkpoint directory and all its files.

        Args:
            run_id: Run identifier

        Returns:
            True if deleted, False if didn't exist
        """
        run_dir = self._get_run_dir(run_id)

        if not run_dir.exists():
            logger.info(f"Checkpoint {run_id} does not exist")
            return False

        try:
            shutil.rmtree(run_dir)
            logger.info(f"Deleted checkpoint: {run_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting checkpoint {run_id}: {e}")
            return False

    def get_latest_checkpoint(self) -> Optional[IngestionState]:
        """
        Get the most recently updated checkpoint.

        Returns:
            Latest checkpoint state or None
        """
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None

        latest = max(checkpoints, key=lambda c: c["last_updated"])
        return self.load_checkpoint(latest["run_id"])

    def create_initial_state(self, run_id: Optional[str] = None) -> IngestionState:
        """
        Create initial checkpoint state for a new pipeline run.

        Args:
            run_id: Optional run identifier (defaults to timestamp)

        Returns:
            Initial IngestionState
        """
        if run_id is None:
            run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        now = datetime.now().isoformat()

        return {
            "run_id": run_id,
            "start_time": now,
            "last_updated": now,
            "status": "running",
            "documents_fetched": 0,
            "documents_normalized": 0,
            "chunks_created": 0,
            "vectors_uploaded": 0,
            "last_openlegal_case_date": None,
            "last_openlegal_law_date": None,
            "last_eurlex_doc_id": None,
            "error_count": 0,
            "last_error": None,
        }
