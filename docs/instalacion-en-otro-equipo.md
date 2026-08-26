# Instalar PAYRECORD en otro computador

Guía para montar el proyecto desde cero en un equipo nuevo, incluida la copia
de la base de datos.

---

## 1. Programas que hay que instalar

| Programa | Dónde | Notas |
|---|---|---|
| **Python 3.12** | [python.org/downloads](https://www.python.org/downloads/) | **Marcar «Add python.exe to PATH»** en la primera pantalla del instalador |
| **MySQL Community Server 8.x** | [dev.mysql.com/downloads/installer](https://dev.mysql.com/downloads/installer/) | Elegir «Developer Default». **Anotar la contraseña de root** que se defina |
| **Git** | [git-scm.com/downloads](https://git-scm.com/downloads) | Todo por defecto |
| **Visual Studio Code** | [code.visualstudio.com](https://code.visualstudio.com/) | |

> Con el MySQL Installer viene también **MySQL Workbench**, que es la
> aplicación gráfica para manejar la base de datos. Conviene instalarlo.

---

## 2. Extensiones de Visual Studio Code

Se instalan desde el icono de bloques del panel izquierdo (`Ctrl+Shift+X`),
buscando por nombre.

### Imprescindibles

| Extensión | Editor / ID | Para qué |
|---|---|---|
| **Python** | `ms-python.python` | Reconoce Python, ejecuta y depura |
| **Pylance** | `ms-python.vscode-pylance` | Autocompletado y errores mientras se escribe |
| **Django** | `batisteo.vscode-django` | Colorea las plantillas `.html` de Django (sin esto se ven en gris) |

### Muy recomendables

| Extensión | ID | Para qué |
|---|---|---|
| **Ruff** | `charliermarsh.ruff` | Detecta código no usado y errores de estilo |
| **SQLTools** + **SQLTools MySQL** | `mtxr.sqltools`, `mtxr.sqltools-driver-mysql` | Consultar la base de datos sin salir del editor |
| **Even Better TOML** | `tamasfe.even-better-toml` | Archivos de configuración |
| **Error Lens** | `usernamehw.errorlens` | Muestra el error en la misma línea, no solo abajo |
| **GitLens** | `eamodio.gitlens` | Ver quién cambió cada línea y cuándo |

Instalar todas de golpe: abrir la terminal de VS Code y pegar:

```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension batisteo.vscode-django
code --install-extension charliermarsh.ruff
code --install-extension mtxr.sqltools
code --install-extension mtxr.sqltools-driver-mysql
code --install-extension usernamehw.errorlens
code --install-extension eamodio.gitlens
```

> El proyecto ya trae `.vscode/settings.json` y `.vscode/extensions.json`, así
> que al abrir la carpeta VS Code ofrecerá instalar las recomendadas solo.

---

## 3. Descargar el proyecto

```powershell
cd C:\
git clone https://github.com/felipino25/PayRecord.git
cd PayRecord
```

---

## 4. Preparar el entorno de Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Si al activar el entorno PowerShell se queja de que la ejecución de scripts
está deshabilitada:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Y volver a intentarlo. Cuando el entorno está activo, la línea de comandos
empieza por `(.venv)`.

---

## 5. La base de datos

Hay dos caminos. **El B es el recomendado** si solo se necesita el proyecto
funcionando; el A sirve si además se quieren los datos exactos del otro
equipo.

### Opción A — Copiar la base de datos completa

**En el computador de origen**, generar el archivo de respaldo:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe" -u root -p `
    --databases payrecord `
    --add-drop-database `
    --default-character-set=utf8mb4 `
    --result-file=payrecord_respaldo.sql
```

Pedirá la contraseña de root. Genera `payrecord_respaldo.sql`, que se puede
enviar por correo, USB o WeTransfer.

> **No subir ese archivo a GitHub**: contiene datos y hashes de contraseñas.

**En el computador de destino**, crear el usuario y restaurar:

```powershell
# 1. Crear la base y el usuario de la aplicación
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p -e "CREATE DATABASE IF NOT EXISTS payrecord CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'payrecord'@'localhost' IDENTIFIED BY 'LA_QUE_ELIJAS'; GRANT ALL PRIVILEGES ON payrecord.* TO 'payrecord'@'localhost'; GRANT ALL PRIVILEGES ON \`test\_payrecord\`.* TO 'payrecord'@'localhost'; FLUSH PRIVILEGES;"

# 2. Restaurar el respaldo
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p payrecord < payrecord_respaldo.sql
```

También se puede hacer desde **MySQL Workbench**: conectarse, menú
`Server → Data Import → Import from Self-Contained File`, elegir el `.sql`
y pulsar *Start Import*.

### Opción B — Crear la base vacía y generar datos de prueba

Más limpio: no arrastra datos de nadie y deja el proyecto listo para usar.

```powershell
# 1. Crear la base y el usuario (mismo comando que arriba, paso 1)

# 2. Después de configurar el .env (paso 6), crear las tablas
python manage.py migrate
python manage.py cargar_categorias
python manage.py cargar_datos_prueba
python manage.py createsuperuser
```

`cargar_datos_prueba` crea dos cuentas de ejemplo con 14 obligaciones en los
cuatro estados:

| Cuenta | Correo | Contraseña |
|---|---|---|
| Personal | maria@example.com | Demo12345 |
| Empresa | gerente@comercialxyz.com | Demo12345 |

---

## 6. Configurar el archivo `.env`

El archivo `.env` **no viene en el repositorio** porque contiene contraseñas.
Hay que crearlo a partir de la plantilla:

```powershell
copy .env.example .env
```

Abrirlo en VS Code y rellenar:

```ini
SECRET_KEY=una-cadena-larga-y-aleatoria-cualquiera
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_ENGINE=mysql
DB_NAME=payrecord
DB_USER=payrecord
DB_PASSWORD=la-que-se-eligio-al-crear-el-usuario
DB_HOST=127.0.0.1
DB_PORT=3306
```

Para generar una `SECRET_KEY` sin inventarla a mano:

```powershell
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

> Si el archivo se guarda con **codificación UTF-8 con BOM**, Django ignora
> la primera línea en silencio. En VS Code, abajo a la derecha debe decir
> `UTF-8`, no `UTF-8 with BOM`.

---

## 7. Arrancar

```powershell
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>. Para detenerlo, `Ctrl+C`.

Comprobar que todo está bien:

```powershell
python manage.py check
python manage.py test apps --noinput
```

Deberían pasar las 348 pruebas.

---

## 8. Problemas frecuentes

**`Can't connect to MySQL server`**
El servicio de MySQL no está arrancado. Comprobar con
`Get-Service MySQL*`; si aparece `Stopped`, ejecutar `Start-Service` con el
nombre que muestre.

**`Access denied for user 'payrecord'@'localhost'`**
La contraseña del `.env` no coincide con la del usuario de MySQL. Recrear el
usuario con la contraseña correcta.

**`No module named 'django'`**
El entorno virtual no está activo. Falta ejecutar `.venv\Scripts\activate`
(la línea debe empezar por `(.venv)`).

**`ModuleNotFoundError: No module named 'MySQLdb'`**
Falta instalar dependencias: `pip install -r requirements.txt`.

**La página se ve sin estilos**
Comprobar que existe la carpeta `static/vendor/`. Si se clonó bien el
repositorio, está incluida.
