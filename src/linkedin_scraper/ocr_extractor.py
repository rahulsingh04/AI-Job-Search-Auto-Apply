"""EasyOCR singleton and parallel email extraction from images."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import easyocr
import numpy as np
from PIL import Image

_READER: easyocr.Reader | None = None
_LOCK = threading.Lock()

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+",
    re.IGNORECASE,
)


def _is_valid_email(email: str) -> bool:
    """Validate email has proper TLD (2+ alpha chars)."""
    tld = email.split(".")[-1]
    return len(tld) >= 2 and tld.isalpha()


def get_ocr_reader(ocr_cfg: dict) -> easyocr.Reader:
    """
    Return singleton EasyOCR reader.
    Thread-safe. Loaded once, reused for all posts.
    """
    global _READER
    with _LOCK:
        if _READER is None:
            languages = ocr_cfg.get("languages", ["en"])
            use_gpu = ocr_cfg.get("use_gpu", False)
            _READER = easyocr.Reader(
                languages,
                gpu=use_gpu,
                verbose=False,
            )
    return _READER


def warm_up_ocr(ocr_cfg: dict) -> None:
    """
    Pre-load EasyOCR model at app startup in background.
    Eliminates first-call delay during scraping.
    """
    def _load():
        get_ocr_reader(ocr_cfg)

    thread = threading.Thread(
        target=_load,
        daemon=True,
    )
    thread.start()


def extract_emails_from_image(
    image: Image.Image,
    ocr_cfg: dict,
) -> list[str]:
    """
    Run EasyOCR on image and extract valid email addresses.
    Returns list of unique valid emails found.
    """
    reader = get_ocr_reader(ocr_cfg)
    img_array = np.array(image.convert("RGB"))

    results = reader.readtext(
        img_array,
        detail=0,
        paragraph=False,
    )

    full_text = " ".join(results)
    found = EMAIL_REGEX.findall(full_text)

    unique_emails: list[str] = []
    seen: set[str] = set()

    for email in found:
        clean = email.strip().lower()
        if clean not in seen and _is_valid_email(clean):
            seen.add(clean)
            unique_emails.append(clean)

    return unique_emails


def extract_emails_parallel(
    images: list[Image.Image],
    ocr_cfg: dict,
    workers: int = 2,
) -> list[list[str]]:
    """
    Run OCR on multiple screenshots simultaneously.
    Returns list of email lists, one per image.
    """
    results: list[list[str]] = [[] for _ in images]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_index = {
            pool.submit(
                extract_emails_from_image,
                image,
                ocr_cfg,
            ): index
            for index, image in enumerate(images)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception:
                results[index] = []

    return results
