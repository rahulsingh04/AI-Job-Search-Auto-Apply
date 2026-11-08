"""
Email Database & Scraper Helper
===============================
Provides multi-format database parsing (.json, .csv, .xlsx, .txt),
strict email validation, atomic persistence, timestamped backups,
domain-wise analysis, and multi-format exports.
"""

import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Union
import pandas as pd

# Standard project root and default storage path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_DIR = PROJECT_ROOT
DEFAULT_STORAGE_FILE = PROJECT_ROOT / "Email_Storage.json"


def resolve_database_path(custom_path: str | Path | None = None) -> Path:
    """
    Resolve a database file path:
    - If None, empty, or a package dependencies file (e.g. requirements.txt), returns DEFAULT_STORAGE_FILE.
    - If absolute, returns that absolute Path.
    - If relative, first checks PROJECT_ROOT / path, then cwd / path.
    """
    if not custom_path or "requirements.txt" in str(custom_path).lower():
        return DEFAULT_STORAGE_FILE
    p = Path(custom_path).expanduser()
    if p.is_absolute():
        return p
    # Check relative to PROJECT_ROOT
    cand_proj = (PROJECT_ROOT / p).resolve()
    if cand_proj.is_file():
        return cand_proj
    # Check relative to cwd
    cand_cwd = p.resolve()
    if cand_cwd.is_file():
        return cand_cwd
    return cand_proj


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
    # Ensure TLD is at least 2 chars and alphabetic
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
    Load the email storage database from disk (.txt, .json, .csv, .xlsx).
    Returns a sorted dictionary: {email: last_sent_date}.
    """
    target = resolve_database_path(custom_path) if custom_path else DEFAULT_STORAGE_FILE
    if not target.is_file():
        return {}

    try:
        content_bytes = target.read_bytes()
        return parse_email_database_content(content_bytes, target.name)
    except Exception:
        return {}


def save_email_database(data: Dict[str, str], custom_path: str | Path | None = None) -> Path:
    """
    Save the email storage database atomically in its native format (.txt, .json, .csv, .xlsx)
    in sorted order at the exact target location.
    """
    target = resolve_database_path(custom_path) if custom_path else DEFAULT_STORAGE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)

    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))
    temp_target = target.with_suffix(target.suffix + ".tmp")
    ext = target.suffix.lower()

    if ext == ".txt":
        lines = [f"{k}\t{v}" if v else k for k, v in sorted_data.items()]
        with open(temp_target, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + ("\n" if lines else ""))
    elif ext == ".csv":
        df = pd.DataFrame([{"email": k, "last_contacted_date": v} for k, v in sorted_data.items()])
        df.to_csv(temp_target, index=False)
    elif ext in (".xlsx", ".xls"):
        df = pd.DataFrame([{"email": k, "last_contacted_date": v} for k, v in sorted_data.items()])
        df.to_excel(temp_target, index=False)
    else:  # default to json
        with open(temp_target, "w", encoding="utf-8") as f:
            json.dump(sorted_data, f, indent=4, ensure_ascii=False)

    temp_target.replace(target)
    return target



def parse_email_database_content(content_bytes: bytes, filename: str) -> Dict[str, str]:
    """
    Parse an uploaded database file (.json, .csv, .xlsx, .xls, .txt)
    extracting emails and last_sent_date.
    Returns sorted Dict[str, str].
    """
    ext = Path(filename).suffix.lower()
    result: Dict[str, str] = {}

    if ext == ".json":
        try:
            data = json.loads(content_bytes.decode("utf-8", errors="ignore"))
            if isinstance(data, dict):
                for k, v in data.items():
                    clean_k = str(k).strip().lower()
                    if is_valid_email(clean_k):
                        result[clean_k] = str(v).strip() if v else ""
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        email = item.get("email") or item.get("email_id") or item.get("Email")
                        date_val = item.get("last_contacted_date") or item.get("date") or item.get("last_sent") or ""
                        if email and is_valid_email(str(email).strip().lower()):
                            result[str(email).strip().lower()] = str(date_val).strip() if date_val else ""
                    elif isinstance(item, str) and is_valid_email(item.strip().lower()):
                        result[item.strip().lower()] = ""
        except Exception:
            pass

    elif ext in (".csv", ".xlsx", ".xls"):
        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(content_bytes))
            else:
                df = pd.read_excel(io.BytesIO(content_bytes))

            # Locate email column
            email_col = None
            date_col = None

            for col in df.columns:
                c_clean = str(col).strip().lower()
                if "email" in c_clean or "mail" in c_clean:
                    email_col = col
                if any(w in c_clean for w in ["date", "time", "sent", "contact"]):
                    date_col = col

            # Fallback: find first column where at least one row looks like an email
            if email_col is None:
                for col in df.columns:
                    sample_vals = df[col].dropna().astype(str).head(10)
                    if any("@" in v for v in sample_vals):
                        email_col = col
                        break

            if email_col is not None:
                for _, row in df.iterrows():
                    val = str(row[email_col]).strip().lower()
                    if is_valid_email(val):
                        date_val = str(row[date_col]).strip() if (date_col and pd.notna(row[date_col])) else ""
                        if date_val.lower() in ("nan", "none", "nat", ""):
                            date_val = ""
                        result[val] = date_val
        except Exception:
            pass

    elif ext == ".txt":
        text = content_bytes.decode("utf-8", errors="ignore")
        # Line-by-line check if format is email, date
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            parts = re.split(r"[,;\t|]+", line_str)
            if len(parts) >= 2:
                e_cand = parts[0].strip().lower()
                d_cand = parts[1].strip()
                if is_valid_email(e_cand):
                    result[e_cand] = d_cand
                    continue
            # Regex fallback for the line
            for em in extract_emails_from_text(line_str):
                result[em] = ""

    # Sort alphabetically
    return dict(sorted(result.items(), key=lambda x: x[0]))


def export_email_database(data: Dict[str, str], format_type: str = "json") -> bytes:
    """
    Export the email database to bytes in the specified format: 'json', 'csv', 'xlsx', or 'txt'.
    """
    fmt = format_type.lower().strip().lstrip(".")
    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))

    if fmt == "csv":
        df = pd.DataFrame([
            {"email": k, "last_contacted_date": v}
            for k, v in sorted_data.items()
        ])
        return df.to_csv(index=False).encode("utf-8")

    elif fmt in ("xlsx", "excel"):
        buf = io.BytesIO()
        df = pd.DataFrame([
            {"email": k, "last_contacted_date": v}
            for k, v in sorted_data.items()
        ])
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Recipients")
        return buf.getvalue()

    elif fmt == "txt":
        lines = [f"{k}\t{v}" if v else k for k, v in sorted_data.items()]
        return "\n".join(lines).encode("utf-8")

    else:  # json
        return json.dumps(sorted_data, indent=4, ensure_ascii=False).encode("utf-8")


def save_email_database_with_timestamp(
    data: Dict[str, str],
    custom_dir: str | Path | None = None,
    custom_target_file: str | Path | None = None,
    ext: str = "json",
) -> Tuple[Path, Path]:
    """
    Creates a new timestamped backup file:
        Email_Storage_YYYYMMDD_HHMMSS.<ext>
    in the same storage directory, and updates the active storage file.
    Returns (timestamped_path, active_path).
    """
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_active = Path(custom_target_file) if custom_target_file else DEFAULT_STORAGE_FILE
    parent_dir = Path(custom_dir) if custom_dir else target_active.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))

    # 1. Save timestamped archive
    timestamped_file = parent_dir / f"Email_Storage_{now_str}.{ext.lstrip('.')}"
    content_bytes = export_email_database(sorted_data, ext)
    with open(timestamped_file, "wb") as f:
        f.write(content_bytes)

    # 2. Update active storage file atomically as JSON
    active_saved = save_email_database(sorted_data, target_active)

    return timestamped_file, active_saved


def open_database_file_dialog() -> str:
    """
    Open a native Windows file selection dialog to let the user navigate and choose
    a database file (.json, .csv, .xlsx, .xls, .txt).
    Uses a clean PowerShell subprocess so it never blocks or conflicts with GUI event loops.
    """
    import subprocess
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        "$f.Filter = 'Database Files (*.txt;*.json;*.csv;*.xlsx;*.xls)|*.txt;*.json;*.csv;*.xlsx;*.xls|All Files (*.*)|*.*'; "
        "$f.Title = 'Navigate & Choose Recipient Database File'; "
        "$f.InitialDirectory = (Get-Location).Path; "
        "$top = New-Object System.Windows.Forms.Form; "
        "$top.TopMost = $true; "
        "if ($f.ShowDialog($top) -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.FileName }"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=120,
        )
        picked = res.stdout.strip()
        if picked and Path(picked).is_file():
            return picked
    except Exception:
        pass

    # Secondary fallback to Tkinter if PowerShell unavailable
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        selected_file = filedialog.askopenfilename(
            title="Navigate & Choose Recipient Database File",
            filetypes=[
                ("Database Files (*.json, *.csv, *.xlsx, *.txt)", "*.json;*.csv;*.xlsx;*.xls;*.txt"),
                ("Text Files (*.txt)", "*.txt"),
                ("JSON Files (*.json)", "*.json"),
                ("CSV Files (*.csv)", "*.csv"),
                ("Excel Files (*.xlsx, *.xls)", "*.xlsx;*.xls"),
                ("All Files (*.*)", "*.*")
            ]
        )
        root.destroy()
        return selected_file
    except Exception:
        return ""



def load_database_from_location(file_path: str | Path) -> Tuple[Dict[str, str], str]:
    """
    Load email database from a specific file path on disk (.json, .csv, .xlsx, .xls, .txt).
    Returns (data_dict, status_message).
    """
    path = resolve_database_path(file_path)
    if not path.is_file():
        return {}, f"File not found: {path}"

    try:
        content_bytes = path.read_bytes()
        parsed = parse_email_database_content(content_bytes, path.name)
        return parsed, f"Loaded {len(parsed)} valid emails into memory from {path.name}"
    except Exception as e:
        return {}, f"Failed to read {path.name}: {e}"


def export_and_save_database_files(
    data: Dict[str, str],
    target_dir: str | Path | None = None,
    formats: List[str] | None = None,
) -> Dict[str, Path]:
    """
    Saves export snapshot files (.csv, .xlsx, .txt, .json) in the directory
    where the database is located, along with an automatic timestamped backup
    Email_Storage_<YYYYMMDD_HHMMSS>.json without asking.
    Returns dictionary mapping format -> saved Path.
    """
    dest_dir = Path(target_dir).resolve() if target_dir else DEFAULT_STORAGE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["csv", "xlsx", "txt", "json"]

    saved_files: Dict[str, Path] = {}
    sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))

    # Always save a timestamped backup without asking
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = dest_dir / f"Email_Storage_{now_str}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=4, ensure_ascii=False)
    saved_files["backup"] = backup_path

    # Save each requested export format in the database directory
    for fmt in formats:
        clean_fmt = fmt.lower().lstrip(".")
        filename = f"Email_Storage.{clean_fmt}"
        file_path = dest_dir / filename
        data_bytes = export_email_database(sorted_data, clean_fmt)
        with open(file_path, "wb") as f:
            f.write(data_bytes)
        saved_files[clean_fmt] = file_path

    return saved_files


def ingest_and_save_emails(
    raw_input: Union[str, bytes, List[str], Dict[str, Any]],
    filename: str = "",
    custom_save_path: str | Path | None = None,
    create_timestamped_backup: bool = True,
    backup_format: str | None = None,
) -> Dict[str, Any]:
    """
    Ingest emails from text, files (.json, .csv, .xlsx, .txt), or lists.
    Extracts all valid emails, creates a backup of the current database file first
    in the exact same location, then adds the updated emails into the current database
    in the same location (deduplicated, sorted alphabetically).
    """
    incoming_dict: Dict[str, str] = {}
    invalid_count = 0

    if isinstance(raw_input, bytes) and filename:
        incoming_dict = parse_email_database_content(raw_input, filename)
    elif isinstance(raw_input, dict):
        for k, v in raw_input.items():
            clean = str(k).strip().lower()
            if is_valid_email(clean):
                incoming_dict[clean] = str(v).strip() if v else ""
            else:
                invalid_count += 1
    elif isinstance(raw_input, list):
        for item in raw_input:
            clean = str(item).strip().lower()
            if is_valid_email(clean):
                incoming_dict[clean] = ""
            else:
                invalid_count += 1
    elif isinstance(raw_input, str):
        raw_str = raw_input.strip()
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        clean = str(k).strip().lower()
                        if is_valid_email(clean):
                            incoming_dict[clean] = str(v).strip() if v else ""
                        else:
                            invalid_count += 1
            except Exception:
                extracted = extract_emails_from_text(raw_str)
                for e in extracted:
                    incoming_dict[e] = ""
        else:
            extracted = extract_emails_from_text(raw_str)
            for e in extracted:
                incoming_dict[e] = ""

    # 1. Target database path: resolved to exact same location
    target_active = resolve_database_path(custom_save_path) if custom_save_path else DEFAULT_STORAGE_FILE
    parent_dir = target_active.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    # 2. Load CURRENT database from that exact location
    current_db = load_email_database(target_active)

    # 3. Create backup of current database in the SAME directory before updating
    timestamped_path = None
    if create_timestamped_backup and current_db:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = backup_format or target_active.suffix.lstrip(".") or "txt"
        timestamped_filename = f"{target_active.stem}_{now_str}.{ext.lstrip('.')}"
        timestamped_path = parent_dir / timestamped_filename
        
        backup_bytes = export_email_database(current_db, ext)
        with open(timestamped_path, "wb") as f:
            f.write(backup_bytes)

    # 4. Add new unique validated emails to database
    added_count = 0
    for email, date_val in incoming_dict.items():
        if email not in current_db:
            current_db[email] = date_val or ""
            added_count += 1
        elif date_val and not current_db[email]:
            current_db[email] = date_val

    # 5. Ensure clean alphabetical sort and save updated database to target_active at the SAME location
    sorted_db = dict(sorted(current_db.items(), key=lambda x: x[0].lower()))
    active_path = save_email_database(sorted_db, target_active)

    return {
        "added_count": added_count,
        "invalid_count": invalid_count,
        "total_in_db": len(sorted_db),
        "valid_scraped": len(incoming_dict),
        "timestamped_file": str(timestamped_path) if timestamped_path else None,
        "active_file": str(active_path),
        "emails": list(incoming_dict.keys()),
        "updated_db": sorted_db,
    }




def group_emails_by_domain(data: Dict[str, str] | List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group email addresses domain-wise (e.g. capgemini.com, ey.com, fractal.ai).
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


def filter_grouped_domains(
    grouped: Dict[str, List[Dict[str, Any]]],
    query: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Filter domain-grouped email database by either domain name or full email address.
    Supports:
    - Full email address (e.g. 'akash.sirohi@hireoneshot.com')
    - Email prefix/substring (e.g. 'akash.sirohi')
    - Domain name with or without leading @ (e.g. '@hireoneshot.com' or 'hireoneshot.com')
    - Partial domain name (e.g. 'hireoneshot')
    """
    if not query or not query.strip():
        return grouped

    q = query.strip().lower()
    q_domain = q.lstrip("@").strip()

    filtered: Dict[str, List[Dict[str, Any]]] = {}

    for domain, emails in grouped.items():
        domain_lower = domain.lower()
        # Case 1: Search query matches domain name (e.g. 'capgemini.com' or '@capgemini.com' or 'capgemini')
        if q_domain and q_domain in domain_lower:
            # Domain itself matches query: include all contacts under this domain
            filtered[domain] = emails
        else:
            # Case 2: Search query matches full email address or email username
            matching_emails = [
                e for e in emails
                if q in e["email"].lower() or (q_domain and q_domain in e["email"].lower())
            ]
            if matching_emails:
                filtered[domain] = matching_emails

    return filtered


