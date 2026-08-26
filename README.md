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
| 9 | Escenario empresarial | ✅ Completada |
| 10 | Insights | ✅ Completada |
| 11 | Seguridad y pruebas | ✅ Completada — 346 pruebas, 95.8% de cobertura |
| 12 | Documentación | ✅ Completada |

**Las doce fases están cerradas.** La aplicación cubre por completo el MVP
definido en el análisis.

---

## Documentación

| Documento | Contenido |
|---|---|
| [Análisis y decisiones](docs/00-analisis-fase0.md) | Arquitectura propuesta, modelo E-R, riesgos y las 10 decisiones de diseño |
| [Arquitectura](docs/arquitectura.md) | Capas, apps, invariantes del sistema y puntos de extensión |
| [Modelo de datos](docs/modelo-datos.md) | Las 8 tablas, restricciones e integridad referencial |
| [Casos de uso](docs/casos-de-uso.md) | Los 18 casos, cada uno con la prueba que lo verifica |
| [Manual de usuario](docs/manual-usuario.md) | Guía funcional para quien usa la aplicación |
| [Informe de pruebas](docs/pruebas.md) | Cobertura, casos exigidos por la especificación y limitaciones |
| [Instalar en otro equipo](docs/instalacion-en-otro-equipo.md) | Montar el proyecto desde cero: programas, extensiones de VS Code y copia de la base de datos |
| [Publicar en Azure](docs/despliegue-azure.md) | Despliegue paso a paso en App Service + MySQL, con lo que es gratis y lo que no |

---

## Requisitos

- **Python 3.12.x**
- **MySQL 8.0 o superior** (probado en 8.4)
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
coverage run manage.py test apps --noinput
coverage report
coverage html        # informe navegable en htmlcov/index.html

# Revisión de seguridad antes de desplegar
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
python manage.py check --deploy
```

> Con `HTTPS_ACTIVO=True` en el `.env`, `check --deploy` no reporta ningún aviso.
> Sin HTTPS quedan cuatro, todos relativos a SSL: activarlos sin certificado
> dejaría la aplicación inaccesible.

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

Python 3.12 · Django 5.2 LTS · MySQL 8.4 · HTML5 · CSS3 · JavaScript · Bootstrap 5.3 ·
Chart.js 4.4

Sin Docker, sin Celery, sin npm. Cuatro dependencias de producción.

---

## Qué hace distinto a PAYRECORD

No es un CRUD de pagos. Tres cosas concretas:

**Los estados no se actualizan a mano.** Se derivan de la fecha y de si está
pagada, en Python y en SQL, con una prueba que compara ambos caminos. Nunca
quedan desfasados.

**Las prioridades se explican.** El algoritmo da un puntaje de 0 a 100 y,
sobre todo, **los motivos en texto**: «vence mañana», «monto alto frente a
tus obligaciones pendientes». Es análisis determinístico, no IA simulada.

**Los recordatorios no se duplican, y la garantía está en la base de datos.**
Una restricción única sobre `(obligación, días, fecha, canal)`, no una
comprobación en Python que podría fallar por concurrencia. Eso permite
además recuperar los avisos atrasados al abrir el dashboard, resolviendo que
la tarea programada no corra con el equipo apagado.
