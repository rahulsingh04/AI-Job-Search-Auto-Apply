#!/usr/bin/env bash
# deps_installer.sh
# Install/verify project dependencies from pyproject.toml.
# Requires: colors_and_utils.sh sourced first.
# Requires: ACTIVE_PY, PROJECT_ROOT set by caller.

run_deps_install() {
    printf '\n%b\n' \
        "${YELLOW}[STEP 4/5] Installing dependencies...${NC}"

    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        print_error "pyproject.toml missing; cannot install."
        exit 1
    fi

    "$ACTIVE_PY" -m pip install --upgrade pip --quiet
    "$ACTIVE_PY" -m pip install .
    print_ok "Project dependencies installed/verified."
}
