@echo off

cd /d "%~dp0"

if not exist backups mkdir backups

venv\Scripts\python.exe -m database.backup_db >> backups\backup.log 2>&1