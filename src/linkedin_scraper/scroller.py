"""Smart LinkedIn post scroller with email extraction."""

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_seen_emails() -> set[str]:
    """Load all emails already in Email_Storage.json."""
    import json
    storage_file = PROJECT_ROOT / "Email_Storage.json"
    if not storage_file.is_file():
        return set()
    try:
        with storage_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return set(data.keys())
    except Exception:
        pass
    return set()


def _scroll_down(scroll_amount: int) -> None:
    """Scroll down by given amount using pyautogui."""
    pyautogui.scroll(-scroll_amount)


def scroll_and_scrape(
    scraper_cfg: dict,
    workers: int = 2,
) -> Generator[dict, None, None]:
    """
    Smart scroll generator — yields progress events.

    Event types yielded:
    {"event": "started"}
    {"event": "skipped",   "post": n, "reason": str}
    {"event": "found",     "post": n, "email": str}
    {"event": "duplicate", "post": n, "email": str}
    {"event": "streak",    "count": n}
    {"event": "done",      "total_found": n, "posts": n}
    {"event": "error",     "message": str}
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

    yield {"event": "started"}

    window = find_edge_window()
    if window:
        focus_edge_window(window)
    time.sleep(post_wait)

    for post_number in range(1, max_posts + 1):
        region = get_edge_window_region()

        if region is None:
            yield {
                "event": "error",
                "message": (
                    "Edge window not found. "
                    "Please keep Edge open."
                ),
            }
            break

        image, has_potential = capture_and_check(region)

        if not has_potential:
            empty_streak += 1
            yield {
                "event": "skipped",
                "post": post_number,
                "reason": "no @ symbol detected",
            }

            if empty_streak >= streak_limit:
                yield {
                    "event": "streak",
                    "count": empty_streak,
                }
                empty_streak = 0

            _scroll_down(scroll_amount)
            time.sleep(scroll_delay)
            continue

        emails = extract_emails_from_image(
            image,
            ocr_cfg,
        )

        post_has_new = False

        for email in emails:
            if email in seen_emails:
                yield {
                    "event": "duplicate",
                    "post": post_number,
                    "email": email,
                }
                continue

            if email in session_emails:
                yield {
                    "event": "duplicate",
                    "post": post_number,
                    "email": email,
                }
                continue

            session_emails.add(email)
            total_found += 1
            post_has_new = True
            empty_streak = 0

            yield {
                "event": "found",
                "post": post_number,
                "email": email,
            }

        if not post_has_new and not emails:
            empty_streak += 1

            if empty_streak >= streak_limit:
                yield {
                    "event": "streak",
                    "count": empty_streak,
                }
                empty_streak = 0

        _scroll_down(scroll_amount)
        time.sleep(scroll_delay)

    yield {
        "event": "done",
        "total_found": total_found,
        "posts": max_posts,
        "emails": list(session_emails),
    }
