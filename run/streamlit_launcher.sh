#!/usr/bin/env bash
# streamlit_launcher.sh
# Launch the Streamlit application.
# Requires: colors_and_utils.sh sourced first.
# Requires: ACTIVE_PY, PROJECT_ROOT, APP_LAUNCHED set by caller.

run_streamlit_launch() {
    printf '\n%b\n' \
        "${YELLOW}[STEP 5/5] Starting Streamlit...${NC}"
    printf '%b\n' \
        "${CYAN}+------------------------------------------------------------------+${NC}"
    printf '%b\n' \
        "${CYAN}|${BOLD} Launching Streamlit Web Interface...                             ${NC}${CYAN}|${NC}"
    printf '%b\n' \
        "${CYAN}+------------------------------------------------------------------+${NC}"
    printf '%b\n' \
        "${GREEN}${BOLD}Dashboard starting on http://localhost:8501 ...${NC}"
    printf '%b\n\n' \
        "${YELLOW}Press Ctrl+C to stop the application.${NC}"

    if [ ! -f "$PROJECT_ROOT/app.py" ]; then
        print_error "app.py not found in: $PROJECT_ROOT"
        exit 1
    fi

    APP_LAUNCHED="true"
    STREAMLIT_EXIT_STATUS=0

    # Do not use exec — Bash must regain control for cleanup.
    set +e
    "$ACTIVE_PY" -m streamlit run "$PROJECT_ROOT/app.py"
    STREAMLIT_EXIT_STATUS=$?
    set -e

    exit "$STREAMLIT_EXIT_STATUS"
}
