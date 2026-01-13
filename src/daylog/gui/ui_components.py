"""UI component builders for Daylog GUI."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

if TYPE_CHECKING:
    from typing import Optional


def setup_queue_display(parent: tk.Frame) -> ttk.Treeview:
    """
    Setup queue display treeview.

    Args:
        parent: Parent frame

    Returns:
        Configured Treeview widget
    """
    queue_frame = tk.Frame(parent, bg="#e8f4f8")
    queue_frame.pack(fill="both", expand=True, pady=(0, 10))

    # Treeview
    columns = ("file", "datetime", "status")
    tree = ttk.Treeview(queue_frame, columns=columns, show="headings", height=12)
    tree.heading("file", text="Filename")
    tree.heading("datetime", text="Date/Time")
    tree.heading("status", text="Status")

    tree.column("file", width=300)
    tree.column("datetime", width=180)
    tree.column("status", width=100)

    # Scrollbar
    scrollbar = ttk.Scrollbar(queue_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Tag colors
    tree.tag_configure("pending", background="#f0f0f0")
    tree.tag_configure("processing", background="#cce5ff")
    tree.tag_configure("completed", background="#ccffcc")
    tree.tag_configure("failed", background="#ffcccc")

    return tree


def setup_controls(
    parent: tk.Frame,
    on_browse: Callable,
    on_drop: Optional[Callable],
    on_start: Callable,
    on_pause: Callable,
    on_clear: Callable,
    on_cancel: Callable,
    has_dnd: bool,
) -> dict:
    """
    Setup control panel.

    Args:
        parent: Parent frame
        on_browse: Browse button callback
        on_drop: Drag & drop callback (or None if DnD not available)
        on_start: Start button callback
        on_pause: Pause button callback
        on_clear: Clear button callback
        on_cancel: Cancel button callback
        has_dnd: Whether tkinterdnd2 is available

    Returns:
        Dict with widgets: start_btn, pause_btn, clear_btn, cancel_btn,
                          status_label, progress_bar
    """
    controls_frame = tk.Frame(parent, bg="#e8f4f8")
    controls_frame.pack(fill="both")

    # Drop zone
    drop_frame = tk.Frame(controls_frame, bg="#d4e9f2", relief="groove", bd=2, height=80)
    drop_frame.pack(fill="x", pady=(0, 10))
    drop_frame.pack_propagate(False)

    drop_label = tk.Label(
        drop_frame,
        text="Drag audio files here or click Browse",
        bg="#d4e9f2",
        fg="#2c5f7a",
        font=("Segoe UI", 11),
        cursor="hand2",
    )
    drop_label.pack(expand=True)
    drop_label.bind("<Button-1>", lambda e: on_browse())

    # Register drag & drop
    if has_dnd and on_drop:
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind("<<Drop>>", on_drop)
        logging.info("Drag & drop registered successfully")
    else:
        logging.warning(f"Drag & drop NOT registered (has_dnd={has_dnd}, on_drop={on_drop})")

    # Action buttons
    btn_frame = tk.Frame(controls_frame, bg="#e8f4f8")
    btn_frame.pack(fill="x", pady=(0, 10))

    start_btn = create_button(btn_frame, "▶ Start", "#4CAF50", on_start)
    pause_btn = create_button(btn_frame, "⏸ Pause", "#FF9800", on_pause, state="disabled")
    clear_btn = create_button(btn_frame, "Clear Done", "#FFC107", on_clear)
    cancel_btn = create_button(btn_frame, "✗ Cancel", "#F44336", on_cancel)

    start_btn.pack(side="left", padx=5)
    pause_btn.pack(side="left", padx=5)
    clear_btn.pack(side="left", padx=5)
    cancel_btn.pack(side="left", padx=5)

    # Status bar
    status_frame = tk.Frame(controls_frame, bg="#e8f4f8")
    status_frame.pack(fill="x")

    status_label = tk.Label(
        status_frame,
        text="Ready - Drop files to begin",
        bg="#e8f4f8",
        fg="#2c5f7a",
        font=("Segoe UI", 9),
        anchor="w",
    )
    status_label.pack(side="left", fill="x", expand=True)

    # Progress bar
    progress_bar = ttk.Progressbar(status_frame, length=200, mode="determinate")
    progress_bar.pack(side="right", padx=(5, 0))

    return {
        "start_btn": start_btn,
        "pause_btn": pause_btn,
        "clear_btn": clear_btn,
        "cancel_btn": cancel_btn,
        "status_label": status_label,
        "progress_bar": progress_bar,
    }


def create_button(
    parent: tk.Frame,
    text: str,
    color: str,
    command: Callable,
    state: str = "normal",
) -> tk.Button:
    """
    Create a styled button.

    Args:
        parent: Parent frame
        text: Button text
        color: Background color
        command: Click callback
        state: Button state (normal/disabled)

    Returns:
        Configured Button widget
    """
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=color,
        fg="white",
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        bd=0,
        padx=15,
        pady=8,
        cursor="hand2",
        state=state,
    )
