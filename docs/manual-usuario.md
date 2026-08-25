# PAYRECORD — Manual de usuario

PAYRECORD reúne en un solo lugar tus pagos, sus fechas y sus recordatorios,
para que sepas **qué debes pagar, cuándo y qué atender primero**.

---

## 1. Crear tu cuenta

Entra a la aplicación y pulsa **Crear cuenta**.

Tendrás que elegir cómo vas a usarla:

| | |
|---|---|
| **Personal** | Arriendo, servicios, tarjetas, suscripciones, impuestos… |
| **Empresa** | Proveedores, nómina, seguridad social, arriendo, software… |

Si eliges empresa, se te pedirán además el nombre y el NIT. La diferencia no
son dos aplicaciones distintas: cambian las categorías disponibles, aparecen
los campos de proveedor y referencia, y el dashboard añade el bloque de
proveedores.

> La contraseña debe tener al menos 8 caracteres y no puede ser demasiado
> común ni parecerse a tu correo.

Si olvidas la contraseña, usa **¿Olvidaste tu contraseña?** en la pantalla de
inicio de sesión. Recibirás un enlace válido durante 24 horas.

---

## 2. El dashboard

Es la primera pantalla al entrar y responde a cuatro preguntas de un vistazo.

**Dinero comprometido.** El total de lo que aún no has pagado.

**Las cuatro tarjetas de estado.** Vencidas, próximas, pendientes y pagadas.
Cada una es un enlace: al pulsarla vas a esa lista filtrada.

**Prioridades de hoy.** Aquí está lo que diferencia a PAYRECORD de una simple
lista. No están ordenadas por fecha, sino por lo que conviene atender
primero, y **cada una te dice por qué**:

```
🔴 Crédito de vivienda        $450.000
     · Vence mañana
     · Monto alto frente a tus obligaciones pendientes
     · La marcaste como prioridad alta
     · «Créditos» es una categoría crítica
```

El cálculo combina cuatro cosas: lo cerca que está el vencimiento (lo que
más pesa), cuánto es el monto **comparado con tus propias obligaciones**, la
prioridad que le pusiste y la importancia de la categoría.

**Próximas por fecha** y **comprometido por categoría** completan la vista.

---

## 3. Registrar una obligación

Pulsa **Registrar obligación**. Lo mínimo son cuatro datos: concepto, valor,
fecha de vencimiento y categoría.

Opcionalmente puedes añadir:

- **Prioridad**: cuánto te importa a ti. Influye en el orden, pero nunca por
  encima de la urgencia real.
- **Descripción**: cualquier detalle que quieras recordar.
- **Enlace de pago**: la URL donde pagas. PAYRECORD **no realiza pagos**;
  solo te lleva al enlace cuando lo necesites.
- **Proveedor y referencia** (cuentas de empresa).

**Puedes registrar obligaciones ya vencidas.** Si estás poniéndote al día,
regístralas con su fecha real y aparecerán como vencidas.

### Los recordatorios

En el mismo formulario eliges cuándo quieres que te avise:

```
[x] 7 días antes    [x] 3 días antes    [x] 1 día antes    [x] El día del vencimiento
```

Vienen marcados según tus preferencias, que puedes cambiar en tu perfil.

---

## 4. Mis obligaciones

El listado completo, ordenado con lo pendiente arriba. Cada fila muestra el
estado con su color:

| Color | Estado | Significado |
|---|---|---|
| ⚪ Gris | Pendiente | Falta tiempo |
| 🟡 Ámbar | Próxima a vencer | Dentro de tu umbral (7 días por defecto) |
| 🔴 Rojo | Vencida | Ya pasó la fecha y no está pagada |
| 🟢 Verde | Pagada | Resuelta |

**No tienes que actualizar el estado nunca.** Se calcula solo a partir de la
fecha y de si está pagada.

Puedes filtrar por texto, estado, categoría, prioridad y rango de fechas. El
total pendiente que ves arriba corresponde a lo filtrado.

Para marcar algo como pagado, pulsa **Pagada**. Si te equivocas, el botón
**Reabrir** lo deshace.

---

## 5. El calendario

Muestra el mes con tus vencimientos. Cada día con obligaciones indica el
total y un punto de color por categoría. Los días con algo vencido se marcan
en rojo; los que están todo pagado, en verde; hoy lleva borde azul.

