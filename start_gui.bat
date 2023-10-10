@echo off
setlocal

:: Step 1: Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python and add it to your PATH.
    pause
    exit /b 1
)

:: Step 2: Check if the virtual environment exists
if not exist python-env (
    echo Virtual environment not found. Please run the install.bat file to create it.
    pause
    exit /b 1
)

:: Step 3: Check if requirements are installed
echo Checking if required packages are installed...
python-env\Scripts\python.exe check_requirements.py
if %errorlevel% neq 0 (
    echo [ERROR] Some required packages are missing or an error occurred. Please run install.bat.
    deactivate
    pause
    exit /b 1
)

:: Step 4: Run the Python file
echo Running gui.py inside the elena/ directory...
cd elena
..\python-env\Scripts\python.exe gui.py

:: Restore environment to previous settings
endlocal

@echo on
