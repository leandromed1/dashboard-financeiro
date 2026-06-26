@echo off
REM Atalho para abrir o Dashboard Financeiro. E so dar dois cliques neste arquivo.
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m streamlit run app.py
pause
