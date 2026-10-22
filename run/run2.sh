#!/usr/bin/env bash
# ================================================================================
# AI Job Search & Auto-Apply — Environment, Ollama Model & App Launcher (run/run2.sh)
# Project:  AI-Job-Search-Auto-Apply
# Author:   Rahul Singh
# Contact:  javarahul04@gmail.com
# GitHub:   https://github.com/rahulsingh04/AI-Job-Search-Auto-Apply
#
# Flow:
#   1. Detect/install Ollama, list local models, and let the user choose:
#        1) Use an installed model
#        2) Download and use another model
#        3) Continue without local LLM (application fallback paths)
#   2. Find a compatible Python interpreter / virtual environment
#   3. Safely update both model_config.json and project_config.json
#   4. Install project dependencies from pyproject.toml
#   5. Launch Streamlit
#
# NOTE: Option 3 disables local LLM use through the model configuration. It does
# not uninstall Python packages declared in pyproject.toml.
# ================================================================================

set -Eeuo pipefail

# ANSI colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

safe_path() { printf '%s' "$1" | tr '\\' '/'; }
print_error() { printf '%b\n' "${RED}[ERROR] $*${NC}" >&2; }
print_ok() { printf '%b\n' "${GREEN}[OK] $*${NC}"; }
print_warn() { printf '%b\n' "${YELLOW}[WARN] $*${NC}"; }

# The current launcher reuses existing Python/Conda/venv environments; it does
# not create one. These flags allow safe cleanup if a future launcher step does.
APP_LAUNCHED="false"
CLEANUP_DONE="false"
LAUNCHER_CREATED_ENVIRONMENT="false"
LAUNCHER_CREATED_ENVIRONMENT_PATH=""

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

    # Normalize the active email history first. A recovery copy is stored in the
    # operating system temp directory if records need to be changed.
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

# Respect the same setting used by src/email_sender/storage.py.
storage_setting = os.environ.get("EMAIL_STORAGE_FILE", "Email_Storage.json").strip() or "Email_Storage.json"
storage_path = Path(storage_setting).expanduser()
if not storage_path.is_absolute():
    storage_path = root / storage_path
storage_path = storage_path.resolve()

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
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
    return all(label and len(label) <= 63 and not label.startswith("-") and not label.endswith("-") for label in labels)

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
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        for fmt in DATE_FORMATS:
            try:
                parsed = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
    if parsed is None:
        # Preserve unknown non-empty values: the sender should stop rather than
        # interpreting a potentially-sent email as unsent and sending a duplicate.
        return "unknown", raw
    return "date", parsed.strftime("%Y-%m-%d")

def merge_values(old_status, old_value, new_status, new_value):
    # Prefer an unparseable date over a send-permitting blank when records collide.
    if old_status == "unknown":
        return old_status, old_value
    if new_status == "unknown":
        return new_status, new_value
    if old_status == "date" and new_status == "date":
        return (old_status, old_value) if old_value >= new_value else (new_status, new_value)
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
    print("[WARN] Timestamped history files will be preserved in case they are recovery copies.")
