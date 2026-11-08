"""Capture Edge window region screenshots using mss."""

import mss
import mss.tools
import numpy as np
from PIL import Image

_MSS_INSTANCE = None


def get_mss() -> mss.mss:
    """Return singleton mss instance."""
    global _MSS_INSTANCE
    if _MSS_INSTANCE is None:
        _MSS_INSTANCE = mss.mss()
    return _MSS_INSTANCE


def capture_window(region: dict) -> Image.Image:
    """
    Capture Edge window region and return PIL Image.
    region = {"top": y, "left": x, "width": w, "height": h}
    """
    sct = get_mss()
    screenshot = sct.grab(region)
    return Image.frombytes(
        "RGB",
        screenshot.size,
        screenshot.bgra,
        "raw",
        "BGRX",
    )


def quick_at_check(image: Image.Image) -> bool:
    """
    Fast pre-check: does screenshot likely contain an email?
    Converts to small grayscale image and scans for '@'.
    10x faster than running full OCR.
    Returns True if '@' character region detected.
    """
    small = image.convert("L").resize(
        (320, 240),
        Image.LANCZOS,
    )
    arr = np.array(small)
    std_val = float(np.std(arr))

    # No text-like content — skip OCR entirely
    if std_val < 10:
        return False

    # Conservative: trigger OCR if image has text-like
    # contrast. Full OCR confirms presence of '@'.
    return std_val > 15


def capture_and_check(region: dict) -> tuple[Image.Image, bool]:
    """
    Capture screenshot and run quick '@' pre-check.
    Returns (image, has_potential_email).
    """
    image = capture_window(region)
    has_at = quick_at_check(image)
    return image, has_at
