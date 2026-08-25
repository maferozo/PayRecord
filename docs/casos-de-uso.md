# PAYRECORD — Casos de uso

Cada caso indica la prueba automatizada que lo verifica, para que la
documentación no se separe del comportamiento real.

---

## Actores

| Actor | Descripción |
|---|---|
| **Usuario personal** | Administra sus obligaciones personales |
| **Usuario empresa** | Administra las obligaciones de una pequeña empresa |
| **Administrador** | Consulta usuarios, los activa o desactiva, mantiene el catálogo |
| **Sistema** | Proceso automático que genera y entrega recordatorios |

---

## CU-01 · Registrarse

**Actor:** visitante · **Precondición:** ninguna

1. Accede a `/cuenta/registro/`.
2. Indica nombre, correo, contraseña y tipo de cuenta.
3. Si elige **empresa**, el formulario despliega nombre y NIT.
4. El sistema valida: correo no registrado, contraseña robusta, empresa con
   nombre si aplica.
5. Crea la cuenta, su configuración por defecto y, si aplica, la empresa.
6. Inicia sesión y va al dashboard.

**Flujos alternativos**

- *Correo ya registrado* → error en el campo, no se crea nada.
- *Contraseña débil* → error de los validadores de Django.
- *Empresa sin nombre* → error; el guardado es atómico, no queda empresa
  huérfana.

**Pruebas:** `usuarios/tests/test_autenticacion.py::RegistroTests`

---

## CU-02 · Iniciar y cerrar sesión

**Actor:** usuario registrado

1. Accede a `/cuenta/entrar/` e indica correo y contraseña.
2. El sistema valida y abre sesión.
3. Cierra sesión desde el menú (por POST, nunca por enlace).

**Alternativos:** credenciales incorrectas o cuenta desactivada por el
administrador → mensaje genérico, sin revelar cuál de las dos falló.

**Pruebas:** `test_autenticacion.py::LoginTests`

---

## CU-03 · Recuperar la contraseña

1. Solicita el enlace indicando su correo.
2. El sistema **responde igual exista o no la cuenta**, para no revelar qué
   correos están registrados.
3. Si existe, envía un enlace válido 24 horas.
4. El usuario define la contraseña nueva.

**Pruebas:** `test_autenticacion.py::RecuperacionContrasenaTests`

---

## CU-04 · Registrar una obligación

**Actor:** usuario autenticado

1. Accede a `/obligaciones/nueva/`.
2. Indica concepto, valor, fecha de vencimiento, categoría y prioridad.
3. Opcionalmente: descripción, enlace de pago y, en cuentas de empresa,
   proveedor y referencia.
4. Marca los recordatorios que desea (7, 3, 1 días antes, el mismo día).
5. El sistema valida y guarda, creando las reglas de recordatorio.

**Reglas de negocio**

- El selector de categorías solo ofrece las visibles para ese usuario: las
  predeterminadas de su ámbito y las suyas propias.
- El propietario nunca llega desde el formulario, lo fija la vista.
- La empresa se copia del usuario.
- Se admiten fechas pasadas: registrar una deuda vencida es legítimo.
- El proveedor se normaliza reutilizando la grafía ya usada.

**Alternativos:** valor cero o negativo, fecha inválida, enlace mal formado,
categoría de otro ámbito o de otro usuario → todos rechazados.

**Pruebas:** `obligaciones/tests/test_obligaciones.py::CrearObligacionTests`

---

## CU-05 · Consultar y filtrar obligaciones

1. Accede a `/obligaciones/`.
2. Ve sus obligaciones con estado, valor y vencimiento.
3. Filtra por texto, estado, categoría, prioridad y rango de fechas.
4. El total pendiente refleja el conjunto filtrado, no solo la página.

**Alternativos:** rango invertido → aviso en el campo. Fecha mal escrita →
se ignora ese filtro, la página no falla.

**Pruebas:** `test_obligaciones.py::FiltrosListadoTests`,
`analitica/tests/test_estadisticas.py::FiltroFechasHistorialTests`

---

## CU-06 · Editar y eliminar

1. Abre el detalle y edita, o elimina con confirmación.
2. Eliminar marca `eliminada_en`: la obligación desaparece de las vistas
   pero el registro se conserva para no alterar el historial ni las
   estadísticas.
3. Si cambia la fecha de vencimiento, los recordatorios pendientes que
   apuntaban a la fecha anterior se cancelan y el generador crea los nuevos.

**Pruebas:** `test_obligaciones.py::EditarYEliminarTests`,
`recordatorios/tests/test_generacion.py::CancelacionTests`

---

## CU-07 · Marcar como pagada

1. Pulsa «Pagada» en el listado o en el detalle (**solo por POST**).
2. El sistema registra la fecha de pago; el estado pasa a `PAGADA`.
3. Los recordatorios pendientes se cancelan automáticamente.
4. La acción es reversible con «Volver a pendiente».

**Alternativo:** un GET a esa URL devuelve 405. Cambiar datos con GET
permitiría provocarlo desde un simple enlace.

**Pruebas:** `test_obligaciones.py::MarcarPagadaTests`

---

## CU-08 · Consultar el dashboard

1. Al iniciar sesión llega a `/dashboard/`.
2. El sistema **recupera los recordatorios atrasados** (una vez al día).
3. Ve dinero comprometido, resumen por estado, prioridades del día con el
   motivo de cada una, próximas por fecha y reparto por categoría.
4. En cuentas de empresa, además los principales proveedores.

**Pruebas:** `dashboard/tests/test_dashboard.py`

