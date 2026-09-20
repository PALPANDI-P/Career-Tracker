@echo off
title Career Tracker — Offline Hourly Job Bot
echo =================================================================
echo   CAREER TRACKER — HOURLY AI JOB MONITORING & EMAIL BOT (OFFLINE)
echo   Target Recipient: palulaptop@gmail.com
echo =================================================================
echo.

cd /d "%~dp0"
python hourly_job_bot.py --daemon --interval 3600 --email palulaptop@gmail.com
pause