else:
    try:
        with storage_path.open("r", encoding="utf-8-sig") as handle:
            original = json.load(handle)
        if not isinstance(original, dict):
            raise ValueError("Email history must be a JSON object mapping email addresses to dates.")

        cleaned = {}
        statuses = {}
        dropped_emails = 0
        repaired_dates = 0
        duplicate_keys = 0
        unknown_dates = []

        for raw_email, raw_date in original.items():
            if not valid_email(raw_email):
                dropped_emails += 1
                print(f"[EMAIL HISTORY] Dropping invalid email key: {raw_email!r}")
                continue
            canonical_email = raw_email.strip().lower()
            status, normalized_value = normalize_date(raw_date)
            if status == "date" and normalized_value != str(raw_date).strip():
                repaired_dates += 1
            if status == "unknown":
                unknown_dates.append((canonical_email, normalized_value))
            if canonical_email in cleaned:
                duplicate_keys += 1
                old_status = statuses[canonical_email]
                old_value = cleaned[canonical_email]
                status, normalized_value = merge_values(
                    old_status, old_value, status, normalized_value
                )
            cleaned[canonical_email] = normalized_value
            statuses[canonical_email] = status

        changed = cleaned != original
        if changed:
            backup_root = Path(tempfile.gettempdir()) / "AI-Job-Search-Auto-Apply-cleanup-recovery"
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = backup_root / f"{storage_path.stem}_pre_cleanup_{stamp}{storage_path.suffix or '.json'}"
            shutil.copy2(storage_path, backup_path)
            temp_path = storage_path.with_name(storage_path.name + ".cleanup.tmp")
            try:
                with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(cleaned, handle, ensure_ascii=False, indent=4)
                    handle.write("\n")
                os.replace(temp_path, storage_path)
            finally:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            print(f"[EMAIL HISTORY] Updated active file: {storage_path}")
            print(f"[EMAIL HISTORY] Recovery backup kept outside the project: {backup_path}")
        else:
            print(f"[EMAIL HISTORY] No normalization changes needed: {storage_path}")

        print(f"[EMAIL HISTORY] Records retained: {len(cleaned)}")
        print(f"[EMAIL HISTORY] Invalid email keys dropped: {dropped_emails}")
        print(f"[EMAIL HISTORY] Dates normalized: {repaired_dates}")
        print(f"[EMAIL HISTORY] Duplicate email keys merged: {duplicate_keys}")
        if unknown_dates:
            print(f"[WARN] {len(unknown_dates)} record(s) have unrecognized non-empty dates; preserved to prevent accidental duplicate sending:")
            for email, value in unknown_dates:
                print(f"        {email}: {value!r}")
        storage_ok = True
    except Exception as exc:
        print(f"[ERROR] Could not safely normalize email history: {type(exc).__name__}: {exc}")
        print("[WARN] Timestamped email history files will be preserved for recovery.")

# Delete timestamped / temporary email-history files in the project root only,
# and only after successfully reading/normalizing the active history.
def is_old_email_history(name):
    low = name.lower()
    if re.fullmatch(r"email_storage_\d{8}(?:[_-]\d{6})?.*\.json(?:\..*)?", low):
        return True
    if re.fullmatch(r"email_storage\.json(?:_(?:time|timestamp|backup|bak|old|20\d{6}).*|\.(?:time|timestamp|backup|bak|old|tmp|20\d{6}).*)", low):
        return True
    return False

if storage_ok:
    removed_history_files = 0
    active_resolved = storage_path.resolve()
    for candidate in root.iterdir():
        try:
            if candidate.is_file() and candidate.resolve() != active_resolved and is_old_email_history(candidate.name):
                candidate.unlink()
                removed_history_files += 1
                print(f"[EMAIL HISTORY] Deleted old timestamped file: {candidate.name}")
        except OSError as exc:
            print(f"[WARN] Could not delete {candidate}: {exc}")
    print(f"[EMAIL HISTORY] Old timestamped files deleted: {removed_history_files}")

# Remove Python-generated cache folders and bytecode within the project only.
# Existing environments, Git metadata, node_modules, and site-packages are skipped.
cache_dir_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis"}
skip_dir_names = {".git", ".venv", "venv", "env", "envs", "node_modules", "site-packages", ".tox"}
removed_cache_dirs = 0
removed_bytecode = 0
for current, dirs, files in os.walk(root):
    dirs[:] = [name for name in dirs if name not in skip_dir_names]
    current_path = Path(current)
    for directory in list(dirs):
        if directory in cache_dir_names:
            target = current_path / directory
            try:
                shutil.rmtree(target)
                removed_cache_dirs += 1
                dirs.remove(directory)
            except OSError as exc:
                print(f"[WARN] Could not remove Python cache directory {target}: {exc}")
    for filename in files:
        if filename.endswith((".pyc", ".pyo")):
            target = current_path / filename
            try:
                target.unlink()
                removed_bytecode += 1
            except OSError as exc:
                print(f"[WARN] Could not remove bytecode {target}: {exc}")

