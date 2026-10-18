#!/usr/bin/env bash
# ==============================================================================
# AI Job Search & Auto-Apply — Environment & App Launcher (Root run.sh)
# ==============================================================================
# Terminal Easy-Viewer Edition with Color Highlights and Step Progress
# ==============================================================================

set -e

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine project directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo -e "${CYAN}+==================================================================+${NC}"
echo -e "${CYAN}|${BOLD}       AI Job Search & Auto-Apply -- Environment & App Launcher   ${NC}${CYAN}|${NC}"
echo -e "${CYAN}+==================================================================+${NC}"
echo -e "${CYAN}|${NC} Root Directory: ${BOLD}$PROJECT_ROOT${NC}"
echo -e "${CYAN}+==================================================================+${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 1: Locate Python Executable
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 1/4] Detecting Python Environment...${NC}"
PYTHON_CMD=""

if [ -n "$CONDA_PREFIX" ] && [ -f "$CONDA_PREFIX/python.exe" ]; then
    PYTHON_CMD="$CONDA_PREFIX/python.exe"
elif [ -n "$CONDA_PREFIX" ] && [ -f "$CONDA_PREFIX/bin/python" ]; then
    PYTHON_CMD="$CONDA_PREFIX/bin/python"
elif [ -f "$HOME/OneDrive/Desktop/agentic-ai/agentic-ai/python.exe" ]; then
    PYTHON_CMD="$HOME/OneDrive/Desktop/agentic-ai/agentic-ai/python.exe"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif [ -f "/c/ProgramData/anaconda3/python.exe" ]; then
    PYTHON_CMD="/c/ProgramData/anaconda3/python.exe"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}[ERROR] Python 3.10+ was not found on PATH or common directories.${NC}"
    echo -e "${RED}        Please install Python 3.10 or higher and rerun this script.${NC}"
    exit 1
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo -e "${GREEN}[OK] Python Detected: ${BOLD}$PY_VER${NC} (${CYAN}$PYTHON_CMD${NC})"
echo ""

# ------------------------------------------------------------------------------
# STEP 2: Manage Virtual Environment
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 2/4] Setting Up Virtual Environment...${NC}"
VENV_DIR="$PROJECT_ROOT/.venv"

if [ -n "$CONDA_PREFIX" ]; then
    echo -e "${GREEN}[OK] Active Conda environment detected:${NC} $CONDA_PREFIX"
    ACTIVE_PY="$PYTHON_CMD"
elif [ -d "$VENV_DIR" ]; then
    echo -e "${GREEN}[OK] Existing virtual environment found:${NC} $VENV_DIR"
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        ACTIVE_PY="python"
    elif [ -f "$VENV_DIR/Scripts/activate" ]; then
        source "$VENV_DIR/Scripts/activate"
        ACTIVE_PY="python"
    else
        ACTIVE_PY="$PYTHON_CMD"
    fi
else
    echo -e "${YELLOW}[SETUP] Creating new virtual environment at:${NC} $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
    elif [ -f "$VENV_DIR/Scripts/activate" ]; then
        source "$VENV_DIR/Scripts/activate"
    fi
    ACTIVE_PY="python"
    echo -e "${GREEN}[OK] New virtual environment successfully initialized.${NC}"
fi
echo ""

# ------------------------------------------------------------------------------
# STEP 3: Verify and Install Dependencies
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 3/4] Checking and Installing Dependencies...${NC}"
echo -e "${CYAN}Running: pip install -e .[dev]${NC}"
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet
echo -e "${GREEN}[OK] All dependencies verified and up to date.${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 4: Launch Streamlit Application
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[STEP 4/4] Starting Streamlit Web Interface...${NC}"
echo -e "${CYAN}+------------------------------------------------------------------+${NC}"
echo -e "${CYAN}|${BOLD} Application Modules Ready:                                      ${NC}${CYAN}|${NC}"
echo -e "${CYAN}|${NC} - Tab 1: Chat & Auto-Email (Multi-format DB + Live Streaming)     ${CYAN}|${NC}"
echo -e "${CYAN}|${NC} - Tab 2: Dynamic Subject, Body & System Prompt Inspector         ${CYAN}|${NC}"
echo -e "${CYAN}|${NC} - Tab 3: Database Manager (Modify & Delete Only)                  ${CYAN}|${NC}"
echo -e "${CYAN}|${NC} - Tab 4: Domain-Wise Email Viewer (Analytics & Safe Deletion)     ${CYAN}|${NC}"
echo -e "${CYAN}+------------------------------------------------------------------+${NC}"
echo -e "${GREEN}${BOLD}Launching dashboard on http://localhost:8501 ...${NC}"
echo -e "${YELLOW}Press Ctrl+C in this terminal to stop the application.${NC}"
echo ""

python -m streamlit run app.py

