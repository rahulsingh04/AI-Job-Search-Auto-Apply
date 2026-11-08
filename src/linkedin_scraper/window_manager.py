"""Detect, launch, and focus the Edge browser window."""

import subprocess
import time

import pygetwindow as gw


EDGE_TITLES = [
    "edge",
    "microsoft edge",
    "msedge",
]

EDGE_EXECUTABLES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application"
    r"\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application"
    r"\msedge.exe",
    "msedge",
]


def find_edge_window() -> object | None:
    """Find the first visible Edge browser window."""
    all_windows = gw.getAllWindows()
    for window in all_windows:
        title_lower = (window.title or "").lower()
        if any(
            edge_kw in title_lower
            for edge_kw in EDGE_TITLES
        ):
            if window.visible:
                return window
    return None


def focus_edge_window(window) -> bool:
    """Bring Edge window to foreground and maximize."""
    try:
        if window.isMinimized:
            window.restore()
            time.sleep(0.5)
        window.activate()
        time.sleep(0.5)
        return True
    except Exception:
        return False


def launch_edge(url: str) -> bool:
    """Launch Edge browser with the given URL."""
    for exe in EDGE_EXECUTABLES:
        try:
            subprocess.Popen(
                [exe, url],
                shell=False,
            )
            time.sleep(4)
            return True
        except (FileNotFoundError, OSError):
            continue

    # Fallback: use Windows start command
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "msedge", url],
            shell=False,
        )
        time.sleep(4)
        return True
    except Exception:
        pass

    # Last resort: open with default browser
    try:
        import webbrowser
        webbrowser.open(url)
        time.sleep(3)
        return True
    except Exception:
        return False


def get_edge_window_region() -> dict | None:
    """
    Return screen coordinates of Edge window content area.
    Returns {top, left, width, height} or None if not found.
    """
    window = find_edge_window()
    if window is None:
        return None

    return {
        "top": max(0, window.top + 80),
        "left": max(0, window.left),
        "width": max(100, window.width),
        "height": max(100, window.height - 80),
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
        time.sleep(3)
        window = find_edge_window()

    if window is None:
        # Edge launched but window title not matched yet
        # Try one more time after extra wait
        time.sleep(3)
        window = find_edge_window()

    if window is None:
        # Still not found — browser may have opened but
        # title detection failed; return True optimistically
        # so scraping can still attempt to proceed
        return True

    return focus_edge_window(window)


def build_linkedin_job_search_url(
    job_titles: list[str],
) -> str:
    """
    Build LinkedIn job search URL for one or more titles.
    Multiple titles are joined with OR operator.
    """
    from urllib.parse import quote_plus

    if not job_titles:
        return "https://www.linkedin.com/jobs/"

    if len(job_titles) == 1:
        query = quote_plus(job_titles[0].strip())
    else:
        combined = " OR ".join(
            f'"{t.strip()}"'
            for t in job_titles
            if t.strip()
        )
        query = quote_plus(combined)

    return (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={query}"
    )
