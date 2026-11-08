#!/usr/bin/env bash
# python_env.sh
# Detect a compatible Python interpreter for the project.
# Requires: colors_and_utils.sh, PROJECT_ROOT set by caller.
# Sets: ACTIVE_PY, ENV_TYPE.

ACTIVE_PY=""
ENV_TYPE=""

_read_python_requirement() {
    local toml_file="$PROJECT_ROOT/pyproject.toml"
    REQ_PY=">=3.10"
    if [ -f "$toml_file" ]; then
        local parsed
        parsed="$(grep -i \
            '^[[:space:]]*requires-python[[:space:]]*=' \
            "$toml_file" 2>/dev/null \
            | head -n 1 \
            | sed -E \
                's/^[[:space:]]*requires-python[[:space:]]*=[[:space:]]*//;
                 s/"//g' \
            | tr -d '\r\n' || true)"
        if [ -n "$parsed" ]; then
            REQ_PY="$parsed"
        fi
        print_ok "Required Python: $REQ_PY"
    else
        print_warn "pyproject.toml not found; assuming $REQ_PY."
    fi
}

check_py_version() {
    local py_exec="$1"
    [ -n "$py_exec" ] || return 1
    if [ ! -x "$py_exec" ] \
        && ! command -v "$py_exec" >/dev/null 2>&1; then
        return 1
    fi
    "$py_exec" -c '
import re, sys
req = sys.argv[1] if len(sys.argv) > 1 else ">=3.10"
m = re.search(r"([><=]+)\s*(\d+)(?:\.(\d+))?", req)
if not m: sys.exit(0)
op, major = m.group(1), int(m.group(2))
minor = int(m.group(3)) if m.group(3) else 0
current = (sys.version_info.major, sys.version_info.minor)
target = (major, minor)
if op == ">=" and current < target: sys.exit(1)
elif op == ">" and current <= target: sys.exit(1)
elif op in ("==", "=") and current != target: sys.exit(1)
elif op == "<=" and current > target: sys.exit(1)
elif op == "<" and current >= target: sys.exit(1)
' "$REQ_PY" >/dev/null 2>&1
}

find_venv_python() {
    local vdir="$1"
    if   [ -f "$vdir/Scripts/python.exe" ]; then
        printf '%s' "$vdir/Scripts/python.exe"
    elif [ -f "$vdir/Scripts/python" ]; then
        printf '%s' "$vdir/Scripts/python"
    elif [ -f "$vdir/bin/python" ]; then
        printf '%s' "$vdir/bin/python"
    elif [ -f "$vdir/bin/python3" ]; then
        printf '%s' "$vdir/bin/python3"
    fi
}

activate_venv() {
    local vdir="$1"
    if   [ -f "$vdir/Scripts/activate" ]; then
        source "$vdir/Scripts/activate"
    elif [ -f "$vdir/bin/activate" ]; then
        source "$vdir/bin/activate"
    fi
}

path_from_py_launcher() {
    local native_path=""
    if command -v py >/dev/null 2>&1; then
        native_path="$(py -3 -c \
            'import sys; print(sys.executable)' \
            2>/dev/null || true)"
    elif command -v py.exe >/dev/null 2>&1; then
        native_path="$(py.exe -3 -c \
            'import sys; print(sys.executable)' \
            2>/dev/null || true)"
    fi
    if [ -n "$native_path" ] \
        && command -v cygpath >/dev/null 2>&1; then
        native_path="$(cygpath -u "$native_path" \
            2>/dev/null || printf '%s' "$native_path")"
    fi
    printf '%s' "$native_path"
}

run_python_env_detection() {
    printf '\n%b\n' \
        "${YELLOW}[STEP 2/5] Checking Python environment...${NC}"

    _read_python_requirement

    local candidate=""

    # 1. Active virtual environment
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        candidate="$(find_venv_python "$VIRTUAL_ENV")"
        [ -n "$candidate" ] || candidate="python"
        if check_py_version "$candidate"; then
            ACTIVE_PY="$candidate"
            ENV_TYPE="Active virtual environment"
        fi
    fi

    # 2. Active Conda environment
    if [ -z "$ACTIVE_PY" ] && [ -n "${CONDA_PREFIX:-}" ]; then
        candidate=""
        [ -f "$CONDA_PREFIX/python.exe" ] \
            && candidate="$CONDA_PREFIX/python.exe"
        [ -z "$candidate" ] \
            && [ -f "$CONDA_PREFIX/bin/python" ] \
            && candidate="$CONDA_PREFIX/bin/python"
        [ -n "$candidate" ] || candidate="python"
        if check_py_version "$candidate"; then
            ACTIVE_PY="$candidate"
            ENV_TYPE="Active Conda (${CONDA_DEFAULT_ENV:-unknown})"
        fi
    fi

    # 3. python / python3 on PATH
    if [ -z "$ACTIVE_PY" ] \
        && command -v python >/dev/null 2>&1 \
        && check_py_version python; then
        ACTIVE_PY="python"
        ENV_TYPE="Python on PATH"
    elif [ -z "$ACTIVE_PY" ] \
        && command -v python3 >/dev/null 2>&1 \
        && check_py_version python3; then
        ACTIVE_PY="python3"
        ENV_TYPE="Python3 on PATH"
    fi

    # 4. Project .venv
    if [ -z "$ACTIVE_PY" ] \
        && [ -d "$PROJECT_ROOT/.venv" ]; then
        candidate="$(find_venv_python "$PROJECT_ROOT/.venv")"
        if [ -n "$candidate" ] \
            && check_py_version "$candidate"; then
            activate_venv "$PROJECT_ROOT/.venv"
            ACTIVE_PY="$candidate"
            ENV_TYPE="Existing project .venv"
        fi
    fi

    # 5. Windows py launcher
    if [ -z "$ACTIVE_PY" ]; then
        candidate="$(path_from_py_launcher)"
        if [ -n "$candidate" ] \
            && check_py_version "$candidate"; then
            ACTIVE_PY="$candidate"
            ENV_TYPE="Python launcher (py -3)"
        fi
    fi

    # 6. Known install paths
    if [ -z "$ACTIVE_PY" ]; then
        local known_paths=(
            "/c/ProgramData/anaconda3/python.exe"
            "/c/Python312/python.exe"
            "/c/Python311/python.exe"
            "/c/Python310/python.exe"
            "/usr/bin/python3"
            "/usr/local/bin/python3"
        )
        for candidate in "${known_paths[@]}"; do
            if [ -f "$candidate" ] \
                && check_py_version "$candidate"; then
                ACTIVE_PY="$candidate"
                ENV_TYPE="Python at $(safe_path "$candidate")"
                break
            fi
        done
    fi

    if [ -z "$ACTIVE_PY" ]; then
        print_error \
            "No compatible Python found (need $REQ_PY)." \
            "Install Python and rerun."
        exit 1
    fi

    local current_ver
    current_ver="$("$ACTIVE_PY" --version 2>&1)"
    print_ok "Environment: $ENV_TYPE"
    printf '     Executable: %s\n     Version:    %s\n' \
        "$(safe_path "$ACTIVE_PY")" "$current_ver"
}
