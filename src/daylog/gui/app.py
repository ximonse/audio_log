"""Main GUI application for Daylog."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None  # Fallback if tkinterdnd2 not installed

from daylog.config import load_config, DaylogConfig

from .date_parser import DateTimeParser
from .processor import BatchProcessor
from .queue_manager import FileQueue
from .ui_components import setup_queue_display, setup_controls


class DaylogGUI:
    """Main Daylog GUI application."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize GUI."""
        # Load config
        self.config = load_config(config_path)

        # Initialize components
        self.queue = FileQueue()
        self.processor = BatchProcessor(self.config, self._on_progress)

        # Create window
        if TkinterDnD:
            self.root = TkinterDnD.Tk()
            logging.info("TkinterDnD enabled")
        else:
            self.root = tk.Tk()
            logging.warning("tkinterdnd2 not available, drag & drop disabled")

        self.root.title("Daylog - Audio Processing")
        self.root.geometry("700x600")
        self.root.minsize(600, 500)

        # Styling
        self.root.configure(bg="#e8f4f8")
        self.root.attributes("-alpha", 0.95)

        # Register drag & drop on entire window (Windows compatibility)
        if TkinterDnD:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self.on_drop)
            logging.info("Drag & drop registered on root window")

        # UI components
        self.tree: Optional[ttk.Treeview] = None
        self.status_label: Optional[tk.Label] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.start_btn: Optional[tk.Button] = None
        self.pause_btn: Optional[tk.Button] = None
        self.clear_btn: Optional[tk.Button] = None
        self.cancel_btn: Optional[tk.Button] = None

        self.setup_ui()
        self.bind_events()

    def setup_ui(self) -> None:
        """Setup UI components."""
        # Main container
        main_frame = tk.Frame(self.root, bg="#e8f4f8")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Top: Queue display (60%)
        self.tree = setup_queue_display(main_frame)

        # Bottom: Controls (40%)
        controls = setup_controls(
            main_frame,
            on_browse=self.on_browse,
            on_drop=self.on_drop if TkinterDnD else None,
            on_start=self.on_start,
            on_pause=self.on_pause,
            on_clear=self.on_clear,
            on_cancel=self.on_cancel,
            has_dnd=TkinterDnD is not None,
        )

        self.start_btn = controls["start_btn"]
        self.pause_btn = controls["pause_btn"]
        self.clear_btn = controls["clear_btn"]
        self.cancel_btn = controls["cancel_btn"]
        self.status_label = controls["status_label"]
        self.progress_bar = controls["progress_bar"]

    def bind_events(self) -> None:
        """Bind keyboard and window events."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_drop(self, event) -> None:
        """Handle drag & drop files."""
        files = self.root.tk.splitlist(event.data)
        logging.info(f"Dropped {len(files)} file(s): {files}")
        for file_path_str in files:
            # Strip curly braces that Windows sometimes adds
            file_path_str = file_path_str.strip("{}")
            logging.info(f"Processing: {file_path_str}")
            self._add_file(Path(file_path_str))

    def on_browse(self) -> None:
        """Handle browse button."""
        files = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[
                ("Audio files", "*.mp3 *.m4a *.aac *.wav *.flac *.ogg *.opus *.wma *.webm"),
                ("All files", "*.*"),
            ],
        )
        for file_path in files:
            self._add_file(Path(file_path))

    def _add_file(self, path: Path) -> None:
        """Add file to queue."""
        logging.info(f"Adding file: {path}")
        if not path.exists():
            logging.warning(f"File not found: {path}")
            return

        # Check if it's a file (not directory)
        if not path.is_file():
            logging.warning(f"Not a file: {path}")
            return

        # Check file extension (warn but allow - ffmpeg will validate)
        SUPPORTED_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg', '.opus', '.wma', '.webm'}
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logging.warning(f"Unsupported file type: {path.suffix} (file: {path.name})")
            # Still add it - let ffmpeg decide if it can handle it

        # Parse date/time
        date_str, start_time_iso, use_mtime = DateTimeParser.extract_date_time(path)
        logging.info(f"Parsed date/time: {date_str} {start_time_iso} (use_mtime={use_mtime})")

        # Add to queue
        self.queue.add(path, date_str, start_time_iso, use_mtime)
        logging.info(f"Added to queue: {path.name}")

        # Update display
        self._update_queue_display()
        self._update_status_bar()

    def on_start(self) -> None:
        """Start batch processing."""
        if self.queue.get_counts()["pending"] == 0:
            logging.info("No pending files to process")
            return

        self.processor.start(self.queue)
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")

    def on_pause(self) -> None:
        """Pause/resume processing."""
        if self.processor.is_paused():
            self.processor.resume()
            self.pause_btn.config(text="⏸ Pause")
        else:
            self.processor.pause()
            self.pause_btn.config(text="▶ Resume")

    def on_clear(self) -> None:
        """Clear completed/failed items."""
        count = self.queue.clear_completed()
        logging.info(f"Cleared {count} items")
        self._update_queue_display()
        self._update_status_bar()

    def on_cancel(self) -> None:
        """Cancel processing and clear queue."""
        self.processor.stop()
        self.queue.clear_all()
        self._update_queue_display()
        self._update_status_bar()
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")

    def on_close(self) -> None:
        """Handle window close."""
        self.processor.stop()
        self.root.destroy()

    def _on_progress(self, item_id: str, status: str, progress: float, message: str) -> None:
        """Progress callback from processor (runs in background thread)."""
        # Thread-safe UI update
        self.root.after(0, lambda: self._update_progress(item_id, status, progress, message))

    def _update_progress(self, item_id: str, status: str, progress: float, message: str) -> None:
        """Update UI with progress (runs in main thread)."""
        self._update_queue_display()
        self._update_status_bar()

        # Check if processing finished
        if not self.processor.is_running():
            self.start_btn.config(state="normal")
            self.pause_btn.config(state="disabled")

    def _update_queue_display(self) -> None:
        """Update treeview with current queue state."""
        # Clear treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Populate with queue items
        for item in self.queue.get_all():
            self.tree.insert(
                "",
                "end",
                values=(item.filename, item.datetime_display, item.status_display),
                tags=(item.status,),
            )

    def _update_status_bar(self) -> None:
        """Update status bar with queue counts."""
        counts = self.queue.get_counts()

        if counts["total"] == 0:
            status_text = "Ready - Drop files to begin"
            progress_val = 0
        elif counts["processing"] > 0:
            status_text = f"Processing {counts['completed'] + 1}/{counts['total']} files..."
            progress_val = int((counts["completed"] / counts["total"]) * 100)
        elif counts["pending"] > 0:
            status_text = f"{counts['pending']} files waiting - Click Start"
            progress_val = int((counts["completed"] / counts["total"]) * 100)
        else:
            status_text = f"Done - {counts['completed']} completed, {counts['failed']} failed"
            progress_val = 100

        self.status_label.config(text=status_text)
        self.progress_bar["value"] = progress_val

    def run(self) -> None:
        """Run the GUI main loop."""
        logging.info("Starting Daylog GUI")
        self.root.mainloop()