Pulsa cualquier día para ver el detalle de esa fecha. Usa las flechas para
cambiar de mes y **Ir a hoy** para volver.

---

## 6. Notificaciones

La campana del menú muestra cuántos avisos tienes sin leer.

```
🔔 «Internet» vence mañana
   Tu obligación «Internet» por $120.000 vence el 27/08/2026.
```

Al pulsar una notificación se marca como leída y te lleva a la obligación.
También puedes marcarlas todas de una vez.

En **Programados** ves qué avisos tiene previstos el sistema y cuáles ya te
envió. Cuando marcas una obligación como pagada, sus avisos pendientes pasan
a *Cancelado* automáticamente: no vas a recibir recordatorios de algo que ya
resolviste.

---

## 7. Categorías

Vienen 13 categorías listas, distintas según tu tipo de cuenta. No se pueden
editar ni borrar, y son las mismas para todos.

Puedes crear las tuyas: nombre, color, icono y una **importancia de 0 a 5**
que influye en el orden de prioridades. Si más adelante intentas eliminar una
que ya tiene obligaciones, se desactivará en lugar de borrarse, para no
alterar tu historial.

---

## 8. Estadísticas

Totales de lo pagado, pendiente y vencido, con el porcentaje de obligaciones
que ya resolviste y **cuántas pagaste a tiempo**.

Tres gráficos: reparto por estado, valor por categoría y evolución de los
últimos seis meses separando pagado de pendiente.

---

## 9. Insights

Observaciones que el sistema detecta en tus datos:

> **Tienes 3 obligaciones que vencen durante los próximos 7 días.**
> Suman $1.470.000.

> **La mayoría de tus obligaciones vence entre los días 21 y 31.**
> Son 5 de 6, un 83% del total.

Cada tarjeta indica de qué dato sale su cifra, para que puedas comprobarla.

> **Nota:** esto no es inteligencia artificial. Son reglas aplicadas a tus
> obligaciones registradas. La página lo dice explícitamente.

---

## 10. Proveedores (cuentas de empresa)

Qué le debes a cada proveedor, con lo pendiente, lo vencido y el próximo
vencimiento. Al abrir uno ves todas sus facturas.

Cuando escribas un proveedor que ya usaste, la aplicación te lo sugiere y
respeta la forma en que lo escribiste la primera vez, para que no se te
dupliquen por una mayúscula.

---

## 11. Configuración

En **Configuración** (menú de tu nombre) puedes:

- Cambiar tu nombre y tu correo.
- Editar los datos de tu empresa, si tienes cuenta empresarial.
- Ajustar **cuántos días antes** consideras que algo está próximo a vencer.
  Por defecto son 7; si pones 15, verás en ámbar lo que vence dentro de dos
  semanas.
- Elegir los recordatorios que se proponen al crear una obligación.
- Cambiar tu contraseña.

El tipo de cuenta no se puede cambiar: implicaría que tus obligaciones
quedaran clasificadas en categorías que no corresponden.

---

## 12. Tu privacidad

Cada usuario ve **únicamente sus propios datos**. Ni siquiera escribiendo la
dirección a mano se puede acceder a la información de otra persona: el
sistema responde como si no existiera.

Las contraseñas se guardan cifradas y nadie —tampoco el administrador— puede
verlas. El administrador puede consultar la lista de usuarios y activarlos o
desactivarlos, pero **no puede leer ni modificar tus obligaciones**.

En cuentas de empresa, los usuarios de una misma empresa sí comparten sus
obligaciones entre ellos.

---

## 13. Preguntas frecuentes

**¿PAYRECORD paga por mí?**
No. Solo te avisa y te lleva al enlace de pago que tú registres.

**¿Tengo que marcar algo como vencido?**
No. El estado se calcula solo a partir de la fecha.

**¿Y si no abro la aplicación durante días?**
Al volver a entrar, PAYRECORD genera los avisos que quedaron pendientes. Si
alguno ya venció, el mensaje te lo dirá tal cual: «está vencida».

**¿Puedo registrar algo que ya venció?**
Sí. Ponle su fecha real y aparecerá como vencida.

**Eliminé una obligación por error.**
Deja de aparecer, pero el registro se conserva internamente para no alterar
tus estadísticas. Puedes volver a crearla.

**¿Recibiré correos?**
En esta versión los recordatorios son solo dentro de la aplicación. El canal
de correo está previsto para una versión posterior.
