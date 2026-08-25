# PAYRECORD — Arquitectura

Cómo está organizado el código y por qué. El análisis previo y las
decisiones de diseño están en [`00-analisis-fase0.md`](00-analisis-fase0.md);
este documento describe lo que finalmente se construyó.

---

## 1. Estilo

**Monolito modular en Django, patrón MVT con una capa de servicios.**

Un solo proyecto, un solo despliegue, una sola base de datos. Sin
microservicios, sin Docker, sin Celery. La modularidad se consigue con apps
Django delimitadas, no con procesos separados.

Es una decisión deliberada: para el alcance de PAYRECORD, un monolito bien
organizado es más fácil de desarrollar, probar, desplegar y defender que una
arquitectura distribuida que no resolvería ningún problema real.

---

## 2. Capas

```
┌──────────────────────────────────────────────────────────────┐
│  PRESENTACIÓN                                                 │
│  templates/ · static/ · views.py · urls.py · forms.py         │
│  Recibe la petición, valida la entrada, elige el template.    │
│  NO contiene reglas de negocio.                               │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  NEGOCIO                                                      │
│  services/  → operaciones que escriben o calculan             │
│  selectors/ → consultas de solo lectura reutilizables         │
│  Estados, prioridades, generación de recordatorios, insights. │
│  Funciones puras siempre que es posible.                      │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  DATOS                                                        │
│  models.py · managers.py · migrations/                        │
│  ORM de Django. Invariantes y restricciones en la base.       │
└──────────────────────────────────────────────────────────────┘
```

**Regla práctica:** un módulo sin reglas de negocio no tiene capa de
servicios. El CRUD de categorías no la tiene; obligaciones, recordatorios y
analítica sí.

---

## 3. Apps

| App | Modelos | Responsabilidad | Servicios |
|---|---|---|---|
| `core` | `ModeloBase` (abstracto) | Mixins de autorización, filtros de plantilla, context processors | — |
| `usuarios` | `Empresa`, `Usuario`, `ConfiguracionUsuario` | Autenticación, tipos de cuenta, perfil | — |
| `obligaciones` | `Categoria`, `Obligacion` | Entidad central, CRUD, estados, prioridades, proveedores | ✅ |
| `recordatorios` | `ConfiguracionRecordatorio`, `Recordatorio`, `Notificacion` | Programación, generación, canales | ✅ |
| `dashboard` | — | Resumen operativo y calendario | Selectores |
| `analitica` | — | Estadísticas e insights | ✅ |

Dependencias, sin ciclos:

```
core  ←  usuarios  ←  obligaciones  ←  recordatorios
                            ↑                 ↑
                            └── dashboard ────┘
                            └── analitica
```

`dashboard` y `analitica` **solo leen**. No escriben nada, así que no pueden
introducir inconsistencias.

`recordatorios` conoce a `obligaciones`, nunca al revés. Cuando una
obligación se paga y hay que cancelar sus avisos, se hace mediante una
**señal** `post_save` declarada en `recordatorios`, no llamando al servicio
desde el modelo `Obligacion`. Esto mantiene la dirección de las
dependencias.

---

## 4. Dónde vive cada regla de negocio

| Regla | Módulo | Naturaleza |
|---|---|---|
| Estado de una obligación | `obligaciones/services/estados.py` | Función pura + expresión SQL |
| Algoritmo de prioridades | `obligaciones/services/priorizacion.py` | Función pura |
| Normalización de proveedores | `obligaciones/services/proveedores.py` | Consulta + limpieza |
| Generación de recordatorios | `recordatorios/services/generacion.py` | Escribe, idempotente |
| Canales de entrega | `recordatorios/services/canales.py` | Interfaz + implementaciones |
| Insights | `analitica/services/insights.py` | Nueve funciones puras |

Todos estos módulos son **sustituibles sin tocar vistas ni plantillas**. Es
lo que hace posible §39: reemplazar el algoritmo de prioridades por un
modelo entrenado significa cambiar una función, no reescribir la aplicación.

---

## 5. Tres invariantes que sostienen el sistema

### 5.1 El acceso a datos tiene un único punto

```python
Obligacion.objects.visibles_para(usuario)
```

Todas las vistas heredan de `ObligacionQuerysetMixin`. No existe en el
código ni un `get_object_or_404(Obligacion, pk=pk)` sin filtrar.

Además, una prueba recorre automáticamente el árbol de URLs registradas y
comprueba que ninguna ruta privada responde a un usuario anónimo. Si alguien
añade una vista y olvida el mixin, la suite falla sin que nadie escriba un
test nuevo.

