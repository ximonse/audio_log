"""Background processor for batch file processing."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from daylog.config import DaylogConfig
from daylog.pipeline.run import run_pipeline

from .queue_manager import FileQueue, QueueItem


class BatchProcessor:
    """Processes files from queue in background thread."""

    def __init__(
        self,
        config: DaylogConfig,
        progress_callback: Callable[[str, str, float, str], None],
    ):
        """
        Initialize batch processor.

        Args:
            config: Daylog configuration
            progress_callback: Callback(item_id, status, progress, message)
        """
        self.config = config
        self.progress_callback = progress_callback
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.paused = False
        self._current_item_id: Optional[str] = None

    def start(self, queue: FileQueue) -> None:
        """
        Start background processing thread.

        Args:
            queue: File queue to process
        """
        if self.running:
            logging.warning("Processor already running")
            return

        self.running = True
        self.paused = False
        self.thread = threading.Thread(
            target=self._process_loop, args=(queue,), daemon=True
        )
        self.thread.start()
        logging.info("Batch processor started")

    def pause(self) -> None:
        """Pause processing (finish current file first)."""
        self.paused = True
        logging.info("Batch processor pausing...")

    def resume(self) -> None:
        """Resume processing."""
        self.paused = False
        logging.info("Batch processor resumed")

    def stop(self) -> None:
        """Stop processing (finish current file first)."""
        self.running = False
        logging.info("Batch processor stopping...")

    def is_running(self) -> bool:
        """Check if processor is running."""
        return self.running

    def is_paused(self) -> bool:
        """Check if processor is paused."""
        return self.paused

    def get_current_item_id(self) -> Optional[str]:
        """Get ID of currently processing item."""
        return self._current_item_id

    def _update_progress(self, item_id: str, queue: FileQueue, progress: float, message: str) -> None:
        """Helper to update progress in both queue and callback."""
        queue.update_status(item_id, "processing", progress, message)
        self.progress_callback(item_id, "processing", progress, message)

    def _process_loop(self, queue: FileQueue) -> None:
        """
        Main processing loop (runs in background thread).

        Args:
            queue: File queue to process
        """
        try:
            while self.running:
                # Check pause state
                if self.paused:
                    time.sleep(0.5)
                    continue

                # Get next pending item
                item = queue.get_next_pending()
                if item is None:
                    # Queue empty, stop
                    logging.info("Queue empty, processor finished")
                    break

                # Process item
                try:
                    self._process_item(item, queue)
                except Exception as e:
                    logging.error(f"Error processing {item.filename}: {e}")
                    queue.update_status(
                        item.id, "failed", 0.0, "Processing failed", str(e)
                    )
                    self.progress_callback(item.id, "failed", 0.0, str(e))

        finally:
            self.running = False
            self._current_item_id = None
            logging.info("Batch processor stopped")

    def _process_item(self, item: QueueItem, queue: FileQueue) -> None:
        """
        Process a single queue item.

        Args:
            item: Queue item to process
            queue: File queue for status updates
        """
        self._current_item_id = item.id

        try:
            # Initial status
            self._update_progress(item.id, queue, 0.01, "Initializing...")
            logging.info(f"Processing {item.filename}")

            # Callback for pipeline
            def pipeline_progress(stage: str, progress: float):
                # Throttle updates if needed, but for now direct transparency is good
                # Ensure we don't block the pipeline, so keep it lightweight.
                # _update_progress just puts things in queue/callback, which is fast.
                self._update_progress(item.id, queue, progress, stage)

            outputs = run_pipeline(
                input_path=item.path,
                config=self.config,
                date_override=item.date if not item.use_mtime else None,
                start_time=item.start_time,
                use_mtime=item.use_mtime,
                progress_callback=pipeline_progress,
            )

            # Success
            output_paths = ", ".join([str(p) for p in outputs])
            queue.update_status(item.id, "completed", 1.0, f"Done: {output_paths}")
            self.progress_callback(item.id, "completed", 1.0, "Completed")
            logging.info(f"Completed {item.filename}")

        except Exception as e:
            # Failure
            error_msg = str(e)
            queue.update_status(item.id, "failed", 0.0, "Failed", error_msg)
            self.progress_callback(item.id, "failed", 0.0, error_msg)
            logging.error(f"Failed to process {item.filename}: {error_msg}")
            raise

        finally:
            self._current_item_id = None
