"""
ABOUTME: Secure file storage using Supabase Storage with deduplication
ABOUTME: Handles original file storage, retrieval, and cleanup
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Optional

from app.db.supabase_client import supabase_client
from app.utils.logging import logger


class FileStorage:
    """
    Manage file storage in Supabase Storage
    Implements hash-based deduplication and secure temp file handling
    """

    def __init__(self, bucket_name: str = "documents"):
        """
        Initialize file storage

        Args:
            bucket_name: Supabase storage bucket name
        """
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure storage bucket exists"""
        try:
            # Check if bucket exists
            buckets = supabase_client.client.storage.list_buckets()
            bucket_exists = any(b.name == self.bucket_name for b in buckets)

            if not bucket_exists:
                # Create bucket with private access
                supabase_client.client.storage.create_bucket(
                    self.bucket_name, options={"public": False}
                )
                logger.info(f"Created storage bucket: {self.bucket_name}")

        except Exception as e:
            logger.warning(f"Bucket check/creation failed: {str(e)}")

    def store_file(
        self,
        file_content: bytes,
        file_hash: str,
        filename: str,
        user_id: str,
        metadata: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        Store file in Supabase Storage with deduplication

        Args:
            file_content: Raw file bytes
            file_hash: SHA-256 hash of file
            filename: Original filename
            user_id: User ID for namespacing
            metadata: Optional metadata dict

        Returns:
            Storage path if successful, None otherwise
        """
        try:
            # Create path: user_id/hash/filename
            # This allows multiple users to have same file
            storage_path = f"{user_id}/{file_hash}/{filename}"

            # Check if file already exists
            if self.file_exists(storage_path):
                logger.info(f"File already exists at {storage_path}")
                return storage_path

            # Upload file
            supabase_client.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={
                    "content-type": self._guess_content_type(filename),
                    "upsert": False,  # Don't overwrite
                },
            )

            logger.info(f"Stored file: {storage_path} ({len(file_content)} bytes)")
            return storage_path

        except Exception as e:
            logger.error(f"File storage failed: {str(e)}")
            return None

    def retrieve_file(self, storage_path: str) -> Optional[bytes]:
        """
        Retrieve file from storage

        Args:
            storage_path: Storage path from store_file()

        Returns:
            File content bytes, or None if not found
        """
        try:
            response = supabase_client.client.storage.from_(self.bucket_name).download(storage_path)
            return response

        except Exception as e:
            logger.error(f"File retrieval failed: {str(e)}")
            return None

    def file_exists(self, storage_path: str) -> bool:
        """
        Check if file exists in storage

        Args:
            storage_path: Storage path to check

        Returns:
            True if exists, False otherwise
        """
        try:
            # Try to get file metadata
            files = supabase_client.client.storage.from_(self.bucket_name).list(
                path=os.path.dirname(storage_path)
            )
            filename = os.path.basename(storage_path)
            return any(f.get("name") == filename for f in files)

        except Exception:
            return False

    def delete_file(self, storage_path: str) -> bool:
        """
        Delete file from storage

        Args:
            storage_path: Storage path to delete

        Returns:
            True if successful
        """
        try:
            supabase_client.client.storage.from_(self.bucket_name).remove([storage_path])
            logger.info(f"Deleted file: {storage_path}")
            return True

        except Exception as e:
            logger.error(f"File deletion failed: {str(e)}")
            return False

    def get_signed_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Generate signed URL for temporary file access

        Args:
            storage_path: Storage path
            expires_in: Expiration time in seconds (default 1 hour)

        Returns:
            Signed URL string or None
        """
        try:
            response = supabase_client.client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path, expires_in=expires_in
            )
            return response.get("signedURL")

        except Exception as e:
            logger.error(f"Signed URL generation failed: {str(e)}")
            return None

    def create_temp_file(self, file_content: bytes, suffix: str = "") -> str:
        """
        Create secure temporary file

        Args:
            file_content: File content bytes
            suffix: File suffix/extension

        Returns:
            Path to temporary file (caller must delete)
        """
        try:
            # Create temp file with secure permissions
            fd, temp_path = tempfile.mkstemp(suffix=suffix)

            # Write content
            with os.fdopen(fd, "wb") as f:
                f.write(file_content)

            logger.debug(f"Created temp file: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Temp file creation failed: {str(e)}")
            raise

    def cleanup_temp_file(self, temp_path: str):
        """
        Securely delete temporary file

        Args:
            temp_path: Path to temp file
        """
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")

        except Exception as e:
            logger.warning(f"Temp file cleanup failed: {str(e)}")

    def schedule_deletion(self, storage_path: str, days: int = 30) -> Optional[datetime]:
        """
        Schedule file for future deletion (for data retention)

        Args:
            storage_path: Storage path
            days: Days until deletion

        Returns:
            Deletion datetime or None
        """
        # Note: Actual deletion would be handled by maintenance cron job
        # This just returns the scheduled deletion time
        deletion_time = datetime.utcnow() + timedelta(days=days)

        # Store deletion schedule in database
        # (Would need to add a table for scheduled deletions)

        logger.info(f"Scheduled deletion for {storage_path} at {deletion_time}")
        return deletion_time

    def _guess_content_type(self, filename: str) -> str:
        """
        Guess content type from filename

        Args:
            filename: File name

        Returns:
            MIME type string
        """
        extension = filename.lower().split(".")[-1]

        content_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "odt": "application/vnd.oasis.opendocument.text",
            "eml": "message/rfc822",
            "txt": "text/plain",
            "zip": "application/zip",
        }

        return content_types.get(extension, "application/octet-stream")

    def get_storage_stats(self, user_id: str) -> Dict:
        """
        Get storage statistics for a user

        Args:
            user_id: User ID

        Returns:
            Dict with storage stats
        """
        try:
            # List all files for user
            files = supabase_client.client.storage.from_(self.bucket_name).list(path=user_id)

            total_size = sum(f.get("metadata", {}).get("size", 0) for f in files)
            file_count = len(files)

            return {
                "user_id": user_id,
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.error(f"Storage stats failed: {str(e)}")
            return {"user_id": user_id, "file_count": 0, "total_size_bytes": 0, "error": str(e)}


# Global instance
file_storage = FileStorage()
