"""Thread-safe file queue for batch processing."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class QueueItem:
    """Represents a file in the processing queue."""

    id: str
    path: Path
    date: str  # YYYY-MM-DD
    start_time: Optional[str]  # ISO format or None
    use_mtime: bool
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0  # 0.0-1.0
    message: str = ""  # Status message
    error: Optional[str] = None

    @property
    def filename(self) -> str:
        """Get filename for display."""
        return self.path.name

    @property
    def datetime_display(self) -> str:
        """Get date/time for display."""
        if self.start_time:
            # Extract HH:MM:SS from ISO string
            try:
                time_part = self.start_time.split("T")[1].split("+")[0].split(".")[0]
                return f"{self.date} {time_part}"
            except (IndexError, AttributeError):
                return self.date
        return self.date

    @property
    def status_icon(self) -> str:
        """Get status icon."""
        icons = {
            "pending": "⏳",
            "processing": "▶",
            "completed": "✓",
            "failed": "✗",
        }
        return icons.get(self.status, "?")

    @property
    def status_display(self) -> str:
        """Get status for display."""
        if self.status == "processing" and self.progress > 0:
            return f"{self.status_icon} {int(self.progress * 100)}%"
        return self.status_icon


@dataclass
class FileQueue:
    """Thread-safe queue for managing file processing."""

    items: List[QueueItem] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(
        self,
        path: Path,
        date: str,
        start_time: Optional[str],
        use_mtime: bool,
    ) -> str:
        """
        Add a file to the queue.

        Args:
            path: Path to audio file
            date: Date string (YYYY-MM-DD)
            start_time: Optional start time (ISO format)
            use_mtime: Whether to use file mtime

        Returns:
            ID of created queue item
        """
        with self._lock:
            item_id = str(uuid.uuid4())
            item = QueueItem(
                id=item_id,
                path=path,
                date=date,
                start_time=start_time,
                use_mtime=use_mtime,
            )
            self.items.append(item)
            return item_id

    def remove(self, item_id: str) -> bool:
        """
        Remove an item from the queue.

        Args:
            item_id: ID of item to remove

        Returns:
            True if item was removed, False if not found
        """
        with self._lock:
            for i, item in enumerate(self.items):
                if item.id == item_id:
                    self.items.pop(i)
                    return True
            return False

    def clear_completed(self) -> int:
        """
        Clear all completed and failed items.

        Returns:
            Number of items removed
        """
        with self._lock:
            count = len([i for i in self.items if i.status in ("completed", "failed")])
            self.items = [
                i for i in self.items if i.status not in ("completed", "failed")
            ]
            return count

    def clear_all(self) -> int:
        """
        Clear all items.

        Returns:
            Number of items removed
        """
        with self._lock:
            count = len(self.items)
            self.items = []
            return count

    def get_next_pending(self) -> Optional[QueueItem]:
        """
        Get the next pending item to process.

        Returns:
            Next pending item or None if queue is empty/all processed
        """
        with self._lock:
            for item in self.items:
                if item.status == "pending":
                    return item
            return None

    def get_by_id(self, item_id: str) -> Optional[QueueItem]:
        """
        Get an item by ID.

        Args:
            item_id: ID of item to get

        Returns:
            QueueItem if found, None otherwise
        """
        with self._lock:
            for item in self.items:
                if item.id == item_id:
                    return item
            return None

    def update_status(
        self,
        item_id: str,
        status: str,
        progress: float = 0.0,
        message: str = "",
        error: Optional[str] = None,
    ) -> bool:
        """
        Update an item's status.

        Args:
            item_id: ID of item to update
            status: New status
            progress: Progress (0.0-1.0)
            message: Status message
            error: Error message (if failed)

        Returns:
            True if item was updated, False if not found
        """
        with self._lock:
            for item in self.items:
                if item.id == item_id:
                    item.status = status
                    item.progress = progress
                    item.message = message
                    if error:
                        item.error = error
                    return True
            return False

    def update_datetime(
        self,
        item_id: str,
        date: str,
        start_time: Optional[str],
        use_mtime: bool,
    ) -> bool:
        """
        Update an item's date/time.

        Args:
            item_id: ID of item to update
            date: New date string (YYYY-MM-DD)
            start_time: New start time (ISO format or None)
            use_mtime: Whether to use file mtime

        Returns:
            True if item was updated, False if not found
        """
        with self._lock:
            for item in self.items:
                if item.id == item_id:
                    item.date = date
                    item.start_time = start_time
                    item.use_mtime = use_mtime
                    return True
            return False

    def get_all(self) -> List[QueueItem]:
        """
        Get a copy of all items for display.

        Returns:
            List of all queue items (shallow copy)
        """
        with self._lock:
            return self.items.copy()

    def get_counts(self) -> dict:
        """
        Get status counts for display.

        Returns:
            Dict with counts: total, pending, processing, completed, failed
        """
        with self._lock:
            counts = {
                "total": len(self.items),
                "pending": sum(1 for i in self.items if i.status == "pending"),
                "processing": sum(1 for i in self.items if i.status == "processing"),
                "completed": sum(1 for i in self.items if i.status == "completed"),
                "failed": sum(1 for i in self.items if i.status == "failed"),
            }
            return counts
