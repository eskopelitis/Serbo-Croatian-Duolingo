@echo off
rem Starts Nas jezik in HTTPS mode (the iPhone microphone needs HTTPS).
rem A shortcut to this file in the Windows Startup folder runs it at every logon.
rem ponytail: log is overwritten per start, so it never grows without bound.
cd /d "%~dp0"
set SONGTOLEARN_HTTPS=1
set PYTHONUTF8=1
python app.py > data\app.log 2>&1
