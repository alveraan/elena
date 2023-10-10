@echo off
setlocal

:: Check if python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python and add it to your PATH.
    pause
    exit /b 1
)

:: Remove existing virtual environment if it exists
if exist python-env (
    echo Removing existing virtual environment...
    rmdir /s /q python-env
)

:: Create a new Python virtual environment
echo Creating new virtual environment...
python -m venv python-env

:: Activate the virtual environment
echo Activating virtual environment...
call python-env\Scripts\activate

:: Install required packages
echo Installing required packages from requirements.txt...
pip install -r requirements.txt

:: Check if elena\oo2core_8_win64.dll exists
if not exist elena\oo2core_8_win64.dll (
    echo.
    echo WARNING: The file elena\oo2core_8_win64.dll was not found.
    echo It is required if you want to open compressed map .entities files.
    echo Copy it from the Doom Eternal install directory into the elena directory.
    echo Otherwise, you'll need to decompress the files with a different tool first.
)

echo.
echo.
echo Installation complete. If no errors occured above, you can launch the application using start.bat

set /p =Press ENTER to close this window...

:: Deactivate the virtual environment
echo Deactivating virtual environment...
deactivate

:: Restore environment to previous settings
endlocal

@echo on
