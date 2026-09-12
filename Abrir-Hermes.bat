@echo off
setlocal
title VMP-AI CLI - VMP-AI
cd /d "%~dp0hermes-agent"
set "HERMES_HOME=%~dp0"
echo ==========================================
echo  VMP-AI CLI - VMP-AI
echo  HERMES_HOME: %HERMES_HOME%
echo  Pasta: %CD%
echo ==========================================
echo.
set "HERMES_EXE=%~dp0hermes-agent\venv\Scripts\hermes.exe"
if not exist "%HERMES_EXE%" set "HERMES_EXE=%~dp0bin\hermes.exe"
if not exist "%HERMES_EXE%" (
  echo [ERRO] hermes.exe nao encontrado.
  echo.
  echo Voce precisa rodar o setup primeiro:
  echo   Duplo-clique em setup.bat  na raiz do projeto
  echo   Ou: powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  echo.
  pause
  exit /b 1
)
if not exist "%~dp0.env" (
  echo [AVISO] .env nao encontrado. O setup cria automaticamente.
  echo Rode setup.bat antes, ou copie .env.example para .env e preencha 1 chave.
  echo Continuando mesmo assim (fallback local pode funcionar)...
  echo.
)
REM CROWORK auto-start: cria/entra na sala padrão ampliagro-sprint (via python handler - sempre disponível)
if not exist "%~dp0crowork" mkdir "%~dp0crowork" >nul 2>&1
set "PY=%~dp0hermes-agent\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "%~dp0crowork\ampliagro-sprint.json" (
  echo [CROWORK] criando sala padrão ampliagro-sprint...
  "%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['create','ampliagro-sprint','Sprint Agro 5.0 - sala padrao VMP-AI']))" >nul 2>&1
)
echo [CROWORK] entrando em ampliagro-sprint...
"%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['join','ampliagro-sprint']))" >nul 2>&1
"%PY%" -c "from hermes_cli.crowork import handle_crowork; print(handle_crowork(['share','ampliagro-sprint']))"
echo.
"%HERMES_EXE%" %*
echo.
echo Hermes saiu com codigo %errorlevel%
pause