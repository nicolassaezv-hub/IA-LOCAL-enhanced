@echo off
call venv\Scripts\activate
for /f "skip=2 tokens=1" %%i in ('pip list --outdated') do pip install --upgrade %%i
pause
