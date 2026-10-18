"""
Email Database & Scraper Helper
===============================
Provides email scraping from text, files, and directories,
along with domain-wise analysis, strict email validation,
and timestamped database versioning.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Union

# Standard project root and default storage path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "bin" / "data"
DEFAULT_STORAGE_FILE = DEFAULT_STORAGE_DIR / "Email_Storage.json"
DEFAULT_RECIPIENTS_FILE = PROJECT_ROOT / "data" / "config" / "recipients.json"

# Strict regex pattern for email address validation
EMAIL_STRICT_PATTERN = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

# Extraction pattern from free-flowing text
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+",
    re.IGNORECASE,
)


def is_valid_email(email: str) -> bool:
    """Validate if string is a strictly valid email address."""
    if not email or not isinstance(email, str):
        return False
    clean = email.strip()
    if len(clean) > 254 or " " in clean:
        return False
    if not EMAIL_STRICT_PATTERN.fullmatch(clean):
        return False
    # Ensure TLD is at least 2 chars
    tld = clean.split(".")[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def extract_emails_from_text(text: str) -> List[str]:
    """
    Extract, validate, and deduplicate all valid email addresses from any raw text,
    description, or scraped job posting. Filters out all invalid emails.
    """
    if not text:
        return []

    found = EMAIL_REGEX.findall(text)
    unique_emails: List[str] = []
    seen: Set[str] = set()

    for email in found:
        # Strip trailing punctuation
        clean_email = email.strip().strip(".,;:()<>[]\"'").lower()
        if clean_email and clean_email not in seen and is_valid_email(clean_email):
            seen.add(clean_email)
            unique_emails.append(clean_email)

    return sorted(unique_emails)


def scrape_emails_from_directory(dir_path: str | Path) -> Tuple[List[str], int]:
    """
    Scrape all valid email addresses from readable files in a directory/folder.
    Returns (list_of_unique_emails, files_scanned_count).
    """
    path = Path(dir_path).expanduser().resolve()
    if not path.is_dir():
        return [], 0

    all_emails: Set[str] = set()
    files_scanned = 0
    supported_extensions = {".txt", ".csv", ".json", ".md", ".log", ".py", ".html", ".eml"}

    for root, _, files in os.walk(path):
        for f in files:
            file_path = Path(root) / f
            if file_path.suffix.lower() in supported_extensions:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    extracted = extract_emails_from_text(content)
                    all_emails.update(extracted)
                    files_scanned += 1
                except Exception:
                    continue

    return sorted(list(all_emails)), files_scanned


def load_email_database(custom_path: str | Path | None = None) -> Dict[str, str]:
    """
    Load the email storage JSON database.
    """
    target = Path(custom_path) if custom_path else DEFAULT_STORAGE_FILE
    if not target.is_file():
        return {}

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def save_email_database(data: Dict[str, str], custom_path: str | Path | None = None) -> Path:
    """
    Save the email storage JSON database atomically.
    If custom_path is empty/None, defaults to bin/data/Email_Storage.json.
    """
    target = Path(custom_path) if custom_path else DEFAULT_STORAGE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_target = target.with_suffix(target.suffix + ".tmp")
    with open(temp_target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    temp_target.replace(target)
    return target


def save_email_database_with_timestamp(
    data: Dict[str, str],
    custom_dir: str | Path | None = None,
    custom_target_file: str | Path | None = None
) -> Tuple[Path, Path]:
    """
    Creates a new timestamped file:
        Email_Storage_YYYYMMDD_HHMMSS.json
    and also updates the active Email_Storage.json.
    Returns (timestamped_path, active_path).
    """
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_active = Path(custom_target_file) if custom_target_file else DEFAULT_STORAGE_FILE
    parent_dir = Path(custom_dir) if custom_dir else target_active.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    timestamped_file = parent_dir / f"Email_Storage_{now_str}.json"

    # 1. Save timestamped archive
    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    # 2. Update active storage file atomically
    active_saved = save_email_database(data, target_active)

    return timestamped_file, active_saved


def ingest_and_save_emails(
    raw_input: Union[str, List[str], Dict[str, Any]],
    custom_save_path: str | Path | None = None,
    create_timestamped_backup: bool = True,
) -> Dict[str, Any]:
    """
    Ingest emails from raw text, email list, or uploaded JSON dict,
    validates all addresses (filtering out invalid ones), merges with current database,
    and creates Email_Storage_<date_time>.json.

    Returns:
        dict with added_count, invalid_count, total_count, timestamped_file, unique_valid_emails
    """
    candidate_emails = []

    # Parse input based on type
    if isinstance(raw_input, dict):
        candidate_emails = list(raw_input.keys())
    elif isinstance(raw_input, list):
        candidate_emails = raw_input
    elif isinstance(raw_input, str):
        # Could be JSON string or raw text
        raw_str = raw_input.strip()
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, dict):
                    candidate_emails = list(parsed.keys())
                else:
                    candidate_emails = extract_emails_from_text(raw_str)
            except Exception:
                candidate_emails = extract_emails_from_text(raw_str)
        else:
            candidate_emails = extract_emails_from_text(raw_str)

    # Validate and filter
    valid_unique_emails: List[str] = []
    invalid_count = 0
    seen = set()

    for item in candidate_emails:
        clean = str(item).strip().strip(".,;:\"'<>[]()").lower()
        if is_valid_email(clean):
            if clean not in seen:
                seen.add(clean)
                valid_unique_emails.append(clean)
        else:
            invalid_count += 1

    # Load existing database
    current_db = load_email_database(custom_save_path)
    added_count = 0

    for email in valid_unique_emails:
        if email not in current_db:
            current_db[email] = ""  # New contact, not yet sent
            added_count += 1

    timestamped_path = None
    if create_timestamped_backup:
        timestamped_path, active_path = save_email_database_with_timestamp(
            data=current_db,
            custom_target_file=custom_save_path,
        )
    else:
        active_path = save_email_database(current_db, custom_save_path)

    return {
        "added_count": added_count,
        "invalid_count": invalid_count,
        "total_in_db": len(current_db),
        "valid_scraped": len(valid_unique_emails),
        "timestamped_file": str(timestamped_path) if timestamped_path else None,
        "active_file": str(active_path),
        "emails": valid_unique_emails,
    }


def group_emails_by_domain(data: Dict[str, str] | List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group email addresses domain-wise (e.g. capgemini.com, ey.com, gmail.com).
    Returns a dictionary mapping domain -> list of email objects.
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    if isinstance(data, dict):
        items = data.items()
    else:
        items = [(email, "") for email in data]

    for email, sent_date in items:
        clean_email = email.strip().lower()
        if "@" in clean_email:
            domain = clean_email.split("@", 1)[1]
        else:
            domain = "unknown"

        if domain not in grouped:
            grouped[domain] = []

        grouped[domain].append({
            "email": clean_email,
            "last_sent": sent_date or "Never",
        })

    # Sort domains by number of emails descending
    return dict(sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True))


def delete_emails_from_database(
    data: Dict[str, str],
    emails_or_text: List[str] | str
) -> Tuple[Dict[str, str], int]:
    """
    Delete email(s) from database.
    Accepts a list of emails OR a text script (which is scraped for emails to delete).
    Returns (updated_dict, count_deleted).
    """
    if isinstance(emails_or_text, str):
        target_emails = set(extract_emails_from_text(emails_or_text))
    else:
        target_emails = {e.strip().lower() for e in emails_or_text}

    new_data = {}
    deleted_count = 0

    for email, sent_date in data.items():
        if email.strip().lower() in target_emails:
            deleted_count += 1
        else:
            new_data[email] = sent_date

    return new_data, deleted_count
