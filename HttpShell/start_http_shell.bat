@echo off
setlocal
set HTTP_SHELL_TOKEN=change-me-to-a-complex-token
cd /d "%~dp0"
python "%~dp0http_shell.py" --host 127.0.0.1 --port 8080 --token "%HTTP_SHELL_TOKEN%"
