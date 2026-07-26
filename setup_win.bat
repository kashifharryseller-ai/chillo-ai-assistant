@echo off
REM ---------------------------------------------------------------------------
REM  Gemini AI Assistant - Windows 10/11 setup and launcher.
REM
REM  Verifies Python 3.10+, creates a virtual environment, installs pinned
REM  dependencies and starts the app. Safe to re-run.
REM
REM  Usage: double-click this file, or run  setup_win.bat  from a terminal.
REM ---------------------------------------------------------------------------

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo.
echo === Gemini AI Assistant - Windows setup ===
echo.

REM --------------------------------------------------------------------------
REM 1. Locate a Python 3.10+ interpreter
REM --------------------------------------------------------------------------
REM Prefer the py launcher, which is installed with python.org builds and can
REM select a specific version; fall back to whatever "python" resolves to.
set "PYTHON="

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for %%V in (3.14 3.13 3.12 3.11 3.10) do (
        if not defined PYTHON (
            py -%%V -c "import sys" >nul 2>&1
            if !ERRORLEVEL! EQU 0 set "PYTHON=py -%%V"
        )
    )
)

if not defined PYTHON (
    where python >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        python -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1
        if !ERRORLEVEL! EQU 0 set "PYTHON=python"
    )
)

if not defined PYTHON (
    echo [X] Python 3.10 or newer was not found.
    echo.
    echo     Install it from https://www.python.org/downloads/windows/
    echo     or run:  winget install Python.Python.3.12
    echo.
    echo     IMPORTANT: tick "Add python.exe to PATH" in the installer.
    echo.
    pause
    exit /b 1
)

echo [*] Using Python: %PYTHON%
%PYTHON% --version

REM --------------------------------------------------------------------------
REM 2. Create or reuse the virtual environment
REM --------------------------------------------------------------------------
if not exist "%VENV_PY%" (
    echo [*] Creating virtual environment in %VENV_DIR% ...
    %PYTHON% -m venv "%VENV_DIR%"
    if !ERRORLEVEL! NEQ 0 (
        echo [X] Could not create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [*] Reusing existing virtual environment in %VENV_DIR%
)

REM --------------------------------------------------------------------------
REM 3. Install dependencies
REM --------------------------------------------------------------------------
echo [*] Installing dependencies ^(this can take a minute^) ...
"%VENV_PY%" -m pip install --quiet --upgrade pip
"%VENV_PY%" -m pip install --quiet --require-virtualenv -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [X] Dependency installation failed. Check your network connection and retry.
    pause
    exit /b 1
)
echo [*] Dependencies installed.

REM --------------------------------------------------------------------------
REM 4. Check for an API key
REM --------------------------------------------------------------------------
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [!] Created .env from .env.example - add your key to it.
    )
    echo [!] No GEMINI_API_KEY configured yet.
    echo [!] Get a free key at https://aistudio.google.com/apikey, then either put
    echo [!] it in .env as GEMINI_API_KEY=... or paste it into the app's sidebar.
)

REM --------------------------------------------------------------------------
REM 5. Launch
REM --------------------------------------------------------------------------
echo.
echo [*] Starting the app - it will open in your browser.
echo [*] Press Ctrl+C in this window to stop.
echo.
"%VENV_PY%" -m streamlit run app.py

endlocal
pause