print(f"[PYTHON CACHE] Cache directories removed: {removed_cache_dirs}")
print(f"[PYTHON CACHE] .pyc/.pyo files removed: {removed_bytecode}")
print("[PYTHON CACHE] Existing environment directories were preserved.")
PY_CLEANUP
    then
        print_ok "Email history and project Python-cache cleanup completed."
    else
        print_warn "The email-history/cache cleanup script returned an error; review the messages above."
    fi

    # Clear pip's download/wheel cache for the interpreter used by this launcher.
    if "$ACTIVE_PY" -m pip cache purge; then
        print_ok "Pip cache purged for the active Python interpreter."
    else
        print_warn "Could not purge pip cache (pip cache purge may be unsupported for this interpreter)."
    fi

    # Clear Conda package/download/index caches if Conda is installed. This does
    # NOT remove Conda environments or packages already installed in environments.
    local conda_cmd=""
    if [ -n "${CONDA_EXE:-}" ]; then
        conda_cmd="$CONDA_EXE"
        if command -v cygpath >/dev/null 2>&1; then
            conda_cmd="$(cygpath -u "$CONDA_EXE" 2>/dev/null || printf '%s' "$CONDA_EXE")"
        fi
    fi
    if [ -z "$conda_cmd" ] && command -v conda >/dev/null 2>&1; then
        conda_cmd="$(command -v conda)"
    elif [ -z "$conda_cmd" ] && command -v conda.exe >/dev/null 2>&1; then
        conda_cmd="$(command -v conda.exe)"
    fi
    if [ -n "$conda_cmd" ]; then
        if "$conda_cmd" clean --all --yes; then
            print_ok "Conda caches cleaned; installed Conda environments were preserved."
        else
            print_warn "Conda cache cleanup failed or was unavailable."
        fi
    else
        print_warn "Conda was not found; skipping Conda-cache cleanup."
    fi

    # Delete an environment only if this launcher explicitly created it during
    # this run, recorded its path, and placed it inside the project root. The
    # current launcher creates no environment, so existing environments remain.
    if [ "$LAUNCHER_CREATED_ENVIRONMENT" = "true" ] && [ -n "$LAUNCHER_CREATED_ENVIRONMENT_PATH" ]; then
        case "$LAUNCHER_CREATED_ENVIRONMENT_PATH" in
            "$PROJECT_ROOT"/*)
                if [ -f "$LAUNCHER_CREATED_ENVIRONMENT_PATH/.launcher-created-by-run-sh" ]; then
                    rm -rf -- "$LAUNCHER_CREATED_ENVIRONMENT_PATH"
                    print_ok "Removed the environment created by this launcher run."
                else
                    print_warn "Environment deletion skipped: launcher ownership marker was not found."
                fi
                ;;
            *)
                print_warn "Environment deletion refused because its path is outside the project root."
                ;;
        esac
    else
        print_ok "No environment was created by this launcher run; existing environments were preserved."
    fi

    printf '%b\n' "${GREEN}${BOLD}Cleanup complete. Thank you for using AI-Job-Search-Auto-Apply!${NC}"
}

# Run post-app cleanup on normal closure and Ctrl+C/ordinary shell exit after the
# app has launched. Earlier launcher failures will not trigger destructive cleanup.
launcher_exit_trap() {
    local original_status=$?
    trap - EXIT
    if [ "$APP_LAUNCHED" = "true" ] && [ "$CLEANUP_DONE" != "true" ]; then
        CLEANUP_DONE="true"
        run_post_app_cleanup || print_warn "Some cleanup tasks could not be completed."
    fi
    exit "$original_status"
}
trap launcher_exit_trap EXIT

# ------------------------------------------------------------------------------
# Locate the project root
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../app.py" ] && [ -f "$SCRIPT_DIR/../data/config/project_config.json" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    print_error "Cannot locate the project root (pyproject.toml was not found)."
    exit 1
fi
cd "$PROJECT_ROOT"

show_project_banner

# ------------------------------------------------------------------------------
# STEP 1: Locate / install Ollama, run `ollama list`, and choose the LLM mode
# ------------------------------------------------------------------------------
OLLAMA_BIN=""
OLLAMA_ENABLED="false"
SELECTED_MODEL=""
OLLAMA_LIST_RAW=""
MODEL_NAMES=()

resolve_ollama() {
    local found="" local_app_data="" candidate=""

    if command -v ollama >/dev/null 2>&1; then
        OLLAMA_BIN="$(command -v ollama)"
        return 0
    fi
    if command -v ollama.exe >/dev/null 2>&1; then
        OLLAMA_BIN="$(command -v ollama.exe)"
        return 0
    fi

    # Refresh common install directories in Git Bash / MSYS after installation.
    if [ -n "${LOCALAPPDATA:-}" ]; then
        local_app_data="$LOCALAPPDATA"
        if command -v cygpath >/dev/null 2>&1; then
            local_app_data="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || printf '%s' "$LOCALAPPDATA")"
        fi
        PATH="$local_app_data/Programs/Ollama:$PATH"
        candidate="$local_app_data/Programs/Ollama/ollama.exe"
        if [ -f "$candidate" ]; then
            OLLAMA_BIN="$candidate"
            export PATH
            return 0
        fi
    fi

    for candidate in "/c/Program Files/Ollama/ollama.exe" "/c/Users/${USERNAME:-}/AppData/Local/Programs/Ollama/ollama.exe"; do
        if [ -f "$candidate" ]; then
            OLLAMA_BIN="$candidate"
            return 0
        fi
    done

    return 1
}

install_ollama() {
    local os_name
    os_name="$(uname -s 2>/dev/null || printf 'unknown')"
    printf '%b\n' "${YELLOW}Ollama CLI was not found. Attempting to install Ollama...${NC}"

    case "$os_name" in
        MINGW*|MSYS*|CYGWIN*)
            if command -v winget.exe >/dev/null 2>&1; then
                winget.exe install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements || return 1
            elif command -v winget >/dev/null 2>&1; then
                winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements || return 1
            elif command -v powershell.exe >/dev/null 2>&1; then
                powershell.exe -NoProfile -ExecutionPolicy Bypass -Command 'irm https://ollama.com/install.ps1 | iex' || return 1
            else
                print_error "Neither winget nor PowerShell was found. Install Ollama from https://ollama.com/download/windows ."
                return 1
            fi
            ;;
        Linux*)
            if ! command -v curl >/dev/null 2>&1; then
                print_error "curl is required to install Ollama. Install curl and rerun this script."
                return 1
            fi
            curl -fsSL https://ollama.com/install.sh | sh || return 1
            ;;
        Darwin*)
            if ! command -v curl >/dev/null 2>&1; then
                print_error "curl is required to install Ollama. Install curl and rerun this script."
                return 1
            fi
            curl -fsSL https://ollama.com/install.sh | sh || return 1
            ;;
        *)
            print_error "Automatic Ollama installation is unsupported on '$os_name'. Install Ollama from https://ollama.com/download and rerun this script."
            return 1
            ;;
    esac

    # The current shell may not have received the PATH changes made by the installer.
    resolve_ollama
}

parse_model_names() {
    local raw="$1"
    MODEL_NAMES=()
    while IFS= read -r model_line; do
        model_line="$(printf '%s' "$model_line" | tr -d '\r')"
        [ -n "$model_line" ] && MODEL_NAMES+=("$model_line")
    done < <(printf '%s\n' "$raw" | awk 'NR > 1 && NF { print $1 }')
}

refresh_ollama_list() {
    local attempt=0 output=""
    if output="$("$OLLAMA_BIN" list 2>&1)"; then
        OLLAMA_LIST_RAW="$output"
        parse_model_names "$OLLAMA_LIST_RAW"
        return 0
    fi

    print_warn "Ollama CLI was found, but the local Ollama server did not respond. Attempting to start it..."
    # Starting `serve` is only attempted after `ollama list` failed.
    ( nohup "$OLLAMA_BIN" serve > "$PROJECT_ROOT/ollama-serve.log" 2>&1 </dev/null & ) || true

    while [ "$attempt" -lt 20 ]; do
        sleep 1
        attempt=$((attempt + 1))
        if output="$("$OLLAMA_BIN" list 2>&1)"; then
            OLLAMA_LIST_RAW="$output"
            parse_model_names "$OLLAMA_LIST_RAW"
            return 0
        fi
    done

    OLLAMA_LIST_RAW="$output"
    return 1
}

show_model_list() {
    printf '%b\n' "${CYAN}Current output of 'ollama list':${NC}"
    if [ -n "$OLLAMA_LIST_RAW" ]; then
        printf '%s\n' "$OLLAMA_LIST_RAW"
    else
        printf '%s\n' "(No model list is available.)"
    fi
}

find_installed_name() {
    local requested="$1" model=""
    for model in "${MODEL_NAMES[@]}"; do
        if [ "$model" = "$requested" ]; then
            printf '%s' "$model"
            return 0
        fi
    done
    # Ollama treats a model without an explicit tag as :latest.
    if [[ "$requested" != *:* ]]; then
        for model in "${MODEL_NAMES[@]}"; do
            if [ "$model" = "$requested:latest" ]; then
                printf '%s' "$model"
                return 0
            fi
        done
    fi
    return 1
}

select_installed_model() {
    local idx answer resolved=""
    if [ "${#MODEL_NAMES[@]}" -eq 0 ]; then
        print_error "No local models are installed. Choose option 2 to download a model, or option 3 to continue without an LLM."
        return 1
    fi

    if [ "${#MODEL_NAMES[@]}" -eq 1 ]; then
        SELECTED_MODEL="${MODEL_NAMES[0]}"
        print_ok "Selected installed model: $SELECTED_MODEL"
        return 0
    fi

    printf '%b\n' "${CYAN}Select an installed model:${NC}"
    for idx in "${!MODEL_NAMES[@]}"; do
        printf '  %d) %s\n' "$((idx + 1))" "${MODEL_NAMES[$idx]}"
    done
    read -r -p "Enter model number or exact model name (or 'back'): " answer
    if [ "$answer" = "back" ]; then
        return 1
    fi

    if [[ "$answer" =~ ^[0-9]+$ ]]; then
        idx=$((answer - 1))
        if [ "$idx" -ge 0 ] && [ "$idx" -lt "${#MODEL_NAMES[@]}" ]; then
            SELECTED_MODEL="${MODEL_NAMES[$idx]}"
            print_ok "Selected installed model: $SELECTED_MODEL"
            return 0
        fi
    else
        if resolved="$(find_installed_name "$answer")"; then
            SELECTED_MODEL="$resolved"
            print_ok "Selected installed model: $SELECTED_MODEL"
            return 0
        fi
    fi

    printf '%b\n' "${RED}[ERROR] Model name/number not found in the installed 'ollama list'. Verify the exact name below.${NC}"
    show_model_list
    return 1
}

choose_model_mode() {
    local choice requested retry resolved=""
    while true; do
        printf '\n%b\n' "${CYAN}${BOLD}Choose how to run the application:${NC}"
        if [ "${#MODEL_NAMES[@]}" -eq 1 ]; then
            printf '  1) Continue with "%s" LLM\n' "${MODEL_NAMES[0]}"
        elif [ "${#MODEL_NAMES[@]}" -gt 1 ]; then
            printf '  1) Continue with an installed model (choose from the list)\n'
        else
            printf '  1) Continue with an installed model (currently none installed)\n'
        fi
        printf '  2) Download another model and use it\n'
        printf '  3) Continue without local LLM (use fallback processing)\n'
        read -r -p "Enter 1, 2, or 3: " choice

        case "$choice" in
            1)
                if select_installed_model; then
                    OLLAMA_ENABLED="true"
                    return 0
                fi
                ;;
            2)
                while true; do
                    read -r -p "Enter Ollama model name/tag to download (or 'back' to return to menu): " requested
                    requested="$(printf '%s' "$requested" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                    if [ "$requested" = "back" ]; then
                        break
                    fi
                    if [ -z "$requested" ] || [[ ! "$requested" =~ ^[A-Za-z0-9][A-Za-z0-9._:/-]*$ ]]; then
                        printf '%b\n' "${RED}[ERROR] Invalid model-name format. Verify the exact model tag; installed models are shown by 'ollama list'.${NC}"
                        show_model_list
                        continue
                    fi

                    if resolved="$(find_installed_name "$requested")"; then
                        SELECTED_MODEL="$resolved"
                        OLLAMA_ENABLED="true"
                        print_ok "That model is already installed: $SELECTED_MODEL"
                        return 0
                    fi

                    printf '%b\n' "${YELLOW}Model '$requested' is not installed locally. Running 'ollama pull $requested'...${NC}"
                    if "$OLLAMA_BIN" pull "$requested"; then
                        if refresh_ollama_list; then
                            if resolved="$(find_installed_name "$requested")"; then
                                SELECTED_MODEL="$resolved"
                                OLLAMA_ENABLED="true"
                                print_ok "Downloaded and selected model: $SELECTED_MODEL"
                                return 0
                            fi
                        fi
                        printf '%b\n' "${RED}[ERROR] Download finished, but '$requested' was not found in the refreshed 'ollama list'.${NC}"
                        show_model_list
                    else
                        printf '%b\n' "${RED}[ERROR] Model name may be incorrect or unavailable. Verify the exact tag in the Ollama model library; 'ollama list' shows models installed locally.${NC}"
                        refresh_ollama_list || true
                        show_model_list
                    fi
                    read -r -p "Try another model name? [Y/n] " retry
                    case "$retry" in
                        n|N|no|NO) break ;;
                        *) continue ;;
                    esac
                done
                ;;
            3)
                OLLAMA_ENABLED="false"
                SELECTED_MODEL=""
                print_warn "Local LLM use will be disabled in the project configuration. The app will use its existing fallback paths."
                return 0
                ;;
            *)
                printf '%b\n' "${RED}[ERROR] Please enter 1, 2, or 3.${NC}"
                ;;
        esac
    done
}

printf '%b\n' "${YELLOW}[STEP 1/5] Checking Ollama installation and local models...${NC}"
if ! resolve_ollama; then
    if ! install_ollama; then
        print_error "Ollama could not be installed automatically."
        printf '%b\n' "${YELLOW}You can install it from https://ollama.com/download and rerun this launcher.${NC}"
        read -r -p "Continue without a local LLM for this run? Enter 3 to continue, anything else to exit: " no_ollama_choice
        if [ "$no_ollama_choice" = "3" ]; then
            OLLAMA_ENABLED="false"
            SELECTED_MODEL=""
        else
            exit 1
        fi
    fi
fi

if [ -n "$OLLAMA_BIN" ]; then
    print_ok "Ollama CLI: $(safe_path "$OLLAMA_BIN")"
    if refresh_ollama_list; then
        show_model_list
        if ! choose_model_mode; then
            print_error "Could not select a model mode."
            exit 1
        fi
    else
        print_error "Ollama is installed but 'ollama list' could not connect to the local server. See ollama-serve.log for startup output."
        read -r -p "Continue without a local LLM? Enter 3 to continue, anything else to exit: " no_server_choice
        if [ "$no_server_choice" = "3" ]; then
            OLLAMA_ENABLED="false"
            SELECTED_MODEL=""
        else
            exit 1
        fi
    fi
fi

# ------------------------------------------------------------------------------
# STEP 2: Determine the project's Python requirement
# ------------------------------------------------------------------------------
printf '\n%b\n' "${YELLOW}[STEP 2/5] Checking Python requirements and environment...${NC}"
TOML_FILE="$PROJECT_ROOT/pyproject.toml"
REQ_PY=">=3.10"
if [ -f "$TOML_FILE" ]; then
    PARSED_REQ="$(grep -i '^[[:space:]]*requires-python[[:space:]]*=' "$TOML_FILE" 2>/dev/null | head -n 1 | sed -E 's/^[[:space:]]*requires-python[[:space:]]*=[[:space:]]*//; s/"//g' | tr -d '\r\n' || true)"
    if [ -n "$PARSED_REQ" ]; then REQ_PY="$PARSED_REQ"; fi
    print_ok "Required Python version: $REQ_PY"
