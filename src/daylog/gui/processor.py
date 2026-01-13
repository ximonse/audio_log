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

        # Progress monitor control
        import threading
        done = {"value": False}

        try:
            # Stage 1: Preparing (0-5%)
            self._update_progress(item.id, queue, 0.02, "Preparing...")
            time.sleep(0.1)

            # Stage 2: Converting audio (5-20%)
            self._update_progress(item.id, queue, 0.05, "Converting audio...")

            # Run pipeline with progress monitoring in separate thread
            progress = {"value": 0.05, "message": "Converting audio..."}

            def update_progress_loop():
                # Simple stage-based progress that doesn't get stuck
                stages = [
                    (0.10, "Converting audio..."),
                    (0.20, "Stage 1/5: Audio conversion"),
                    (0.30, "Stage 2/5: VAD processing"),
                    (0.40, "Stage 2/5: VAD - Energy filter"),
                    (0.50, "Stage 2/5: VAD - Spectral analysis"),
                    (0.60, "Stage 2/5: VAD - Silero"),
                    (0.70, "Stage 3/5: Transcription"),
                    (0.80, "Stage 3/5: Transcribing (check terminal for details)"),
                    (0.85, "Stage 4/5: Merging chunks"),
                    (0.90, "Stage 5/5: Writing outputs"),
                ]
                stage_idx = 0
                while not done["value"]:
                    time.sleep(3.0)  # Update every 3 seconds
                    if not done["value"] and stage_idx < len(stages):
                        prog, msg = stages[stage_idx]
                        progress["value"] = prog
                        progress["message"] = msg
                        self._update_progress(item.id, queue, prog, msg)
                        stage_idx += 1
                    # After all stages, stay at 90% showing terminal message

            monitor_thread = threading.Thread(target=update_progress_loop, daemon=True)
            monitor_thread.start()

            logging.info(f"Processing {item.filename}")
            outputs = run_pipeline(
                input_path=item.path,
                config=self.config,
                date_override=item.date if not item.use_mtime else None,
                start_time=item.start_time,
                use_mtime=item.use_mtime,
            )

            done["value"] = True
            monitor_thread.join(timeout=0.5)

            # Stage 5: Saving (90-100%)
            self._update_progress(item.id, queue, 0.92, "Saving outputs...")
            time.sleep(0.1)
            self._update_progress(item.id, queue, 0.96, "Writing files...")
            time.sleep(0.1)

            # Success
            output_paths = ", ".join([str(p) for p in outputs])
            queue.update_status(item.id, "completed", 1.0, f"Done: {output_paths}")
            self.progress_callback(item.id, "completed", 1.0, "Completed")
            logging.info(f"Completed {item.filename}")

        except Exception as e:
            # Failure - stop progress monitor
            done["value"] = True
            error_msg = str(e)
            queue.update_status(item.id, "failed", 0.0, "Failed", error_msg)
            self.progress_callback(item.id, "failed", 0.0, error_msg)
            logging.error(f"Failed to process {item.filename}: {error_msg}")
            raise

        finally:
            # Ensure monitor thread is stopped
            done["value"] = True
            self._current_item_id = None
