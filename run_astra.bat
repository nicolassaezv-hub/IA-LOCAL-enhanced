@echo off
REM Activar entorno virtual
call venv\Scripts\activate

REM Entrar a la carpeta astra
cd astra

REM Ejecutar la IA
python main.py

REM Mantener ventana abierta al terminar
pause