else
    print_warn "pyproject.toml not found; assuming Python $REQ_PY."
fi

check_py_version() {
    local py_exec="$1"
    [ -n "$py_exec" ] || return 1
    if [ ! -x "$py_exec" ] && ! command -v "$py_exec" >/dev/null 2>&1; then return 1; fi
    "$py_exec" -c '
import re, sys
req = sys.argv[1] if len(sys.argv) > 1 else ">=3.10"
m = re.search(r"([><=]+)\s*(\d+)(?:\.(\d+))?", req)
if not m: sys.exit(0)
op, major = m.group(1), int(m.group(2))
minor = int(m.group(3)) if m.group(3) else 0
current, target = (sys.version_info.major, sys.version_info.minor), (major, minor)
if op == ">=" and current < target: sys.exit(1)
elif op == ">" and current <= target: sys.exit(1)
elif op in ("==", "=") and current != target: sys.exit(1)
elif op == "<=" and current > target: sys.exit(1)
elif op == "<" and current >= target: sys.exit(1)
' "$REQ_PY" >/dev/null 2>&1
}

find_venv_python() {
    local vdir="$1"
    if [ -f "$vdir/Scripts/python.exe" ]; then printf '%s' "$vdir/Scripts/python.exe"
    elif [ -f "$vdir/Scripts/python" ]; then printf '%s' "$vdir/Scripts/python"
    elif [ -f "$vdir/bin/python" ]; then printf '%s' "$vdir/bin/python"
    elif [ -f "$vdir/bin/python3" ]; then printf '%s' "$vdir/bin/python3"
    fi
}

