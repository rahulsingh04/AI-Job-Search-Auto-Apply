#!/usr/bin/env bash
# ==============================================================================
# AI Job Search & Auto-Apply — Environment & App Launcher (run/run.sh)
# ==============================================================================
# Workflow:
# 1. Parse requirement (requires-python) from pyproject.toml
# 2. Check if a compatible Python environment is available on your computer
#    (Active Conda / Virtualenv, system/user python on PATH, or existing .venv)
# 3. If available & satisfies TOML requirement:
#      - Use the existing environment directly (DO NOT create a new one)
#    If NOT available:
#      - Locate another compatible Python installation and create a new .venv
# 4. Run `pip install .` to install/verify dependencies from pyproject.toml
# 5. Launch the Streamlit application (app.py)
# ==============================================================================

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Helper to print Windows paths safely without escape interpretation
safe_path() {
    echo "$1" | tr '\\' '/'
}

# ------------------------------------------------------------------------------
# Locate Project Root & pyproject.toml
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Identify project root whether script is run from run/ or the project root
if [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
else
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

cd "$PROJECT_ROOT"

echo -e "${CYAN}+==================================================================+${NC}"
echo -e "${CYAN}|${BOLD}       AI Job Search & Auto-Apply -- Environment & App Launcher   ${NC}${CYAN}|${NC}"
echo -e "${CYAN}+==================================================================+${NC}"
echo -e "${CYAN}|${NC} Project Root : ${BOLD}$(safe_path "$PROJECT_ROOT")${NC}"
echo -e "${CYAN}+==================================================================+${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 1: Parse Python Version Requirement from pyproject.toml
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 1/4] Checking Requirements from pyproject.toml...${NC}"
TOML_FILE="$PROJECT_ROOT/pyproject.toml"
REQ_PY=">=3.10"

if [ -f "$TOML_FILE" ]; then
    PARSED_REQ=$(grep -i "requires-python" "$TOML_FILE" 2>/dev/null | head -n 1 | sed -e 's/^[[:space:]]*requires-python[[:space:]]*=[[:space:]]*//' -e 's/["'\'']//g' | tr -d '\r\n')
    if [ -n "$PARSED_REQ" ]; then
        REQ_PY="$PARSED_REQ"
    fi
    echo -e "${GREEN}[OK] Required Python Version:${NC} ${BOLD}$REQ_PY${NC} (from $(basename "$TOML_FILE"))"
else
    echo -e "${YELLOW}[WARN] pyproject.toml not found at $(safe_path "$TOML_FILE"). Defaulting requirement to: $REQ_PY${NC}"
fi
echo ""

# Helper function to check if a python executable satisfies REQ_PY
check_py_version() {
    local py_exec="$1"
    if [ -z "$py_exec" ]; then
        return 1
    fi
    if [ ! -x "$py_exec" ] && ! command -v "$py_exec" &> /dev/null; then
        return 1
    fi

    "$py_exec" -c "
import sys, re

req = sys.argv[1] if len(sys.argv) > 1 else '>=3.10'
m = re.search(r'([><=]+)\s*(\d+)(?:\.(\d+))?', req)
if not m:
    sys.exit(0)

op, maj = m.group(1), int(m.group(2))
min_ = int(m.group(3)) if m.group(3) else 0

curr = (sys.version_info.major, sys.version_info.minor)
target = (maj, min_)

if op == '>=' and curr < target:
    sys.exit(1)
elif op == '>' and curr <= target:
    sys.exit(1)
elif op in ('==', '=') and curr != target:
    sys.exit(1)
elif op == '<=' and curr > target:
    sys.exit(1)
elif op == '<' and curr >= target:
    sys.exit(1)

sys.exit(0)
" "$REQ_PY" 2>/dev/null
}

