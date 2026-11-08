import json
import os
from datetime import date
from pathlib import Path
from typing import Optional, Union

# Project root: AI-Job-Search-Auto-Apply (two levels up from src/email_sender)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORAGE_FILE = PROJECT_ROOT / "Email_Storage.json"


def get_storage_file() -> Path:
    """Resolve the storage file path, guaranteeing absolute path to project root."""
    env_path = os.getenv("EMAIL_STORAGE_FILE")
    if env_path:
        p = Path(env_path).expanduser()
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()
    return DEFAULT_STORAGE_FILE


# For backwards-compatibility with code importing STORAGE_FILE
STORAGE_FILE = get_storage_file()


def load_email_storage(custom_path: Optional[Union[Path, str]] = None) -> dict:
    """Load existing recipient-to-date records from storage."""
    target_file = Path(custom_path).resolve() if custom_path else get_storage_file()

    if not target_file.exists():
        return {}

    try:
        with target_file.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{target_file} contains invalid JSON. "
            "Correct or recover the file before sending."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{target_file} must contain a JSON object."
        )

    return data


def save_email_storage(email_data: dict, custom_path: Optional[Union[Path, str]] = None) -> Path:
    """Save history atomically to reduce partial-write risk."""
    target_file = Path(custom_path).resolve() if custom_path else get_storage_file()

    target_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temp_file = target_file.with_suffix(
        target_file.suffix + ".tmp"
    )

    # Sort keys for deterministic storage
    sorted_data = dict(sorted(email_data.items(), key=lambda x: str(x[0]).lower()))

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(
            sorted_data,
            file,
            indent=4,
            ensure_ascii=False
        )

    temp_file.replace(target_file)
    return target_file


def record_successful_send(
    recipient_email: str,
    sending_date: Optional[str] = None,
    custom_path: Optional[Union[Path, str]] = None,
) -> dict:
    """
    Immediately record a successfully sent email to Email_Storage.json (and optional custom path).
    Updates recipient with sending_date (defaults to today's date YYYY-MM-DD).
    Returns the updated database dictionary.
    """
    sent_date = sending_date or date.today().strftime("%Y-%m-%d")
    clean_email = recipient_email.strip().lower()

    # 1. Always update master Email_Storage.json
    main_file = get_storage_file()
    main_data = load_email_storage(main_file)
    main_data[clean_email] = sent_date
    save_email_storage(main_data, main_file)

    # 2. If a custom database path is specified and different, update it too
    if custom_path:
        custom_file = Path(custom_path).resolve()
        if custom_file != main_file.resolve():
            try:
                from email_db_helper import load_email_database, save_email_database
                custom_data = load_email_database(custom_file)
                custom_data[clean_email] = sent_date
                save_email_database(custom_data, custom_file)
            except Exception:
                pass

    return main_data
