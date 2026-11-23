@echo off
rem Starts the BJJ Library server (if it isn't already running) and opens the library in your browser.
rem The server only listens on this PC (127.0.0.1) and stops by itself after 4 hours unused.
cd /d "%~dp0"
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:8765/api/ping | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  start "" pythonw "%~dp0server.py"
  powershell -NoProfile -Command "for ($i=0; $i -lt 20; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:8765/api/ping | Out-Null; break } catch { Start-Sleep -Milliseconds 250 } }"
)
start "" "http://127.0.0.1:8765/_BJJ%%20Library/index.html"
