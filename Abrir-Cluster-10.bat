@echo off
setlocal
title Cluster 10 IAs - VMP-AI
if exist "%~dp0plugins\cluster\engine-server.ts" (cd /d "%~dp0") else (cd /d "%USERPROFILE%\.config\opencode")

echo ==========================================
echo  Cluster de 10 IAs - motor
echo  Este processo e o motor do comite.
echo  DEIXE ESTA JANELA ABERTA.
echo ==========================================
echo.

set "ENGINE=%CD%\plugins\cluster\engine-server.ts"
if not exist "%ENGINE%" (
  echo [ERRO] engine-server.ts nao encontrado em:
  echo        %ENGINE%
  echo.
  echo O cluster do OpenCode depende deste arquivo.
  echo Se voce moveu o cluster, ajuste o caminho aqui.
  pause
  exit /b 1
)

where node >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERRO] node nao encontrado no PATH.
  echo Instale via: https://nodejs.org/
  pause
  exit /b 1
)

REM Se o motor ja estiver no ar, avisar em vez de subir um segundo.
curl -s --max-time 3 http://127.0.0.1:8791/health >nul 2>nul
if %errorlevel% equ 0 (
  echo [AVISO] Ja existe um motor em http://127.0.0.1:8791
  echo         ^(10 perfis prontos^)
  echo.
  echo Fechar esta janela NAO derruba o outro motor.
  echo Se quiser reiniciar, feche a outra janela primeiro.
  echo.
  echo Verificando saude...
  curl -s --max-time 5 http://127.0.0.1:8791/health
  echo.
  pause
  exit /b 0
)

echo Portas e argumentos:
echo   - porta 8791, so em 127.0.0.1 ^(nao expoe na rede^)
echo   - 10 perfis: correcao, seguranca, contrato, concorrencia,
echo     legibilidade, erros, dados, dependencias, testes, sintese
echo.
echo Iniciando motor...
echo   (Ctrl+C encerra. Para o motor voltar, rode este arquivo de novo.)
echo.
echo ------------------------------------------------------------
node "%ENGINE%"
echo.
echo [INFO] O motor foi encerrado.
echo As tools vmp-cluster_cluster_consultar vao responder erro
echo "nao consegui falar com o motor" ate voce subir de novo.
pause