---

## CU-09 · Consultar el calendario

1. Accede a `/dashboard/calendario/`.
2. Ve el mes con los días marcados: total y un punto por categoría.
3. Navega entre meses; los días con algo vencido se marcan en rojo y los que
   están todo pagado en verde.
4. Al pulsar una fecha se abre el detalle de ese día.

**Alternativo:** parámetros inválidos en la URL → cae al mes actual.

**Pruebas:** `dashboard/tests/test_calendario.py`

---

## CU-10 · Recibir recordatorios

**Actor:** sistema · **Disparo:** tarea diaria o apertura del dashboard

1. Recorre las obligaciones sin pagar con reglas activas.
2. Calcula `fecha_vencimiento − dias_antes`.
3. Si esa fecha ya llegó y no es más antigua que 30 días, crea el
   recordatorio. **La restricción única impide duplicados.**
4. Entrega los pendientes por su canal, creando la notificación.
5. El texto describe la situación real: un aviso recuperado tarde dice
   «está vencida», no «vence mañana».

**Alternativos**

- *Obligación pagada entre generación y envío* → el aviso se cancela.
- *Canal no implementado* → estado `ERROR` con detalle, sin bloquear a los
  demás.

**Pruebas:** `recordatorios/tests/test_generacion.py`

---

## CU-11 · Consultar notificaciones

1. La campana del menú muestra el número sin leer.
2. En `/notificaciones/` ve la bandeja y puede filtrar las no leídas.
3. Al abrir una, se marca como leída **registrando el momento** y lleva a la
   obligación.
4. Puede marcar todas como leídas.

La fecha de lectura es el dato que necesitará §20 para saber qué
recordatorios le sirven realmente al usuario.

**Pruebas:** `recordatorios/tests/test_vistas.py::BandejaTests`

---

## CU-12 · Gestionar categorías

1. En `/categorias/` ve las del sistema y las suyas.
2. Puede crear, editar y eliminar **solo las propias**.
3. Al crear no se pregunta el ámbito: se deduce del tipo de cuenta.
4. Si una categoría tiene obligaciones, eliminar la **desactiva** en lugar
   de borrarla.

**Alternativos:** nombre repetido o que choca con una del sistema →
rechazado. Intentar editar una predeterminada o la de otro usuario → 404.

**Pruebas:** `obligaciones/tests/test_categorias.py`

---

## CU-13 · Consultar estadísticas

1. En `/estadisticas/` ve totales, porcentaje pagado y cumplimiento.
2. Tres gráficos: estados, valor por categoría y evolución de seis meses.
3. Sin datos suficientes, un mensaje lo explica en vez de mostrar gráficos
   vacíos.

**Pruebas:** `analitica/tests/test_estadisticas.py`

---

## CU-14 · Consultar Insights

1. En `/estadisticas/insights/` ve las observaciones detectadas.
2. Cada tarjeta indica **de qué dato sale su cifra**.
3. La página declara explícitamente que no intervienen modelos de IA.

Las reglas que no tienen nada relevante que decir no producen tarjeta: es
preferible mostrar tres observaciones útiles que diez de relleno.

**Pruebas:** `analitica/tests/test_insights.py`

---

## CU-15 · Gestionar proveedores

**Actor:** usuario empresa

1. En `/proveedores/` ve cada proveedor con pendiente, vencido y próximo
   vencimiento.
2. Al abrir uno, ve sus obligaciones.

**Alternativo:** una cuenta personal es devuelta al dashboard con una
explicación, no con un 403 seco: la sección no le está prohibida, es que no
aplica a su escenario.

**Pruebas:** `obligaciones/tests/test_proveedores.py`

---

## CU-16 · Configurar el perfil

1. En `/cuenta/perfil/` edita nombre y correo, datos de empresa si aplica, y
   preferencias.
2. Puede ajustar cuántos días antes considera una obligación «próxima a
   vencer»: ese umbral afecta al cálculo de estados de toda su cuenta.
3. Puede cambiar su contraseña indicando la actual.

**El tipo de cuenta no es editable** por el usuario. Cambiarlo dejaría
obligaciones clasificadas en categorías de otro ámbito (riesgo R11); solo el
administrador puede hacerlo.

**Pruebas:** `usuarios/tests/test_perfil.py`

---

## CU-17 · Administrar el sistema

**Actor:** administrador (`is_staff`)

1. Entra en `/admin/`.
2. Consulta usuarios y los activa o desactiva en lote.
3. Mantiene el catálogo de categorías predeterminadas.
4. Consulta recordatorios para diagnosticar el proceso automático.

**Restricción:** las obligaciones son de **solo lectura** en el panel. §27
pide que el administrador no acceda innecesariamente a información privada:
puede verificar la integridad de los datos, pero no editarlos ni borrarlos.

**Pruebas:** `core/tests/test_seguridad.py::BarridoDeRutasTests`

---

## CU-18 · Aislamiento entre usuarios

**Actor:** cualquier usuario · **Resultado esperado: siempre rechazado**

1. Un usuario intenta acceder a una obligación, categoría o notificación de
   otro, por URL directa o por POST.
2. El sistema responde **404** — no 403, que confirmaría que el recurso
   existe.
3. Los agregados (totales, prioridades, estadísticas) tampoco filtran
   importes ajenos.
4. Dos usuarios de la **misma empresa** sí comparten sus obligaciones.

**Pruebas:** `core/tests/test_seguridad.py::AislamientoTransversalTests`
y las clases de aislamiento de cada app.
