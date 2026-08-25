# PAYRECORD — Informe de pruebas

**346 pruebas · 95.8% de cobertura · todas en verde contra MySQL 8.4**

Las pruebas se ejecutan con el runner de Django (`unittest`), sin
dependencias adicionales, y crean y destruyen su propia base de datos
(`test_payrecord`). No se prueban contra SQLite: se prueban contra el mismo
motor que usa la aplicación.

---

## 1. Cómo ejecutarlas

```powershell
cd c:\Kompras-V2\PayRecord
.venv\Scripts\activate

python manage.py test apps                    # toda la suite
python manage.py test apps.obligaciones       # una app
python manage.py test apps.core.tests.test_seguridad   # un módulo

# Con cobertura
coverage run manage.py test apps --noinput
coverage report
coverage html          # informe navegable en htmlcov/index.html
```

> El parámetro `--noinput` evita que el comando se detenga a preguntar si
> debe borrar una base de test que quedara de una ejecución interrumpida.

---

## 2. Distribución

| Módulo | Pruebas | Qué cubre |
|---|---:|---|
| `analitica/test_estadisticas.py` | 30 | Totales, agregados, evolución mensual, filtros de fecha |
| `analitica/test_insights.py` | 31 | Las nueve reglas, umbrales y contrato |
| `core/test_formato.py` | 10 | Moneda COP y textos de vencimiento |
| `core/test_seguridad.py` | 17 | Barrido de rutas, aislamiento, CSRF, inyección, XSS |
| `core/test_vistas.py` | 3 | Portada pública |
| `dashboard/test_calendario.py` | 31 | Cuadrícula, navegación, parámetros inválidos |
| `dashboard/test_dashboard.py` | 22 | Resumen, prioridades, proveedores |
| `obligaciones/test_categorias.py` | 21 | Catálogo, CRUD, ámbitos, aislamiento |
| `obligaciones/test_estados.py` | 10 | Los cuatro estados en Python y en SQL |
| `obligaciones/test_obligaciones.py` | 31 | CRUD, validaciones, aislamiento |
| `obligaciones/test_presentacion.py` | 17 | Filtros de plantilla, comandos, mixins |
| `obligaciones/test_priorizacion.py` | 18 | Algoritmo de prioridades |
| `obligaciones/test_proveedores.py` | 19 | Normalización, agregación, acceso |
| `recordatorios/test_generacion.py` | 31 | Generación, idempotencia, cancelación, canales |
| `recordatorios/test_vistas.py` | 20 | Bandeja, catch-up, formulario |
| `usuarios/test_autenticacion.py` | 16 | Registro, login, recuperación |
| `usuarios/test_modelos.py` | 6 | Usuario personalizado, hash, señal |
| `usuarios/test_perfil.py` | 13 | Perfil, empresa, preferencias, contraseña |

---

## 3. Cobertura

```
TOTAL      1713 sentencias      59 sin cubrir      95.8%
```

Se excluyen migraciones, los propios tests y los `__init__.py`. Lo que queda
sin cubrir son ramas defensivas: manejadores de excepciones de errores de
infraestructura y algunas comprobaciones del panel de administración.

---

## 4. Casos exigidos por la especificación (§36)

### Usuarios

| Caso | Prueba |
|---|---|
| Registro correcto | `RegistroTests::test_registro_correcto_crea_usuario_y_lo_autentica` |
| Correo duplicado | `RegistroTests::test_correo_duplicado_es_rechazado` |
| Login correcto | `LoginTests::test_login_correcto` |
| Contraseña incorrecta | `LoginTests::test_contrasena_incorrecta` |

Añadidos: duplicado ignorando mayúsculas, contraseña débil, cuenta
desactivada y registro de empresa sin nombre.

### Obligaciones

| Caso | Prueba |
|---|---|
| Creación correcta | `CrearObligacionTests::test_creacion_correcta` |
| Valor inválido | `test_monto_negativo_es_rechazado`, `test_monto_cero_es_rechazado` |
| Fecha inválida | `test_fecha_invalida_es_rechazada` |
| Edición | `EditarYEliminarTests::test_editar` |
| Eliminación | `test_eliminar_es_logico` |
| Marcar como pagada | `MarcarPagadaTests::test_marcar_pagada` |

