"""Detect, launch, and focus the Edge browser window."""

import subprocess
import time

import pygetwindow as gw


def find_edge_window() -> object | None:
    """Find the first visible Edge browser window."""
    windows = gw.getWindowsWithTitle("Edge")
    if not windows:
        windows = gw.getWindowsWithTitle(
            "Microsoft\u200b\u200bEdge"
        )
    for window in windows:
        if window.visible:
            return window
    return None


def focus_edge_window(window) -> bool:
    """Bring Edge window to foreground and maximize."""
    try:
        if window.isMinimized:
            window.restore()
            time.sleep(0.3)
        window.activate()
        time.sleep(0.3)
        return True
    except Exception:
        return False


def launch_edge(url: str) -> bool:
    """Launch Edge browser with the given URL."""
    try:
        subprocess.Popen(
            [
                "cmd",
                "/c",
                "start",
                "msedge",
                url,
            ]
        )
        time.sleep(3)
        return True
    except Exception:
        return False


def get_edge_window_region() -> dict | None:
    """
    Return screen coordinates of Edge window content area.
    Returns {"top": y, "left": x, "width": w, "height": h}
    or None if Edge window not found.
    """
    window = find_edge_window()
    if window is None:
        return None

    return {
        "top": max(0, window.top + 80),
        "left": max(0, window.left),
        "width": window.width,
        "height": window.height - 80,
    }


def ensure_edge_ready(url: str) -> bool:
    """
    Ensure Edge is open and focused with the given URL.
    Launches Edge if not already running.
    Returns True if ready, False on failure.
    """
    window = find_edge_window()

    if window is None:
        launched = launch_edge(url)
        if not launched:
            return False
        time.sleep(2)
        window = find_edge_window()

    if window is None:
        return False

    return focus_edge_window(window)
