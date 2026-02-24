@echo off
echo =========================================
echo  AI YouTube Shorts Generator — Setup
echo =========================================

:: Step 1: Create virtual environment
echo [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create venv. Is Python installed?
    pause
    exit /b 1
)

:: Step 2: Activate and install requirements
echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

:: Step 3: Check for .env file
echo [3/3] Checking for .env file...
if not exist ".env" (
    echo WARNING: .env file not found.
    echo Copying .env.template to .env — please fill in your API keys.
    copy .env.template .env
) else (
    echo .env file found.
)

echo.
echo =========================================
echo  Setup complete!
echo  Next steps:
echo    1. Edit .env with your API keys
echo    2. Run: venv\Scripts\activate
echo    3. Run: python main.py --dry-run
echo =========================================
pause
