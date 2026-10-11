import json
import os
from pathlib import Path


STORAGE_FILE = Path(
    os.getenv("EMAIL_STORAGE_FILE", "Email_Storage.json")
).expanduser()


def load_email_storage() -> dict:
    """Load existing recipient-to-date records."""

    if not STORAGE_FILE.exists():
        return {}

    try:
        with STORAGE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{STORAGE_FILE} contains invalid JSON. "
            "Correct or recover the file before sending."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{STORAGE_FILE} must contain a JSON object."
        )

    return data


def save_email_storage(email_data: dict) -> None:
    """Save history atomically to reduce partial-write risk."""

    STORAGE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_file = STORAGE_FILE.with_suffix(
        STORAGE_FILE.suffix + ".tmp"
    )

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(
            email_data,
            file,
            indent=4,
            ensure_ascii=False
        )

    temp_file.replace(STORAGE_FILE)
