@echo off
chcp 65001 > nul
title Instalador MecatroniCar - Oficina Mecânica

echo ====================================================================
echo             MecatroniCar - Instalador e Inicializador
echo ====================================================================
echo.

set "TARGET_DIR=%USERPROFILE%\Documents\Projetos\APP Oficina"

if not exist "%TARGET_DIR%" (
    echo Criando pasta do aplicativo em: "%TARGET_DIR%"
    mkdir "%TARGET_DIR%"
)

echo Verificando dependencias necessarias...
python -m pip install --quiet openpyxl xlrd flask customtkinter

echo.
echo Criando atalho na Area de Trabalho...
cd /d "%~dp0"
python criar_atalho_desktop.py

echo.
echo ====================================================================
echo   Instalacao concluida com sucesso!
echo   Iniciando o MecatroniCar...
echo ====================================================================
echo.

start "" python app.py
exit
