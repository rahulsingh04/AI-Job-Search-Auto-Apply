"""Smart LinkedIn post scroller with email extraction."""

import json
import queue
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pyautogui

from linkedin_scraper.screenshot import capture_and_check
from linkedin_scraper.ocr_extractor import (
    extract_emails_from_image,
)
from linkedin_scraper.window_manager import (
    get_edge_window_region,
    focus_edge_window,
    find_edge_window,
)

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)


def _load_seen_emails() -> set[str]:
    """Load all emails already in Email_Storage.json."""
    storage_file = PROJECT_ROOT / "Email_Storage.json"
    if not storage_file.is_file():
        return set()
    try:
        with storage_file.open(
            "r", encoding="utf-8"
        ) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return set(data.keys())
    except Exception:
        pass
    return set()


def _scroll_down(scroll_amount: int) -> None:
    """Scroll down by given amount using pyautogui."""
    try:
        pyautogui.scroll(-scroll_amount)
    except Exception:
        pass


def _run_scrape_loop(
    scraper_cfg: dict,
    result_queue: queue.Queue,
) -> None:
    """
    Blocking scrape loop — runs in a background thread.
    Puts event dicts into result_queue.
    Sentinel None signals completion.
    """
    linkedin_cfg = scraper_cfg.get("linkedin", {})
    ocr_cfg = scraper_cfg.get("ocr", {})

    max_posts = linkedin_cfg.get("max_posts", 20)
    streak_limit = linkedin_cfg.get(
        "empty_streak_limit", 10
    )
    scroll_amount = linkedin_cfg.get("scroll_amount", 3)
    scroll_delay = linkedin_cfg.get(
        "scroll_delay_seconds", 0.8
    )
    post_wait = linkedin_cfg.get(
        "post_load_wait_seconds", 1.0
    )

    seen_emails = _load_seen_emails()
    session_emails: set[str] = set()
    empty_streak = 0
    total_found = 0

    result_queue.put({"event": "started"})

    window = find_edge_window()
    if window:
        focus_edge_window(window)
    time.sleep(post_wait)

    for post_number in range(1, max_posts + 1):
        try:
            region = get_edge_window_region()
        except Exception as err:
            result_queue.put({
                "event": "error",
                "message": (
                    f"Window region error: {err}"
                ),
            })
            break

        if region is None:
            result_queue.put({
                "event": "error",
                "message": (
                    "Edge window not found. "
                    "Please keep Edge open."
                ),
            })
            break

        try:
            image, has_potential = capture_and_check(
                region
            )
        except Exception as err:
            result_queue.put({
                "event": "error",
                "message": (
                    f"Screenshot error: {err}"
                ),
            })
            break

        if not has_potential:
            empty_streak += 1
            result_queue.put({
                "event": "skipped",
                "post": post_number,
                "reason": "no @ symbol detected",
            })

            if empty_streak >= streak_limit:
                result_queue.put({
                    "event": "streak",
                    "count": empty_streak,
                })
                empty_streak = 0

            _scroll_down(scroll_amount)
            time.sleep(scroll_delay)
            continue

        try:
            emails = extract_emails_from_image(
                image,
                ocr_cfg,
            )
        except Exception as err:
            result_queue.put({
                "event": "error",
                "message": f"OCR error: {err}",
            })
            break

        post_has_new = False

        for email in emails:
            if (
                email in seen_emails
                or email in session_emails
            ):
                result_queue.put({
                    "event": "duplicate",
                    "post": post_number,
                    "email": email,
                })
                continue

            session_emails.add(email)
            total_found += 1
            post_has_new = True
            empty_streak = 0

            result_queue.put({
                "event": "found",
                "post": post_number,
                "email": email,
            })

        if not post_has_new and not emails:
            empty_streak += 1

            if empty_streak >= streak_limit:
                result_queue.put({
                    "event": "streak",
                    "count": empty_streak,
                })
                empty_streak = 0

        _scroll_down(scroll_amount)
        time.sleep(scroll_delay)

    result_queue.put({
        "event": "done",
        "total_found": total_found,
        "posts": max_posts,
        "emails": list(session_emails),
    })

    # Sentinel to signal thread completion
    result_queue.put(None)


def scroll_and_scrape(
    scraper_cfg: dict,
    workers: int = 2,
) -> Generator[dict, None, None]:
    """
    Non-blocking scrape generator for Streamlit.
    Runs the blocking loop in a background thread and
    yields events via a queue — prevents app crash.

    Event types yielded:
    {event: started}
    {event: skipped,   post: n, reason: str}
    {event: found,     post: n, email: str}
    {event: duplicate, post: n, email: str}
    {event: streak,    count: n}
    {event: done,      total_found: n, posts: n}
    {event: error,     message: str}
    """
    result_queue: queue.Queue = queue.Queue()

    thread = threading.Thread(
        target=_run_scrape_loop,
        args=(scraper_cfg, result_queue),
        daemon=True,
    )
    thread.start()

    while True:
        try:
            event = result_queue.get(timeout=60)
        except queue.Empty:
            yield {
                "event": "error",
                "message": (
                    "Scraping timed out. "
                    "Edge may have closed."
                ),
            }
            break

        if event is None:
            # Thread finished
            break

        yield event

        if event.get("event") in ("done", "error"):
            break

    thread.join(timeout=5)
