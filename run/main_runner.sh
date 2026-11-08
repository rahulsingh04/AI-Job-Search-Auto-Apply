#!/usr/bin/env bash
# main_runner.sh
# ============================================================
# AI Job Search & Auto-Apply — Main Launcher Orchestrator
# Project:  AI-Job-Search-Auto-Apply
# Author:   Rahul Singh
# Contact:  javarahul04@gmail.com
# GitHub:   https://github.com/rahulsingh04/AI-Job-Search-Auto-Apply
#
# Component scripts sourced (all in run/):
#   1. colors_and_utils.sh  — ANSI colors + print helpers
#   2. banner_and_cleanup.sh — project banner + post-app cleanup
#   3. ollama_setup.sh      — Ollama detect/install/model select
#   4. python_env.sh        — Python interpreter detection
#   5. config_updater.sh    — model_config.json update
#   6. deps_installer.sh    — pip dependency install
#   7. streamlit_launcher.sh — Streamlit app launch
#
# Flow:
#   1. Detect/install Ollama and choose LLM model mode
#   2. Find a compatible Python interpreter
#   3. Update model_config.json with selected model
#   4. Install project dependencies from pyproject.toml
#   5. Launch Streamlit dashboard
# ============================================================

set -Eeuo pipefail

# ── Locate the project root ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    PROJECT_ROOT="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/../app.py" ] \
    && [ -f "$SCRIPT_DIR/../data/config/project_config.json" ]
then
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
    echo "[ERROR] Cannot locate project root (pyproject.toml not found)." >&2
    exit 1
fi

cd "$PROJECT_ROOT"

# ── Source all component scripts ─────────────────────────────
source "$SCRIPT_DIR/colors_and_utils.sh"
source "$SCRIPT_DIR/banner_and_cleanup.sh"
source "$SCRIPT_DIR/ollama_setup.sh"
source "$SCRIPT_DIR/python_env.sh"
source "$SCRIPT_DIR/config_updater.sh"
source "$SCRIPT_DIR/deps_installer.sh"
source "$SCRIPT_DIR/streamlit_launcher.sh"

# ── Launcher state flags ─────────────────────────────────────
APP_LAUNCHED="false"
CLEANUP_DONE="false"
LAUNCHER_CREATED_ENVIRONMENT="false"
LAUNCHER_CREATED_ENVIRONMENT_PATH=""

# ── Exit trap: run cleanup after app closes ──────────────────
launcher_exit_trap() {
    local original_status=$?
    trap - EXIT
    if [ "$APP_LAUNCHED" = "true" ] \
        && [ "$CLEANUP_DONE" != "true" ]; then
        CLEANUP_DONE="true"
        run_post_app_cleanup \
            || print_warn "Some cleanup tasks failed."
    fi
    exit "$original_status"
}
trap launcher_exit_trap EXIT

# ── Show project banner ──────────────────────────────────────
show_project_banner

# ── Run all steps ────────────────────────────────────────────
run_ollama_setup        # Step 1: Ollama + model selection
run_python_env_detection # Step 2: Python interpreter
run_config_update       # Step 3: Update model config
run_deps_install        # Step 4: Install dependencies
run_streamlit_launch    # Step 5: Launch Streamlit