activate_venv() {
    local vdir="$1"
    if [ -f "$vdir/Scripts/activate" ]; then source "$vdir/Scripts/activate"
    elif [ -f "$vdir/bin/activate" ]; then source "$vdir/bin/activate"
    fi
}

path_from_py_launcher() {
    local native_path=""
    if command -v py >/dev/null 2>&1; then
        native_path="$(py -3 -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
    elif command -v py.exe >/dev/null 2>&1; then
        native_path="$(py.exe -3 -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
    fi
    if [ -n "$native_path" ] && command -v cygpath >/dev/null 2>&1; then
        native_path="$(cygpath -u "$native_path" 2>/dev/null || printf '%s' "$native_path")"
    fi
    printf '%s' "$native_path"
}

ACTIVE_PY=""
ENV_TYPE=""

if [ -n "${VIRTUAL_ENV:-}" ]; then
    candidate="$(find_venv_python "$VIRTUAL_ENV")"
    [ -n "$candidate" ] || candidate="python"
    if check_py_version "$candidate"; then ACTIVE_PY="$candidate"; ENV_TYPE="Active virtual environment"; fi
fi

if [ -z "$ACTIVE_PY" ] && [ -n "${CONDA_PREFIX:-}" ]; then
    candidate=""
    [ -f "$CONDA_PREFIX/python.exe" ] && candidate="$CONDA_PREFIX/python.exe"
    [ -z "$candidate" ] && [ -f "$CONDA_PREFIX/bin/python" ] && candidate="$CONDA_PREFIX/bin/python"
    [ -n "$candidate" ] || candidate="python"
    if check_py_version "$candidate"; then ACTIVE_PY="$candidate"; ENV_TYPE="Active Conda environment (${CONDA_DEFAULT_ENV:-unknown})"; fi
