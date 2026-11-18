# Taskflow API local

Esta API REST usa FastAPI y el módulo `sqlite3` incluido con Python. No necesita instalar un servidor SQLite. La API es independiente del frontend actual; este todavía guarda sus datos en el navegador.

## Requisitos

- Python 3.12 o posterior.
- PowerShell en Windows.

## Preparar el entorno

Desde PowerShell, entra a esta carpeta y crea el entorno virtual fuera de OneDrive:

```powershell
$venv = "$env:LOCALAPPDATA\TaskflowAPI\.venv"
py -3.12 -m venv $venv
& "$venv\Scripts\python.exe" -m pip install -r .\requirements.txt
```

La base de datos se crea automáticamente en `%USERPROFILE%\.taskflow\taskflow.db`, fuera de la carpeta sincronizada del proyecto. Se puede cambiar la ubicación con la variable `TASKFLOW_DB_PATH`.

## Ejecutar la API

Desde la carpeta `api`:

```powershell
$venv = "$env:LOCALAPPDATA\TaskflowAPI\.venv"
& "$venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- Documentación interactiva: <http://127.0.0.1:8000/docs>
- Prefijo de API: `http://127.0.0.1:8000/api/v1`

Mantén la terminal abierta mientras haces pruebas. Detén el servidor con `Ctrl+C`.

## Ejecutar las pruebas automatizadas

Desde la carpeta `api`:

```powershell
$venv = "$env:LOCALAPPDATA\TaskflowAPI\.venv"
& "$venv\Scripts\python.exe" -m pytest -q
```

Las pruebas usan una base de datos temporal; no alteran la base local de desarrollo.
