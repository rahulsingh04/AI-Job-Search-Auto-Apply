#!/usr/bin/env bash
# banner_and_cleanup.sh
# Project banner display and post-app cleanup logic.
# Requires: colors_and_utils.sh sourced first.
# Requires: PROJECT_ROOT, ACTIVE_PY set by caller.

show_project_banner() {
    printf '\n%b\n' "${CYAN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}${GREEN}AI JOB SEARCH & AUTO-APPLY${NC}  ${CYAN}— Your Career Automation Workspace${NC}  ${CYAN}║${NC}"
    printf '%b\n' "${CYAN}╠══════════════════════════════════════════════════════════════════════════╣${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}PROJECT${NC}  AI-Job-Search-Auto-Apply                                      ${CYAN}║${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}AUTHOR${NC}   Rahul Singh                                                   ${CYAN}║${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}CONTACT${NC}  javarahul04@gmail.com                                        ${CYAN}║${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}GITHUB${NC}   https://github.com/rahulsingh04/AI-Job-Search-Auto-Apply       ${CYAN}║${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}ROOT${NC}     $(safe_path "$PROJECT_ROOT")"
    printf '%b\n\n' "${CYAN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"
}

run_post_app_cleanup() {
    printf '\n%b\n' "${CYAN}╔══════════════════════════════════════════════════════════════════════════╗${NC}"
    printf '%b\n' "${CYAN}║${NC}  ${BOLD}APPLICATION CLOSED — STARTING CLEANUP${NC}                               ${CYAN}║${NC}"
    printf '%b\n\n' "${CYAN}╚══════════════════════════════════════════════════════════════════════════╝${NC}"

    if ! "$ACTIVE_PY" - "$PROJECT_ROOT" <<'PY_CLEANUP'
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

root = Path(sys.argv[1]).resolve()

storage_setting = os.environ.get("EMAIL_STORAGE_FILE", "Email_Storage.json").strip() or "Email_Storage.json"
storage_path = Path(storage_setting).expanduser()
if not storage_path.is_absolute():
    storage_path = root / storage_path
storage_path = storage_path.resolve()

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)"
    r"+[A-Za-z]{2,63}$"
)
DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%Y.%m.%d",
    "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%d-%b-%Y", "%d %b %Y", "%d %B %Y",
    "%B %d, %Y", "%b %d, %Y",
)

def valid_email(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value or len(value) > 254 or value.count("@") != 1:
        return False
    local, domain = value.rsplit("@", 1)
    if (
        not local or len(local) > 64 or local.startswith(".")
        or local.endswith(".") or ".." in local
        or not domain or len(domain) > 253
    ):
        return False
    if not EMAIL_RE.fullmatch(value):
        return False
    labels = domain.split(".")
    return all(
        label and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        for label in labels
    )

def normalize_date(value):
    if value is None:
        return "unsent", ""
    raw = str(value).strip()
    if not raw:
        return "unsent", ""
    if raw.lower() == "never":
        return "unsent", "Never"
    parsed = None
    try:
        parsed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        ).date()
    except (ValueError, TypeError):
        for fmt in DATE_FORMATS:
            try:
                parsed = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
    if parsed is None:
        return "unknown", raw
    return "date", parsed.strftime("%Y-%m-%d")

def merge_values(old_status, old_value, new_status, new_value):
    if old_status == "unknown":
        return old_status, old_value
    if new_status == "unknown":
        return new_status, new_value
    if old_status == "date" and new_status == "date":
        return (
            (old_status, old_value)
            if old_value >= new_value
            else (new_status, new_value)
        )
    if old_status == "date":
        return old_status, old_value
    if new_status == "date":
        return new_status, new_value
    if old_value == "Never" or new_value == "Never":
        return "unsent", "Never"
    return "unsent", ""

storage_ok = False
if not storage_path.is_file():
    print(f"[WARN] Active email history not found: {storage_path}")
    print("[WARN] Timestamped history files will be preserved.")