# Helper to find python inside a virtual environment directory
find_venv_python() {
    local vdir="$1"
    if [ -f "$vdir/Scripts/python.exe" ]; then
        echo "$vdir/Scripts/python.exe"
    elif [ -f "$vdir/Scripts/python" ]; then
        echo "$vdir/Scripts/python"
    elif [ -f "$vdir/bin/python" ]; then
        echo "$vdir/bin/python"
    fi
}

# Helper to activate a virtual environment
activate_venv() {
    local vdir="$1"
    if [ -f "$vdir/Scripts/activate" ]; then
        source "$vdir/Scripts/activate"
    elif [ -f "$vdir/bin/activate" ]; then
        source "$vdir/bin/activate"
    fi
}

# ------------------------------------------------------------------------------
# STEP 2: Check Existing Python Environment Available on Computer
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 2/4] Checking Python Environment on your computer...${NC}"

ACTIVE_PY=""
ENV_TYPE=""

# 1. Check if user already has an active Virtualenv or Conda environment
if [ -n "$VIRTUAL_ENV" ]; then
    PY_CANDIDATE="$(find_venv_python "$VIRTUAL_ENV")"
    if [ -z "$PY_CANDIDATE" ]; then PY_CANDIDATE="python"; fi
    if check_py_version "$PY_CANDIDATE"; then
        ACTIVE_PY="$PY_CANDIDATE"
        ENV_TYPE="Active Virtual Environment ($VIRTUAL_ENV)"
    fi
elif [ -n "$CONDA_PREFIX" ]; then
    PY_CANDIDATE=""
    if [ -f "$CONDA_PREFIX/python.exe" ]; then
        PY_CANDIDATE="$CONDA_PREFIX/python.exe"
    elif [ -f "$CONDA_PREFIX/bin/python" ]; then
        PY_CANDIDATE="$CONDA_PREFIX/bin/python"
    else
        PY_CANDIDATE="python"
    fi
    if check_py_version "$PY_CANDIDATE"; then
        ACTIVE_PY="$PY_CANDIDATE"
        ENV_TYPE="Active Conda Environment (${CONDA_DEFAULT_ENV:-base})"
    fi
fi

# 2. Check if default Python on PATH is available and satisfies requirement
if [ -z "$ACTIVE_PY" ]; then
    if command -v python &> /dev/null && check_py_version "python"; then
        ACTIVE_PY="python"
        ENV_TYPE="Python available on PATH"
    elif command -v python3 &> /dev/null && check_py_version "python3"; then
        ACTIVE_PY="python3"
        ENV_TYPE="Python3 available on PATH"
    fi
fi

# 3. Check existing project .venv if present and satisfies requirement
if [ -z "$ACTIVE_PY" ] && [ -d "$PROJECT_ROOT/.venv" ]; then
    LOCAL_PY="$(find_venv_python "$PROJECT_ROOT/.venv")"
    if [ -n "$LOCAL_PY" ] && check_py_version "$LOCAL_PY"; then
        activate_venv "$PROJECT_ROOT/.venv"
        ACTIVE_PY="$LOCAL_PY"
        ENV_TYPE="Existing Project Virtual Environment (.venv)"
    fi
fi

# 4. Check common standard installation locations (e.g. Anaconda, Windows paths)
if [ -z "$ACTIVE_PY" ]; then
    KNOWN_PATHS=(
        "/c/ProgramData/anaconda3/python.exe"
        "C:/ProgramData/anaconda3/python.exe"
        "$HOME/OneDrive/Desktop/agentic-ai/agentic-ai/python.exe"
        "/c/Python312/python.exe"
        "/c/Python311/python.exe"
        "/c/Python310/python.exe"
        "/usr/bin/python3"
        "/usr/local/bin/python3"
    )
    for p in "${KNOWN_PATHS[@]}"; do
        if [ -f "$p" ] && check_py_version "$p"; then
            ACTIVE_PY="$p"
            ENV_TYPE="Installed Python at $(safe_path "$p")"
            break
        fi
    done
fi

