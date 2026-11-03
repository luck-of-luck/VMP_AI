@echo off
setlocal
title Operarios - VMP-AI
cd /d "%~dp0"

echo ==========================================
echo  Operarios - fila de tarefas com board
echo  Roda N agentes OpenCode em paralelo.
echo  Eles so se encontram pelo board.
echo ==========================================
echo.

REM --- parametros ---
set "QTD=%~1"
if "%QTD%"=="" set "QTD=2"
set "PERFIL=%~2"
if "%PERFIL%"=="" set "PERFIL=rapido"
set "MODELO=%~3"
if "%MODELO%"=="" set "MODELO=opencode/fledge-alpha-free"

REM --- pre-requisitos ---
where opencode >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERRO] opencode nao esta no PATH. Instale: npm install -g opencode-ai
  pause
  exit /b 1
)

curl -s --max-time 4 http://127.0.0.1:8791/health >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERRO] o motor do cluster nao esta de pe.
  echo         Ele e quem guarda a fila. De duplo-clique em:
  echo           Abrir-Cluster-10.bat
  echo.
  pause
  exit /b 1
)

REM A trava de custo e do motor, nao daqui. Se ela estourar, os operarios
REM param de pegar tarefa e dizem por que. Este aviso existe so para o
REM usuario saber o que vai encontrar.
echo Configuracao:
echo   operarios : %QTD%
echo   perfil    : %PERFIL%
echo   modelo    : %MODELO%
echo.
echo A trava de custo esta no motor e vale para todos:
echo   ver com: curl http://127.0.0.1:8791/board
echo.

echo A trava de custo e do motor, nao daqui. Se ela estourar, os operarios
REM param de pegar tarefa e dizem por que. Este bloco so mostra o estado.
echo.
call :avisos
echo Rodando %QTD% operario(s). Isso abre varios processos opencode.
echo (Ctrl+C encerra; tarefas em andamento voltam para a fila pelo lease.)
echo.

REM O prompt vai em arquivo em vez de aspas na linha de comando: com aspas
REM aninhadas o CMD abre a janela VAZIA e sem erro visivel — foi o que
REM aconteceu na primeira versao deste arquivo. Arquivo evita as duas
REM camadas de escape.
for /L %%i in (1,1,%QTD%) do (
  > "%TEMP%\operario_%%i.txt" echo Use vmp-cluster_cluster_board_pegar com quem='op-%%i'. Leia os artefatos que vierem. Execute, publique, conclua. Se nao vier tarefa, responda so SEM_TAREFA e pare. Termine sempre com RESULTADO=<1 frase>.
  start "Operario %%i" /min cmd /c "opencode run --agent operario --model %MODELO% ^< ""%TEMP%\operario_%%i.txt"""
)
del /Q "%TEMP%\operario_*.txt" 2>nul

echo Os %QTD% operario(s) foram abertos em janelas separadas.
echo Acompanhe a fila com:
echo   curl http://127.0.0.1:8791/board
echo.
pause
exit /b 0

:avisos
REM MEDIDO: a versao que usava `goto` DENTRO deste :rotulo falhava com
REM "nao pode localizar o rotulo" — `goto` dentro de um bloco `call` sai
REM do bloco e procura o rotulo no arquivo inteiro. E o JSON cru do motor
REM nao ajuda ninguem: a tela pedia "2 tarefa(s)" dentro de uma linha de
REM JSON. Entao o estado vai pelo stdin do curl, que ja vem formatado.
for /f "usebackq delims=" %%a in (`curl -s --max-time 5 http://127.0.0.1:8791/board ^| python -c "import json,sys; d=json.load(sys.stdin); print(d['texto'])" 2^>nul`) do echo   %%a
exit /b 0