else:
    try:
        with storage_path.open("r", encoding="utf-8-sig") as h:
            original = json.load(h)
        if not isinstance(original, dict):
            raise ValueError(
                "Email history must be a JSON object."
            )

        cleaned = {}
        statuses = {}
        dropped_emails = 0
        repaired_dates = 0
        duplicate_keys = 0
        unknown_dates = []

        for raw_email, raw_date in original.items():
            if not valid_email(raw_email):
                dropped_emails += 1
                print(
                    f"[EMAIL HISTORY] Dropping invalid: "
                    f"{raw_email!r}"
                )
                continue
            canonical_email = raw_email.strip().lower()
            status, normalized_value = normalize_date(raw_date)
            if (
                status == "date"
                and normalized_value != str(raw_date).strip()
            ):
                repaired_dates += 1
            if status == "unknown":
                unknown_dates.append(
                    (canonical_email, normalized_value)
                )
            if canonical_email in cleaned:
                duplicate_keys += 1
                old_status = statuses[canonical_email]
                old_value = cleaned[canonical_email]
                status, normalized_value = merge_values(
                    old_status, old_value,
                    status, normalized_value,
                )
            cleaned[canonical_email] = normalized_value
            statuses[canonical_email] = status

        changed = cleaned != original
        if changed:
            backup_root = (
                Path(tempfile.gettempdir())
                / "AI-Job-Search-Auto-Apply-cleanup-recovery"
            )
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )
            backup_path = backup_root / (
                f"{storage_path.stem}_pre_cleanup_{stamp}"
                f"{storage_path.suffix or '.json'}"
            )
            shutil.copy2(storage_path, backup_path)
            temp_path = storage_path.with_name(
                storage_path.name + ".cleanup.tmp"
            )
            try:
                with temp_path.open(
                    "w", encoding="utf-8", newline="\n"
                ) as h:
                    json.dump(
                        cleaned, h,
                        ensure_ascii=False, indent=4,
                    )
                    h.write("\n")
                os.replace(temp_path, storage_path)
            finally:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            print(
                f"[EMAIL HISTORY] Updated: {storage_path}"
            )
            print(
                f"[EMAIL HISTORY] Recovery backup: "
                f"{backup_path}"
            )
        else:
            print(
                f"[EMAIL HISTORY] No changes needed: "
                f"{storage_path}"
            )

        print(
            f"[EMAIL HISTORY] Records retained: "
            f"{len(cleaned)}"
        )
        print(
            f"[EMAIL HISTORY] Invalid keys dropped: "
            f"{dropped_emails}"
        )
        print(
            f"[EMAIL HISTORY] Dates normalized: "
            f"{repaired_dates}"
        )
        print(
            f"[EMAIL HISTORY] Duplicate keys merged: "
            f"{duplicate_keys}"
        )
        if unknown_dates:
            print(
                f"[WARN] {len(unknown_dates)} record(s) "
                f"have unrecognized dates; preserved:"
            )
            for email, value in unknown_dates:
                print(f"        {email}: {value!r}")
        storage_ok = True
    except Exception as exc:
        print(
            f"[ERROR] Could not normalize email history: "
            f"{type(exc).__name__}: {exc}"
        )
        print("[WARN] Timestamped files preserved for recovery.")

def is_old_email_history(name):
    low = name.lower()
    if re.fullmatch(
        r"email_storage_\d{8}(?:[_-]\d{6})?.*"
        r"\.json(?:\..*)?",
        low,
    ):
        return True
    if re.fullmatch(
        r"email_storage\.json(?:_(?:time|timestamp|backup"
        r"|bak|old|20\d{6}).*|\."
        r"(?:time|timestamp|backup|bak|old|tmp|20\d{6}).*)",
        low,
    ):
        return True
    return False