# Decision: If a compatible Python is available on the computer, USE IT!
# Only if NONE is found, create a new virtual environment.
if [ -n "$ACTIVE_PY" ]; then
    CURRENT_VER=$("$ACTIVE_PY" --version 2>&1)
    echo -e "${GREEN}[OK] Compatible Python environment found on computer:${NC}"
    echo -e "     - Environment : ${BOLD}$ENV_TYPE${NC}"
    echo -e "     - Executable  : ${CYAN}$(safe_path "$ACTIVE_PY")${NC}"
    echo -e "     - Version     : ${BOLD}$CURRENT_VER${NC} (Satisfies requirement: $REQ_PY)"
    echo -e "${GREEN}[OK] Using existing environment (no new virtual environment needed).${NC}"
else
    echo -e "${YELLOW}[SETUP] No compatible Python environment currently found on PATH meeting $REQ_PY.${NC}"
    echo -e "${YELLOW}[SETUP] Searching for another Python installation to create a new virtual environment...${NC}"

    BASE_PY=""
    FALLBACK_CANDIDATES=(
        "py -3"
        "/c/ProgramData/anaconda3/python.exe"
        "C:/ProgramData/anaconda3/python.exe"
        "/c/Python312/python.exe"
        "/c/Python311/python.exe"
        "/c/Python310/python.exe"
        "/usr/bin/python3"
        "/usr/local/bin/python3"
    )
    for cand in "${FALLBACK_CANDIDATES[@]}"; do
        if command -v "$cand" &> /dev/null || [ -f "$cand" ]; then
            if check_py_version "$cand"; then
                BASE_PY="$cand"
                break
            fi
        fi
    done

    if [ -z "$BASE_PY" ]; then
        echo -e "${RED}[ERROR] No Python interpreter found on this computer that satisfies: $REQ_PY${NC}"
        echo -e "${RED}        Please install Python $REQ_PY or higher and add it to your PATH.${NC}"
        exit 1
    fi

    echo -e "${GREEN}[OK] Base Python located:${NC} $(safe_path "$BASE_PY") ($($BASE_PY --version 2>&1))"
    echo -e "${YELLOW}[SETUP] Creating new virtual environment at: $(safe_path "$PROJECT_ROOT/.venv") ...${NC}"
    
    if [ -d "$PROJECT_ROOT/.venv" ]; then
        rm -rf "$PROJECT_ROOT/.venv"
    fi

    "$BASE_PY" -m venv "$PROJECT_ROOT/.venv"
    activate_venv "$PROJECT_ROOT/.venv"
    ACTIVE_PY="$(find_venv_python "$PROJECT_ROOT/.venv")"
    if [ -z "$ACTIVE_PY" ]; then
        ACTIVE_PY="python"
    fi
    echo -e "${GREEN}[OK] Virtual environment successfully created and activated.${NC}"
fi

echo ""

# ------------------------------------------------------------------------------
# STEP 3: Install Package & Dependencies (pip install .)
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 3/4] Installing / Updating Dependencies via pip install . ...${NC}"
"$ACTIVE_PY" -m pip install --upgrade pip --quiet
"$ACTIVE_PY" -m pip install .
echo -e "${GREEN}[OK] Dependencies successfully installed and verified from pyproject.toml.${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 4: Start Streamlit Application
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 4/4] Starting Streamlit Application...${NC}"
echo -e "${CYAN}+------------------------------------------------------------------+${NC}"
echo -e "${CYAN}|${BOLD} Launching Streamlit Web Interface...                             ${NC}${CYAN}|${NC}"
echo -e "${CYAN}+------------------------------------------------------------------+${NC}"
echo -e "${GREEN}${BOLD}Dashboard starting on http://localhost:8501 ...${NC}"
echo -e "${YELLOW}Press Ctrl+C in this terminal to stop the application.${NC}"
echo ""

"$ACTIVE_PY" -m streamlit run app.py
