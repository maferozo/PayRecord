# Publicar PAYRECORD en Azure

Guía paso a paso para poner la aplicación en internet con Azure App Service
y Azure Database for MySQL.

---

## 0. Antes de empezar: qué es gratis y qué no

Conviene tenerlo claro para no llevarse un cobro inesperado.

| Servicio | Situación real |
|---|---|
| **App Service, plan F1 (Free)** | Gratis **siempre**. 60 min de CPU al día, 1 GB de disco, sin dominio propio ni certificado personalizado. Suficiente para una demostración |
| **Azure Database for MySQL** | **No es gratis de forma permanente.** Una cuenta nueva tiene 12 meses gratis de un servidor B1ms con 32 GB. Pasado ese plazo, se cobra |

**La mejor opción para un trabajo de grado es Azure for Students:**

- Da **100 USD de crédito por 12 meses**.
- **No pide tarjeta de crédito.**
- Se activa con el correo institucional de la universidad.
- Con ese crédito sobra de largo para tener la aplicación y la base publicadas
  durante toda la sustentación.

Registro: <https://azure.microsoft.com/free/students>

> Si no hay correo institucional, sirve la cuenta gratuita normal
> (<https://azure.microsoft.com/free>), pero **sí pide tarjeta** aunque no
> cobre nada mientras se esté en la capa gratuita.

**Importante:** al terminar la sustentación, borrar el grupo de recursos.
Es un clic y evita cualquier cobro futuro (paso 9).

---

## 1. Crear la cuenta

1. Entrar en <https://azure.microsoft.com/free/students> y pulsar
   **Empezar gratis**.
2. Iniciar sesión con la cuenta de Microsoft (o crear una).
3. Verificar la condición de estudiante con el correo institucional.
4. Al terminar se llega al **Portal de Azure**: <https://portal.azure.com>

---

## 2. Crear el grupo de recursos

Un grupo de recursos es una carpeta que agrupa todo lo del proyecto. Sirve
para borrarlo todo de una vez cuando ya no se necesite.

1. En el portal, buscar **Grupos de recursos** → **Crear**.
2. Rellenar:
   - **Nombre:** `payrecord-rg`
   - **Región:** `East US 2` (de las más baratas y con capa gratuita)
3. **Revisar y crear** → **Crear**.

---

## 3. Crear la base de datos MySQL

1. Buscar **Azure Database for MySQL** → **Crear** → **Servidor flexible**.
2. Configuración:

   | Campo | Valor |
   |---|---|
   | Grupo de recursos | `payrecord-rg` |
   | Nombre del servidor | `payrecord-mysql` (debe ser único en todo Azure) |
   | Región | La misma que el grupo: `East US 2` |
   | Versión de MySQL | `8.0` |
   | Tipo de carga de trabajo | Desarrollo |
   | Nivel de proceso | **Burstable B1ms** |
   | Método de autenticación | Autenticación de MySQL |
   | Usuario administrador | `payrecordadmin` |
   | Contraseña | Una larga. **Anotarla** |

3. En la pestaña **Redes**:
   - Método de conectividad: **Acceso público**.
   - Marcar **Permitir el acceso público a este servidor desde servicios de
     Azure**. Sin esto, App Service no podrá conectarse.
   - Añadir la IP propia con **Agregar la dirección IP del cliente actual**,
     para poder administrarla desde Workbench.

4. **Revisar y crear** → **Crear**. Tarda entre 5 y 10 minutos.

5. Cuando termine, ir al servidor → **Bases de datos** → **Agregar** y crear
   una llamada **`payrecord`** con cotejamiento `utf8mb4_unicode_ci`.

---

## 4. Cargar los datos en la base de Azure

Desde el computador local, con **MySQL Workbench**:

1. Crear una conexión nueva:
   - **Hostname:** `payrecord-mysql.mysql.database.azure.com`
   - **Puerto:** `3306`
   - **Username:** `payrecordadmin`
   - Contraseña: la del paso 3
   - En la pestaña **SSL**, poner *Use SSL* en **Require**
2. Conectarse y comprobar que aparece la base `payrecord`.

Si se quieren llevar los datos locales, generar primero el respaldo:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe" -u root -p `
    --databases payrecord --default-character-set=utf8mb4 `
    --result-file=payrecord_respaldo.sql
```

Y en Workbench, ya conectado a Azure:
`Server → Data Import → Import from Self-Contained File`.

> Si no se quieren llevar los datos, no hace falta: el propio despliegue
> ejecuta `migrate` y crea las tablas vacías.

---

## 5. Crear la aplicación web

1. Buscar **App Services** → **Crear** → **Aplicación web**.
2. Configuración:

   | Campo | Valor |
   |---|---|
   | Grupo de recursos | `payrecord-rg` |
   | Nombre | `payrecord-app` (será `payrecord-app.azurewebsites.net`) |
   | Publicar | **Código** |
   | Pila del entorno en tiempo de ejecución | **Python 3.12** |
   | Sistema operativo | **Linux** |
   | Región | `East US 2` |
   | Plan de precios | **F1 (Gratis)** |

3. **Revisar y crear** → **Crear**.

---

## 6. Configurar las variables de entorno

Este es el paso donde más gente se atasca: **el archivo `.env` no se sube a
Azure**. Las variables se configuran en el portal.

App Service → `payrecord-app` → **Configuración** → **Variables de entorno**
→ pestaña **Configuración de la aplicación**. Añadir una por una:

| Nombre | Valor |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | Una clave nueva, **distinta a la local** (ver abajo) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `payrecord-app.azurewebsites.net` |
| `HTTPS_ACTIVO` | `True` |
| `DB_ENGINE` | `mysql` |
| `DB_NAME` | `payrecord` |
| `DB_USER` | `payrecordadmin` |
| `DB_PASSWORD` | La contraseña del servidor MySQL |
| `DB_HOST` | `payrecord-mysql.mysql.database.azure.com` |
| `DB_PORT` | `3306` |
| `DB_SSL` | `True` |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (con `console...` los correos nunca salen de verdad, ver §10) |
| `EMAIL_HOST` | El servidor SMTP, p. ej. `smtp.gmail.com` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | La cuenta de correo que envía |
| `EMAIL_HOST_PASSWORD` | Su contraseña de aplicación (no la contraseña normal de la cuenta) |
| `EMAIL_USE_TLS` | `True` |
| `DEFAULT_FROM_EMAIL` | `no-responder@payrecord.local` |
| `TAREA_DIARIA_TOKEN` | Una cadena larga y aleatoria — ver §10 |
| `DIAS_PROXIMO_VENCIMIENTO_DEFAULT` | `7` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

Generar la clave para producción:

```powershell
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Pulsar **Aplicar** y confirmar el reinicio.

> `WEBSITE_HOSTNAME` la crea Azure sola, y `config/settings/base.py` ya la
> lee para añadir el dominio a `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`.

---

## 7. Indicar cómo arrancar la aplicación

App Service → **Configuración** → **Configuración general**:

- **Comando de inicio:** `bash startup.sh`

Guardar.

El archivo [`startup.sh`](../startup.sh) ya está en el repositorio y se
encarga de aplicar migraciones, recolectar los archivos estáticos, cargar las
categorías y arrancar gunicorn.

---

## 8. Desplegar el código

La forma más cómoda es conectar GitHub: cada `git push` publica solo.

1. App Service → **Centro de implementación**.
2. **Origen:** GitHub. Autorizar la cuenta si lo pide.
3. Seleccionar:
   - Organización: la cuenta de GitHub
   - Repositorio: `PayRecord`
   - Rama: `main`
4. **Tipo de autenticación:** identidad administrada por el usuario.
5. **Guardar.**

Azure crea un workflow de GitHub Actions y lanza el primer despliegue. Tarda
entre 5 y 10 minutos. El avance se ve en la pestaña **Registros** o en la
sección *Actions* del repositorio en GitHub.

Cuando termine, la aplicación está en:

```
https://payrecord-app.azurewebsites.net
```

### Crear el usuario administrador

App Service → **Herramientas de desarrollo** → **SSH** → **Ir**:

```bash
cd /home/site/wwwroot
python manage.py createsuperuser
```

Para cargar los datos de ejemplo:

```bash
python manage.py cargar_datos_prueba
```

---

## 9. Al terminar: borrar todo

Para evitar cualquier cobro cuando el proyecto ya no se necesite:

Portal → **Grupos de recursos** → `payrecord-rg` → **Eliminar grupo de
recursos**. Pide escribir el nombre para confirmar. Eso borra la aplicación y
la base de datos de una vez.

> Si se quiere conservar el trabajo, hacer antes un `mysqldump` de la base de
> Azure para tener una copia local.

---

## 10. Los recordatorios en Azure

El plan gratuito **no ejecuta tareas programadas propias de Azure**: los
WebJobs necesitan un plan de pago (B1 o superior), y este despliegue usa F1.

Hay dos mecanismos, uno encima del otro:

**1. Recuperación al abrir la app (ya existe, sin configurar nada).**
PAYRECORD genera los periodos mensuales y los recordatorios atrasados cada
vez que alguien abre el dashboard, una vez al día por sesión. Mientras
alguien entre a la aplicación, los avisos se generan y se envían.

**2. Tarea diaria sin costo, vía GitHub Actions (recomendada para que
funcione aunque nadie abra la app ese día).**
El repositorio ya trae un workflow programado,
[`.github/workflows/tarea-diaria.yml`](../.github/workflows/tarea-diaria.yml),
que llama una vez al día (8:00 a.m. hora de Bogotá) a un endpoint protegido
de PAYRECORD: `POST /notificaciones/tarea-diaria/`. GitHub Actions es
gratuito para este uso y no requiere subir de plan en Azure.

Para activarla:

1. En Azure, poner la variable de entorno `TAREA_DIARIA_TOKEN` con una
   cadena larga y aleatoria (§6). Mientras esté vacía, el endpoint responde
   503 y no hace nada — es la forma de tenerlo "apagado" a propósito.
2. En GitHub: `Settings` → `Secrets and variables` → `Actions` →
   `New repository secret`, y crear dos:
   - `TAREA_DIARIA_URL` = `https://<tu-app>.azurewebsites.net/notificaciones/tarea-diaria/`
   - `TAREA_DIARIA_TOKEN` = el mismo valor que se puso en Azure
3. Para comprobar que funciona sin esperar al cron: pestaña **Actions** del
   repositorio → **Tarea diaria de PayRecord** → **Run workflow**. El
   resultado (periodos creados, recordatorios creados/enviados/con error)
   queda en el log de ese run.

Es seguro que se ejecute más de una vez el mismo día (por ejemplo, si se
dispara a mano además del cron): tanto la generación de periodos como la de
recordatorios son idempotentes, no duplican nada.

Si más adelante hiciera falta algo más robusto (reintentos gestionados,
monitoreo, ejecución garantizada por SLA), las opciones son subir al plan B1
de Azure y usar un WebJob, o una Azure Function con temporizador.

---

## 11. Problemas frecuentes

**`Application Error` al abrir la página**
Revisar los registros: App Service → **Flujo de registro**. Casi siempre es
una variable de entorno mal escrita o que falta.

**`DisallowedHost` en los registros**
Falta el dominio en `ALLOWED_HOSTS`. Comprobar que dice exactamente
`payrecord-app.azurewebsites.net`, sin `https://` ni barra final.

**`Can't connect to MySQL server`**
En el servidor MySQL → **Redes**, verificar que está marcado *Permitir el
acceso público desde servicios de Azure*.

**`SSL connection is required`**
Falta la variable `DB_SSL` con valor `True`.

**La página se ve sin estilos**
`collectstatic` falló en el arranque. Revisar los registros; suele ser que
`DJANGO_SETTINGS_MODULE` no apunta a `config.settings.production`.

**Error CSRF al iniciar sesión**
`HTTPS_ACTIVO` debe estar en `True` para que las cookies se marquen como
seguras detrás del balanceador de Azure.

**La aplicación tarda en responder la primera vez**
Normal en el plan gratuito: la aplicación se suspende tras 20 minutos de
inactividad y tarda unos segundos en despertar.