if storage_ok:
    removed_history_files = 0
    active_resolved = storage_path.resolve()
    for candidate in root.iterdir():
        try:
            if (
                candidate.is_file()
                and candidate.resolve() != active_resolved
                and is_old_email_history(candidate.name)
            ):
                candidate.unlink()
                removed_history_files += 1
                print(
                    f"[EMAIL HISTORY] Deleted old file: "
                    f"{candidate.name}"
                )
        except OSError as exc:
            print(f"[WARN] Could not delete {candidate}: {exc}")
    print(
        f"[EMAIL HISTORY] Old files deleted: "
        f"{removed_history_files}"
    )

cache_dir_names = {
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".hypothesis",
}
skip_dir_names = {
    ".git", ".venv", "venv", "env", "envs",
    "node_modules", "site-packages", ".tox",
}
removed_cache_dirs = 0
removed_bytecode = 0
for current, dirs, files in os.walk(root):
    dirs[:] = [
        name for name in dirs
        if name not in skip_dir_names
    ]
    current_path = Path(current)
    for directory in list(dirs):
        if directory in cache_dir_names:
            target = current_path / directory
            try:
                shutil.rmtree(target)
                removed_cache_dirs += 1
                dirs.remove(directory)
            except OSError as exc:
                print(
                    f"[WARN] Could not remove cache "
                    f"{target}: {exc}"
                )
    for filename in files:
        if filename.endswith((".pyc", ".pyo")):
            target = current_path / filename
            try:
                target.unlink()
                removed_bytecode += 1
            except OSError as exc:
                print(
                    f"[WARN] Could not remove bytecode "
                    f"{target}: {exc}"
                )

print(
    f"[PYTHON CACHE] Cache dirs removed: "
    f"{removed_cache_dirs}"
)
print(
    f"[PYTHON CACHE] .pyc/.pyo files removed: "
    f"{removed_bytecode}"
)
print("[PYTHON CACHE] Environments preserved.")
PY_CLEANUP
    then
        print_ok "Email history and Python-cache cleanup completed."
    else
        print_warn "Cleanup script returned an error; review messages above."
    fi

    if "$ACTIVE_PY" -m pip cache purge; then
        print_ok "Pip cache purged."
    else
        print_warn "Could not purge pip cache."
    fi

    local conda_cmd=""
    if [ -n "${CONDA_EXE:-}" ]; then
        conda_cmd="$CONDA_EXE"
        if command -v cygpath >/dev/null 2>&1; then
            conda_cmd="$(cygpath -u "$CONDA_EXE" 2>/dev/null \
                || printf '%s' "$CONDA_EXE")"
        fi
    fi
    if [ -z "$conda_cmd" ] && command -v conda >/dev/null 2>&1; then
        conda_cmd="$(command -v conda)"
    elif [ -z "$conda_cmd" ] \
        && command -v conda.exe >/dev/null 2>&1; then
        conda_cmd="$(command -v conda.exe)"
    fi
    if [ -n "$conda_cmd" ]; then
        if "$conda_cmd" clean --all --yes; then
            print_ok "Conda caches cleaned; environments preserved."
        else
            print_warn "Conda cache cleanup failed."
        fi
    else
        print_warn "Conda not found; skipping Conda-cache cleanup."
    fi

    if [ "$LAUNCHER_CREATED_ENVIRONMENT" = "true" ] \
        && [ -n "$LAUNCHER_CREATED_ENVIRONMENT_PATH" ]; then
        case "$LAUNCHER_CREATED_ENVIRONMENT_PATH" in
            "$PROJECT_ROOT"/*)
                if [ -f \
                    "$LAUNCHER_CREATED_ENVIRONMENT_PATH\
/.launcher-created-by-run-sh" ]; then
                    rm -rf -- "$LAUNCHER_CREATED_ENVIRONMENT_PATH"
                    print_ok "Removed launcher-created environment."
                else
                    print_warn \
                        "Env deletion skipped: ownership marker missing."
                fi
                ;;
            *)
                print_warn \
                    "Env deletion refused: path outside project root."
                ;;
        esac
    else
        print_ok "No environment created by this run; existing preserved."
    fi

    printf '%b\n' \
        "${GREEN}${BOLD}Cleanup complete. Thank you!${NC}"
}
