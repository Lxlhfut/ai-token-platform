@echo off
cd /d %~dp0
if not exist data mkdir data
if not exist .env copy env.example .env
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