fi

if [ -z "$ACTIVE_PY" ] && command -v python >/dev/null 2>&1 && check_py_version python; then
    ACTIVE_PY="python"; ENV_TYPE="Python on PATH"
elif [ -z "$ACTIVE_PY" ] && command -v python3 >/dev/null 2>&1 && check_py_version python3; then
    ACTIVE_PY="python3"; ENV_TYPE="Python3 on PATH"
fi

if [ -z "$ACTIVE_PY" ] && [ -d "$PROJECT_ROOT/.venv" ]; then
    candidate="$(find_venv_python "$PROJECT_ROOT/.venv")"
    if [ -n "$candidate" ] && check_py_version "$candidate"; then
        activate_venv "$PROJECT_ROOT/.venv"
        ACTIVE_PY="$candidate"; ENV_TYPE="Existing project .venv"
    fi
fi

if [ -z "$ACTIVE_PY" ]; then
    candidate="$(path_from_py_launcher)"
    if [ -n "$candidate" ] && check_py_version "$candidate"; then ACTIVE_PY="$candidate"; ENV_TYPE="Python launcher (py -3)"; fi
fi

if [ -z "$ACTIVE_PY" ]; then
    KNOWN_PATHS=(
        "/c/ProgramData/anaconda3/python.exe"
        "/c/Python312/python.exe"
        "/c/Python311/python.exe"
        "/c/Python310/python.exe"
        "/usr/bin/python3"
        "/usr/local/bin/python3"
    )
    for candidate in "${KNOWN_PATHS[@]}"; do
        if [ -f "$candidate" ] && check_py_version "$candidate"; then
            ACTIVE_PY="$candidate"; ENV_TYPE="Python at $(safe_path "$candidate")"; break
        fi
    done