def filter_database_by_query(data: Dict[str, str], query: str) -> Dict[str, str]:
    """Filter email database dictionary by full email address or domain name."""
    if not query or not query.strip():
        return data
    q = query.strip().lower()
    q_domain = q.lstrip("@").strip()
    return {
        email: date_val
        for email, date_val in data.items()
        if q in email.lower() or (q_domain and q_domain in (email.split("@")[-1].lower() if "@" in email else email.lower()))
    }


def get_domain_statistics(data: Dict[str, str]) -> Dict[str, Any]:
    """
    Compute domain breakdown metrics: total domains, total emails, contacted vs uncontacted.
    """
    grouped = group_emails_by_domain(data)
    total_emails = len(data)
    total_domains = len(grouped)
    contacted_count = sum(1 for v in data.values() if v and v.strip() and v.strip().lower() != "never")
    uncontacted_count = total_emails - contacted_count

    return {
        "total_emails": total_emails,
        "total_domains": total_domains,
        "contacted_count": contacted_count,
        "uncontacted_count": uncontacted_count,
        "grouped": grouped,
    }


def delete_emails_from_database(
    data: Dict[str, str],
    emails_or_text: List[str] | str
) -> Tuple[Dict[str, str], int]:
    """
    Delete email(s) from database.
    Accepts a list of emails OR a text script (which is scraped for emails to delete).
    Returns (updated_sorted_dict, count_deleted).
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

    sorted_data = dict(sorted(new_data.items(), key=lambda x: x[0].lower()))
    return sorted_data, deleted_count


def delete_domain_from_database(
    data: Dict[str, str],
    domain: str
) -> Tuple[Dict[str, str], int]:
    """
    Delete all contacts belonging to a specific domain.
    Returns (updated_sorted_dict, count_deleted).
    """
    target_domain = domain.strip().lower().lstrip("@")
    new_data = {}
    deleted_count = 0

    for email, sent_date in data.items():
        clean_email = email.strip().lower()
        email_domain = clean_email.split("@", 1)[1] if "@" in clean_email else ""
        if email_domain == target_domain:
            deleted_count += 1
        else:
            new_data[clean_email] = sent_date

    sorted_data = dict(sorted(new_data.items(), key=lambda x: x[0].lower()))
    return sorted_data, deleted_count


def update_email_in_database(
    data: Dict[str, str],
    old_email: str,
    new_email: str,
    new_date: str = ""
) -> Dict[str, str]:
    """
    Modify an email address or update its last contacted date in the database.
    """
    clean_old = old_email.strip().lower()
    clean_new = new_email.strip().lower()

    new_data = dict(data)
    if clean_old in new_data:
        del new_data[clean_old]

    if is_valid_email(clean_new):
        new_data[clean_new] = new_date.strip()

    return dict(sorted(new_data.items(), key=lambda x: x[0].lower()))
