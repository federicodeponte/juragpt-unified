"""
ABOUTME: Tracks last successful update timestamp for incremental corpus updates.
ABOUTME: Enables efficient daily updates by fetching only new documents since last run.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.exceptions import CheckpointLoadError, CheckpointSaveError

logger = logging.getLogger(__name__)


class UpdateTracker:
    """
    Tracks timestamps for incremental corpus updates.

    Stores the timestamp of the last successful update to enable
    fetching only new documents on subsequent runs.

    File format:
        data/update_state.json:
        {
            "last_update": "2025-10-29T10:00:00",
            "last_update_docs_count": 1523,
            "total_runs": 42
        }

    Usage:
        tracker = UpdateTracker()

        # Get last update time
        last_update = tracker.get_last_update()

        # After successful update
        tracker.save_update(docs_count=1523)
    """

    def __init__(self, state_file: Path = Path("data/update_state.json")):
        """
        Initialize update tracker.

        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"UpdateTracker initialized: {self.state_file}")

    def get_last_update(self) -> Optional[datetime]:
        """
        Get timestamp of last successful update.

        Returns:
            Last update datetime or None if never updated
        """
        if not self.state_file.exists():
            logger.info("No previous update found (first run)")
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            last_update_str = state.get("last_update")
            if not last_update_str:
                return None

            last_update = datetime.fromisoformat(last_update_str)
            logger.info(f"Last update: {last_update.isoformat()}")
            return last_update

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error loading update state: {e}")
            raise CheckpointLoadError(str(self.state_file), reason=str(e)) from e

    def get_last_update_iso(self) -> Optional[str]:
        """
        Get last update timestamp in ISO format (for API queries).

        Returns:
            ISO-formatted date string (YYYY-MM-DD) or None
        """
        last_update = self.get_last_update()
        if not last_update:
            return None

        # Return only date part (APIs expect YYYY-MM-DD)
        return last_update.date().isoformat()

    def save_update(
        self,
        timestamp: Optional[datetime] = None,
        docs_count: int = 0,
    ) -> None:
        """
        Save successful update timestamp.

        Args:
            timestamp: Update timestamp (defaults to now)
            docs_count: Number of documents processed
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Load existing state to preserve counters
        try:
            if self.state_file.exists():
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            else:
                state = {"total_runs": 0}
        except Exception:
            state = {"total_runs": 0}

        # Update state
        state["last_update"] = timestamp.isoformat()
        state["last_update_docs_count"] = docs_count
        state["total_runs"] = state.get("total_runs", 0) + 1

        # Atomic write
        temp_file = self.state_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            temp_file.rename(self.state_file)

            logger.info(
                f"Update state saved: {timestamp.isoformat()} "
                f"({docs_count} docs, run #{state['total_runs']})"
            )

        except OSError as e:
            raise CheckpointSaveError(str(self.state_file), reason=str(e)) from e
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

    def get_stats(self) -> dict:
        """
        Get update statistics.

        Returns:
            Dictionary with last_update, docs_count, total_runs
        """
        if not self.state_file.exists():
            return {
                "last_update": None,
                "last_update_docs_count": 0,
                "total_runs": 0,
            }

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            return {
                "last_update": state.get("last_update"),
                "last_update_docs_count": state.get("last_update_docs_count", 0),
                "total_runs": state.get("total_runs", 0),
            }
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return {
                "last_update": None,
                "last_update_docs_count": 0,
                "total_runs": 0,
            }

    def reset(self) -> None:
        """
        Reset update state (for testing or manual intervention).
        """
        if self.state_file.exists():
            self.state_file.unlink()
            logger.info("Update state reset")
        else:
            logger.info("No update state to reset")


def main():
    """Test update tracker."""
    import sys
    import time

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    tracker = UpdateTracker(state_file=Path("data/test_update_state.json"))

    print("\n=== UpdateTracker Test ===\n")

    # Test 1: First run (no previous update)
    last_update = tracker.get_last_update()
    print(f"1. Last update (first run): {last_update}")
    assert last_update is None

    # Test 2: Save update
    tracker.save_update(docs_count=100)
    print("2. Saved update (100 docs)")

    # Test 3: Get last update
    last_update = tracker.get_last_update()
    print(f"3. Last update: {last_update}")
    assert last_update is not None

    # Test 4: Get ISO format
    iso_date = tracker.get_last_update_iso()
    print(f"4. Last update (ISO): {iso_date}")

    # Test 5: Multiple updates
    time.sleep(0.1)
    tracker.save_update(docs_count=50)
    time.sleep(0.1)
    tracker.save_update(docs_count=75)

    # Test 6: Get stats
    stats = tracker.get_stats()
    print(f"\n5. Stats:")
    print(f"   - Total runs: {stats['total_runs']}")
    print(f"   - Last run docs: {stats['last_update_docs_count']}")
    print(f"   - Last update: {stats['last_update']}")

    assert stats["total_runs"] == 3
    assert stats["last_update_docs_count"] == 75

    # Cleanup
    tracker.reset()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()
