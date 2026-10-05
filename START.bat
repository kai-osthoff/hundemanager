@echo off
cd /d %~dp0
rem Bevorzugt "py" (kommt mit python.org) - "python" kann unter Windows 11 auf den
rem Microsoft-Store-Platzhalter zeigen, wenn der im PATH vor dem echten Python steht
where py >nul 2>nul
if %errorlevel%==0 (
    py start.py
) else (
    python start.py
)
pause