fi

if [ -z "$ACTIVE_PY" ]; then
    print_error "No compatible Python interpreter found (requirement: $REQ_PY). Install Python and rerun the launcher."
    exit 1
fi

CURRENT_VER="$("$ACTIVE_PY" --version 2>&1)"
print_ok "Environment: $ENV_TYPE"
printf '     Python executable: %s\n     Python version: %s\n' "$(safe_path "$ACTIVE_PY")" "$CURRENT_VER"

# If a new virtual environment is needed, this can be added later; using an
# installed compatible interpreter avoids overwriting an existing .venv.

# ------------------------------------------------------------------------------
# STEP 3: Update config files (with backups) using the selected model mode
# ------------------------------------------------------------------------------
printf '\n%b\n' "${YELLOW}[STEP 3/5] Updating model configuration...${NC}"
CONFIG_DIR="$PROJECT_ROOT/data/config"
MODEL_CONFIG_FILE="$CONFIG_DIR/model_config.json"
PROJECT_CONFIG_FILE="$CONFIG_DIR/project_config.json"
if [ ! -f "$MODEL_CONFIG_FILE" ] || [ ! -f "$PROJECT_CONFIG_FILE" ]; then
    print_error "Expected configuration files not found in $CONFIG_DIR."
    exit 1
fi