### 5.2 El estado se deriva, no se guarda

Ver [`modelo-datos.md`](modelo-datos.md), sección 4. Dos implementaciones
—Python y SQL— con una prueba que las compara caso por caso.

### 5.3 La idempotencia la impone la base de datos

`UNIQUE(obligacion, dias_antes, fecha_programada, canal)` sobre
`Recordatorio`, combinada con `get_or_create`.

No es una comprobación en Python, que tendría condición de carrera si el
proceso se ejecutara dos veces simultáneamente. Verificado en producción:

```
Primera ejecución:  19 creados, 19 enviados
Segunda ejecución:   0 creados,  0 enviados
```

Esta propiedad es la que permite disparar el proceso también al abrir el
dashboard (*catch-up*), resolviendo que la tarea programada no corra si el
equipo estaba apagado.

---

## 6. Extensibilidad

### Añadir un canal de notificación

```python
class CanalWhatsApp(Canal):
    codigo = CanalNotificacion.WHATSAPP

    def enviar(self, recordatorio):
        ...
```

Registrarlo en `_REGISTRO` y añadir el valor al enum. Ni el modelo
`Recordatorio` ni el generador cambian. Un canal que falla queda en estado
`ERROR` con su detalle **sin bloquear a los demás**, cosa que hay probada.

### Añadir una regla de insight

Escribir una función `(DatosUsuario) -> Insight | None` y sumarla a
`REGLAS`. Todas comparten contrato y hay una prueba que lo verifica.

### Exponer una API REST (§30)

La lógica de negocio no vive en las vistas, así que una vista de Django REST
Framework consumiría los mismos servicios y selectores sin duplicar nada.
No se implementó porque todavía no existe un consumidor real.

### Varios usuarios por empresa (§26)

Ya funciona a nivel de datos: `visibles_para` contempla la empresa y hay una
prueba con dos usuarios compartiendo obligaciones. Falta solo la interfaz
para invitarlos.

---

## 7. Procesos automáticos

Sin Celery ni Redis. Un management command idempotente:

```
Programador de tareas de Windows  →  diario 07:00
                                  →  manage.py generar_recordatorios
```

**Problema real:** si el equipo está apagado a esa hora, la tarea no corre.
En un portátil eso ocurre casi siempre.

**Solución:** el mismo servicio se invoca al cargar el dashboard, limitado a
una vez al día por sesión. Como es idempotente, ejecutarlo de más produce
exactamente el mismo resultado. Esto es lo que hace innecesario Celery en el
MVP.

---

## 8. Configuración y secretos

```
config/settings/
├── base.py         común
├── local.py        desarrollo, DEBUG=True
└── production.py   DEBUG=False, cabeceras endurecidas
```

Todo lo sensible vive en `.env`, que no se versiona: `SECRET_KEY`,
credenciales de base de datos, configuración de correo. Se lee con
`django-environ`.

El motor de base de datos se elige por variable de entorno (`DB_ENGINE`), lo
que permitió desarrollar antes de tener MySQL disponible y migrar después
sin tocar una línea de código.

`production.py` está gobernado por `HTTPS_ACTIVO`: con esa variable en
`True`, `manage.py check --deploy` no reporta ningún aviso.

---

## 9. Frontend

Sin npm, sin bundler, sin build. Bootstrap 5.3, Bootstrap Icons y Chart.js
descargados en `static/vendor/`, servidos por Django.

**Por qué locales y no por CDN:** en una sustentación sin internet estable,
un CDN caído deja la aplicación sin estilos delante del jurado. El costo son
unos 890 KB versionados.

El calendario se construye con el módulo `calendar` de la biblioteca
estándar y CSS Grid, en lugar de añadir una librería de 300 KB.

Los datos de los gráficos llegan al navegador con `json_script`, que escapa
el contenido. Nunca se interpola JSON dentro de una etiqueta `<script>`.

---

## 10. Dependencias

Producción, cuatro:

| Paquete | Para qué |
|---|---|
| `Django 5.2 LTS` | Framework |
| `mysqlclient` | Driver de MySQL |
| `django-environ` | Lectura de `.env` |
| `django-crispy-forms` + `crispy-bootstrap5` | Formularios con estilo |

Desarrollo: `coverage`.

Descartadas explícitamente: Celery, Redis, Docker, Django REST Framework,
FullCalendar, pytest y cualquier SDK de inteligencia artificial.
