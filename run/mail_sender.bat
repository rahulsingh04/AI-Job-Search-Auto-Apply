@echo off
setlocal enabledelayedexpansion
REM ==============================================================================
REM AI Job Search & Auto-Apply -- Windows Launcher (Easy Terminal Viewer)
REM ==============================================================================

cd /d "%~dp0\.."

echo +==================================================================+
echo ^|       AI Job Search ^& Auto-Apply -- Windows Launcher            ^|
echo +==================================================================+
echo ^| Root Directory: %CD%
echo +==================================================================+
echo.

REM ------------------------------------------------------------------------------
REM STEP 1: Detect Python
REM ------------------------------------------------------------------------------
echo [STEP 1/4] Detecting Python Environment...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found on standard PATH. Searching system installations...
    if exist "C:\Users\javar\OneDrive\Desktop\agentic-ai\agentic-ai\python.exe" (
        set "PYTHON_EXE=C:\Users\javar\OneDrive\Desktop\agentic-ai\agentic-ai\python.exe"
    ) else if exist "C:\ProgramData\anaconda3\python.exe" (
        set "PYTHON_EXE=C:\ProgramData\anaconda3\python.exe"
    ) else (
        echo [ERROR] Python 3.10+ is required but was not found.
        pause
        exit /b 1
    )
) else (
    set "PYTHON_EXE=python"
)

for /f "delims=" %%v in ('%PYTHON_EXE% --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Detected Python: %PY_VER% (%PYTHON_EXE%)
echo.

REM ------------------------------------------------------------------------------
REM STEP 2: Virtual Environment Setup
REM ------------------------------------------------------------------------------
echo [STEP 2/4] Setting Up Virtual Environment...
if not exist ".venv" (
    if defined CONDA_PREFIX (
        echo [OK] Using active Conda environment: %CONDA_PREFIX%
    ) else (
        echo [SETUP] Creating new virtual environment in .venv...
        %PYTHON_EXE% -m venv .venv
        call .venv\Scripts\activate.bat
    )
) else (
    echo [OK] Activating existing .venv...
    call .venv\Scripts\activate.bat
)
echo.

REM ------------------------------------------------------------------------------
REM STEP 3: Verify Dependencies
REM ------------------------------------------------------------------------------
echo [STEP 3/4] Checking and Installing Dependencies...
pip install -e . --quiet
echo [OK] All dependencies are ready.
echo.

REM ------------------------------------------------------------------------------
REM STEP 4: Start Streamlit App
REM ------------------------------------------------------------------------------
echo [STEP 4/4] Starting Streamlit Web Interface...
echo +------------------------------------------------------------------+
echo ^| Ready Modules:                                                   ^|
echo ^| - Tab 1: Chat ^& Auto-Email (Live Email Scraper + Auto Backup)   ^|
echo ^| - Tab 2: Subject, Body ^& System Prompt Inspector                ^|
echo ^| - Tab 3: Email Scraper ^& Database Manager                       ^|
echo ^| - Tab 4: Domain-Wise Email Viewer (Safe Deletion with Prompt)    ^|
echo +------------------------------------------------------------------+
echo Opening http://localhost:8501 in your default browser...
echo Press Ctrl+C in this terminal window to stop the server.
echo.

python -m streamlit run app.py
pause
