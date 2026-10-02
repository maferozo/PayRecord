@echo off
REM Tarea diaria de PAYRECORD: genera los periodos mensuales pendientes y
REM los recordatorios que correspondan. Idempotente: se puede ejecutar de
REM mas sin que se dupliquen datos.
REM
REM Registrada en el Programador de tareas de Windows (ver docs/instalacion-en-otro-equipo.md).

cd /d "%~dp0.."
".venv\Scripts\python.exe" manage.py generar_obligaciones_recurrentes
".venv\Scripts\python.exe" manage.py generar_recordatorios
