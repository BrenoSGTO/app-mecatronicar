@echo off
chcp 65001 > nul
title MecatroniCar - Histórico de Veículos
cd /d "%~dp0"

echo ============================================================
echo   Iniciando MecatroniCar - Histórico da Oficina Mecânica
echo ============================================================
echo.

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao iniciar. Verifique se o Python esta instalado.
    pause
)