CONFIG_BACKUP_DIR="$PROJECT_ROOT/.launcher-config-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$CONFIG_BACKUP_DIR"
cp "$MODEL_CONFIG_FILE" "$CONFIG_BACKUP_DIR/model_config.json"
cp "$PROJECT_CONFIG_FILE" "$CONFIG_BACKUP_DIR/project_config.json"

"$ACTIVE_PY" - "$PROJECT_ROOT" "$OLLAMA_ENABLED" "$SELECTED_MODEL" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
enabled = sys.argv[2].strip().lower() == "true"
selected_model = sys.argv[3].strip()
config_dir = root / "data" / "config"
model_path = config_dir / "model_config.json"
project_path = config_dir / "project_config.json"

def read_json(path):
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value

def atomic_write(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=4)
        handle.write("\n")
    temp.replace(path)

model_cfg = read_json(model_path)
project_cfg = read_json(project_path)
master_model_cfg = project_cfg.get("model_config")
if not isinstance(master_model_cfg, dict):
    master_model_cfg = dict(model_cfg)
else:
    master_model_cfg = dict(master_model_cfg)

configs = [model_cfg, master_model_cfg]
if enabled:
    if not selected_model:
        raise ValueError("A model was selected as enabled, but no model name was supplied.")
    for cfg in configs:
        cfg["model_name"] = selected_model
        cfg["llm_enabled"] = True
        # Avoid the 512-token response cap that previously caused truncated output.
        try:
            configured_tokens = int(cfg.get("max_tokens", 512))
        except (TypeError, ValueError):
            configured_tokens = 512
        if configured_tokens < 2048:
            cfg["max_tokens"] = 2048
    print(f"Local LLM enabled with model: {selected_model}")
    print("Maximum output tokens set to at least 2048.")
else:
    for cfg in configs:
        # `model=None` causes the current ChatOllama initialization to fail safely;
        # model.py already catches initialization errors and sets llm=None.
        cfg["model_name"] = None
        cfg["llm_enabled"] = False
    print("Local LLM disabled in configuration (model_name=null, llm_enabled=false).")
    print("The app's existing regex/generic fallback paths will be used.")

project_cfg["model_config"] = master_model_cfg
atomic_write(model_path, model_cfg)
atomic_write(project_path, project_cfg)
print(f"Updated: {model_path}")
print(f"Updated: {project_path}")
PY

# ------------------------------------------------------------------------------
# STEP 4: Install project dependencies from pyproject.toml
# ------------------------------------------------------------------------------
printf '\n%b\n' "${YELLOW}[STEP 4/5] Installing/verifying project dependencies...${NC}"
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    print_error "pyproject.toml is missing; cannot install project dependencies."
    exit 1
fi
"$ACTIVE_PY" -m pip install --upgrade pip --quiet
"$ACTIVE_PY" -m pip install .
print_ok "Project dependencies installed/verified."

# ------------------------------------------------------------------------------
# STEP 5: Launch Streamlit
# ------------------------------------------------------------------------------
printf '\n%b\n' "${YELLOW}[STEP 5/5] Starting Streamlit application...${NC}"
printf '%b\n' "${CYAN}+------------------------------------------------------------------+${NC}"
printf '%b\n' "${CYAN}|${BOLD} Launching Streamlit Web Interface...                             ${NC}${CYAN}|${NC}"
printf '%b\n' "${CYAN}+------------------------------------------------------------------+${NC}"
printf '%b\n' "${GREEN}${BOLD}Dashboard starting on http://localhost:8501 ...${NC}"
printf '%b\n\n' "${YELLOW}Press Ctrl+C in this terminal to stop the application.${NC}"

if [ ! -f "$PROJECT_ROOT/app.py" ]; then
    print_error "Expected app.py was not found in the project root: $PROJECT_ROOT"
    exit 1
fi
APP_LAUNCHED="true"
STREAMLIT_EXIT_STATUS=0
# Do not use `exec`: Bash must regain control so cleanup can run after Streamlit exits.
set +e
"$ACTIVE_PY" -m streamlit run "$PROJECT_ROOT/app.py"
STREAMLIT_EXIT_STATUS=$?
set -e
exit "$STREAMLIT_EXIT_STATUS"