### Estados

`test_estados.py` cubre los cuatro, incluidos los bordes:

- **Vence hoy** todavía no es «vencida»: aún se puede pagar.
- El umbral de «próxima a vencer» es configurable por usuario.
- **La anotación SQL y el cálculo en Python coinciden** en todos los casos.
  Si alguien modifica uno y olvida el otro, la suite falla.

### Seguridad

| Caso | Prueba |
|---|---|
| Usuario A accede a datos de B | `AislamientoTransversalTests::test_beto_recibe_404_en_todo_lo_de_ana` |
| Modificación por POST | `test_beto_no_puede_modificar_por_post` |
| Los totales no filtran importes ajenos | `test_los_agregados_no_filtran_importes_ajenos` |
| Una empresa no ve otra | `test_una_empresa_no_ve_los_datos_de_otra` |

Se responde **404 y no 403**: un 403 confirmaría que el recurso existe.

### Recordatorios

Los seis casos de §36 están cubiertos en `test_generacion.py`:

| Caso | Prueba |
|---|---|
| 7 días antes | `test_el_ejemplo_de_la_especificacion` |
| 3, 1 y día del vencimiento | `test_los_cuatro_plazos_de_la_especificacion` |
| Obligación vencida | `test_obligacion_ya_vencida_genera_su_aviso` |
| Recordatorio duplicado | `IdempotenciaTests` (4 pruebas) |

---

## 5. Pruebas que merecen mención

### Barrido automático de rutas

`BarridoDeRutasTests::test_ninguna_ruta_privada_responde_a_un_anonimo`

Recorre el árbol de URLs registradas y comprueba que toda ruta que no esté
en la lista de públicas redirige al login. **Si alguien añade una vista
privada y olvida el mixin de autenticación, esta prueba lo detecta sin que
nadie escriba un test nuevo.**

### La idempotencia se verifica contra la base de datos

`IdempotenciaTests::test_la_base_de_datos_impide_el_duplicado`

No comprueba que el código evite duplicar: intenta insertar el duplicado a
mano y verifica que **MySQL lo rechaza** con `IntegrityError`. La garantía
está en la restricción, no en el código.

### Dos implementaciones comparadas entre sí

`EstadoEnSqlTests::test_sql_y_python_coinciden`

El estado se calcula por dos caminos. La prueba los ejecuta sobre el mismo
conjunto y los compara caso por caso.

### El ejemplo de la especificación como caso de prueba

`EjemploDeLaEspecificacionTests`

Reproduce literalmente el ejemplo de §11 —Crédito 🔴, Internet 🟡,
Netflix 🟢— y verifica que el algoritmo produce esas tres bandas.

### Inyección y XSS

`InyeccionTests` lanza cargas como `'; DROP TABLE ...; --` contra el
buscador y comprueba que la tabla sigue intacta, y verifica que un concepto
con `<script>` se escapa al renderizar.

---

## 6. Revisión de seguridad del despliegue

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
python manage.py check --deploy
```

Con `HTTPS_ACTIVO=True` en el `.env`: **0 avisos**.

Sin HTTPS quedan 4, todos relativos a SSL (`SECURE_SSL_REDIRECT`,
`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`).
Vienen desactivados a propósito: activarlos sin certificado dejaría la
aplicación inaccesible.

---

## 7. Limitaciones conocidas

- **No hay pruebas de interfaz automatizadas.** El JavaScript (mostrar los
  campos de empresa, los gráficos) se ha verificado a mano. Un `Selenium` o
  `Playwright` habría añadido una dependencia pesada para un beneficio
  limitado en este alcance.
- **El canal de correo no está probado** porque no está implementado. Lo que
  sí se prueba es que un canal no disponible deja el recordatorio en estado
  `ERROR` sin bloquear a los demás.
- **Las pruebas de concurrencia son indirectas.** La condición de carrera del
  generador se cubre verificando la restricción de la base de datos, no
  lanzando procesos en paralelo.
