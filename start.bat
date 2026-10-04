@echo off
rem Starts InvestIQ AI on this laptop and opens it in your browser.
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo The project's virtual environment ^(.venv^) was not found.
    echo Open a terminal in this folder and run these two commands, then try again:
    echo.
    echo     py -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

rem Open the browser a few seconds from now, giving the server time to start.
start "" /min cmd /c "ping -n 4 127.0.0.1 >nul & start http://localhost:8000"

echo InvestIQ AI is starting at http://localhost:8000
echo Close this window ^(or press Ctrl+C^) to stop the app.
echo.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

echo.
echo The app has stopped. Scroll up to see why if this was unexpected.
pause
