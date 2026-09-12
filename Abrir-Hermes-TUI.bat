@echo off
setlocal
title Hermes - TUI - VMP-AI
cd /d "%~dp0hermes-agent"
set "HERMES_HOME=%~dp0"
echo ==========================================
echo  Hermes TUI - VMP-AI
echo  HERMES_HOME: %HERMES_HOME%
echo ==========================================
echo.
set "HERMES_EXE=%~dp0hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%~dp0bin\hermes.exe"
if not exist "%HERMES_EXE%" (
  echo [ERRO] hermes.exe nao encontrado.
  echo Rode antes: duplo-clique em setup.bat
  echo Ou: powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  pause
  exit /b 1
)
if not exist "%~dp0.env" (
  echo [AVISO] .env nao encontrado. Rode setup.bat primeiro.
  echo.
)
echo [CROWORK] preparando sala ampliagro-sprint...
if not exist "%~dp0crowork" mkdir "%~dp0crowork" >nul 2>&1
set "PY=%~dp0hermes-agent\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "%~dp0crowork\ampliagro-sprint.json" "%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['create','ampliagro-sprint','Sprint Agro 5.0 - sala padrao VMP-AI']))" >nul 2>&1
"%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['join','ampliagro-sprint']))" >nul 2>&1
"%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['share','ampliagro-sprint']))"
echo Iniciando Hermes TUI...
"%HERMES_EXE%" --tui
pause