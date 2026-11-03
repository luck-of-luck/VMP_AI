@echo off
setlocal enabledelayedexpansion
title Cluster 10 IAs - status - VMP-AI

REM ---------------------------------------------------------------------------
REM Por que este arquivo e tao defensivo
REM
REM MEDIDO (2026-10-01), tres defeitos que eu cometi e corrigi aqui:
REM   1. `goto :label` DENTRO de bloco ( ... ) engolia a linha seguinte no
REM      CMD: o "de duplo-clique em Abrir-Cluster-10.bat" nunca aparecia
REM      justamente quando o motor estava fora do ar. Por isso NAO ha goto
REM      dentro de bloco; o fluxo usa variaveis de flag.
REM   2. %TEMP% nao expande dentro de bloco no redirecionamento. Caminho
REM      absoluto de proposito.
REM   3. `|` dentro de echo nao escape fecha o comando. O pipe precisa de ^.
REM ---------------------------------------------------------------------------

echo ==========================================
echo  Cluster de 10 IAs - verificacao
echo ==========================================
echo.

set "MOTOR=0"
set "TOOL=0"
set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
set "MCP=%LOCALAPPDATA%\hermes\VMP-AI\cluster\mcp_server.py"
set "PROBE=%LOCALAPPDATA%\hermes\.cluster_mcp_probe.jsonl"
set "POUT=%LOCALAPPDATA%\hermes\.cluster_mcp_out.txt"

REM --- 1. o motor responde? ---
echo [1/3] Motor HTTP
curl -s --max-time 5 http://127.0.0.1:8791/health 2>nul
if errorlevel 1 (
  echo   NAO responde em http://127.0.0.1:8791
  echo   ^(de duplo-clique em Abrir-Cluster-10.bat e DEIXE ABERTO^)
) else (
  set "MOTOR=1"
  echo   ^<-- OK
)
echo.

if "%MOTOR%"=="1" goto :ferramenta

:fim
echo.
pause
exit /b 0

:ferramenta
REM --- 2. a tool MCP responde? ---
REM Testa de verdade: manda initialize + tools/list e le a resposta. Um
REM findstr sobre a saida nao serviria porque o MCP e um processo que
REM ESPERA input -- medido: pipeo direto nao traz resposta alguma.
echo [2/3] Tool do OpenCode ^(vmp-cluster_cluster_consultar^)
if not exist "%MCP%" (
  echo   NAO achei o MCP em:
  echo     %MCP%
  echo   ^-^> o agente hermes-10 vai pedir a tool e ela nao vem
) else (
  if not exist "%PY%" (
    echo   NAO achei o python em:
    echo     %PY%
    echo   ^-^> ajuste o caminho do vmp-cluster no opencode.jsonc
  ) else (
    >  "%PROBE%" echo {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
    >>"%PROBE%" echo {"jsonrpc":"2.0","id":2,"method":"tools/list"}
    "%PY%" "%MCP%" < "%PROBE%" 2>nul > "%POUT%"
    findstr /C:"cluster_consultar" "%POUT%" >nul 2>nul
    if errorlevel 1 (
      echo   as tools nao vieram ^(MCP nao respondeu^)
      echo   ^-^> reinicie o OpenCode
    ) else (
      set "TOOL=1"
      echo   tools registradas: OK
    )
    del /Q "%PROBE%" "%POUT%" >nul 2>nul
  )
)
echo.

if "%TOOL%"=="1" goto :consulta

goto :fim

:consulta
REM --- 3. quanto custa uma consulta real? ---
echo [3/3] Consulta real com 3 agentes ^(alguns segundos^)
powershell -NoProfile -Command ^
  "$b=@{pergunta='Responda apenas: ok';n=3}|ConvertTo-Json;" ^
  "$sw=[Diagnostics.Stopwatch]::StartNew();" ^
  "try{$r=Invoke-RestMethod 'http://127.0.0.1:8791/consultar' -Method Post -Body $b -ContentType 'application/json' -TimeoutSec 180;" ^
  "$sw.Stop();" ^
  "Write-Host ('   ' + $r.ok + '/' + $r.total + ' agentes em ' + [math]::Round($sw.Elapsed.TotalSeconds,1) + 's');" ^
  "if($r.ok -lt $r.total){Write-Host '   ATENCAO: faltou lente - a resposta veio incompleta'}}" ^
  "catch{Write-Host '   FALHOU: ' + $_.Exception.Message}"
echo.
echo Para usar 10 IAs de verdade, escolha o agente "hermes-10" no OpenCode.
echo   pergunta curta  ~7s   ^|   lendo arquivo  83s a 187s
echo.
goto :fim