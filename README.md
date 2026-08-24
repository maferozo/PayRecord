# PAYRECORD

Aplicación web para la **gestión centralizada de obligaciones financieras**.
Permite registrar pagos, controlar sus fechas y estados, configurar recordatorios y
saber qué obligaciones requieren atención primero.

Proyecto de trabajo de grado.

---

## Estado del desarrollo

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Análisis y arquitectura | ✅ Completada — [`docs/00-analisis-fase0.md`](docs/00-analisis-fase0.md) |
| 1 | Configuración del proyecto | ✅ Completada |
| 2 | Usuarios y autenticación | ✅ Completada |
| 3 | Categorías | ✅ Completada |
| 4 | Obligaciones | ✅ Completada |
| 5 | Dashboard y prioridades | ✅ Completada |
| 6 | Calendario | ✅ Completada |
| 7 | Recordatorios | ✅ Completada |
| 8 | Historial y estadísticas | ✅ Completada — **MVP funcional** |
| 9 | Escenario empresarial | ⏳ Siguiente |
| 10 | Insights | ⏳ |
| 11 | Seguridad y pruebas | ⏳ |
| 12 | Documentación | ⏳ |

---

## Requisitos

- **Python 3.12.x**
- **MySQL 8.0**
- Git

---

## Instalación

### 1. Clonar y entrar al proyecto

```bash
git clone <url-del-repositorio>
cd PayRecord
```

### 2. Crear el entorno virtual e instalar dependencias

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. Crear la base de datos

En MySQL Workbench o en la consola de MySQL, ejecutar el script incluido:

```sql
SOURCE scripts/crear_base_datos.sql;
```

Crea la base `payrecord` con codificación `utf8mb4` y el usuario `payrecord`.

### 4. Configurar las variables de entorno

```powershell
copy .env.example .env
```

Editar `.env` y rellenar como mínimo:

- `SECRET_KEY` — cualquier cadena larga y aleatoria
- `DB_PASSWORD` — la contraseña del usuario `payrecord`
- `DB_ENGINE=mysql`

> `.env` **no se versiona**. Contiene credenciales.

### 5. Aplicar migraciones y arrancar

```powershell
python manage.py migrate
python manage.py cargar_categorias    # catálogo predeterminado (§8)
python manage.py runserver
```

La aplicación queda en <http://127.0.0.1:8000/>

---

## Comandos habituales

```powershell
python manage.py test apps           # ejecutar todas las pruebas
python manage.py check               # verificar la configuración
python manage.py createsuperuser     # crear un administrador
python manage.py cargar_categorias   # catálogo predeterminado (idempotente)
python manage.py cargar_datos_prueba # datos ficticios de desarrollo (§37)
python manage.py generar_recordatorios          # proceso diario (idempotente)
python manage.py generar_recordatorios --fecha 2026-08-25   # simular un día

# Cobertura de pruebas
coverage run manage.py test apps
coverage report
```

---

## Tarea programada

El proceso de recordatorios debe ejecutarse a diario. En Windows, con el
Programador de tareas:

- **Programa:** `c:\Kompras-V2\PayRecord\.venv\Scripts\python.exe`
- **Argumentos:** `manage.py generar_recordatorios`
- **Iniciar en:** `c:\Kompras-V2\PayRecord`
- **Frecuencia:** diaria, por ejemplo a las 07:00

Si el equipo está apagado a esa hora la tarea no corre, así que la aplicación
también recupera los avisos atrasados al abrir el dashboard, una vez al día.
Como el proceso es idempotente, ejecutarlo de más nunca duplica nada.

## Estructura

```text
PayRecord/
├── config/            # configuración del proyecto Django
│   └── settings/      # base.py · local.py · production.py
├── apps/
│   ├── core/          # utilidades transversales, mixins de seguridad
│   ├── usuarios/      # autenticación, tipos de usuario, empresas
│   ├── obligaciones/  # entidad central, categorías, estados, prioridades
│   ├── recordatorios/ # programación, generación, canales de notificación
│   ├── dashboard/     # resumen operativo y calendario
│   └── analitica/     # estadísticas e insights
├── templates/
├── static/
│   └── vendor/        # Bootstrap y Chart.js locales (sin CDN)
├── docs/              # análisis, modelo de datos, manual
└── scripts/           # scripts SQL de apoyo
```

La arquitectura, el modelo de datos y las decisiones de diseño están explicadas en
[`docs/00-analisis-fase0.md`](docs/00-analisis-fase0.md).

---

## Tecnologías

Python 3.12 · Django 5.2 LTS · MySQL 8.0 · HTML5 · CSS3 · JavaScript · Bootstrap 5.3 ·
Chart.js 4.4
