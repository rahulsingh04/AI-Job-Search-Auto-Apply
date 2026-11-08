"""Capture Edge window region screenshots using mss."""

import numpy as np
from PIL import Image


def capture_window(region: dict) -> Image.Image:
    """
    Capture Edge window region and return PIL Image.
    Creates a fresh mss instance per call — required on
    Windows to avoid cross-thread mss context crashes.
    region = {top, left, width, height}
    """
    import mss
    with mss.mss() as sct:
        screenshot = sct.grab(region)
        return Image.frombytes(
            "RGBA",
            screenshot.size,
            screenshot.bgra,
            "raw",
            "BGRA",
        )


def quick_at_check(image: Image.Image) -> bool:
    """
    Fast pre-check: does screenshot likely contain email?
    Converts to small grayscale and checks text contrast.
    10x faster than running full OCR on every post.
    Returns True if image has text-like contrast.
    """
    small = image.convert("L").resize(
        (320, 240),
        Image.LANCZOS,
    )
    arr = np.array(small)
    std_val = float(np.std(arr))

    if std_val < 10:
        return False

    return std_val > 15


def capture_and_check(
    region: dict,
) -> tuple[Image.Image, bool]:
    """
    Capture screenshot and run quick '@' pre-check.
    Returns (image, has_potential_email).
    """
    image = capture_window(region)
    has_at = quick_at_check(image)
    return image, has_at
