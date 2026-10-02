/* PayRecord AI: el panel de conversación (§ asistente IA).

   Todo lo que se muestra viene de /estadisticas/asistente/, que a su vez
   solo devuelve lo que ya calculó apps/analitica/services/asistente_ia.py
   a partir de datos reales. Este archivo no calcula nada, solo conversa. */

(function () {
  "use strict";

  const panel = document.querySelector("[data-pr-ia]");
  if (!panel) return;

  const URL_ASISTENTE = "/estadisticas/asistente/";
  const MENSAJE_ANALIZANDO = "🤖 PayRecord AI está analizando tus datos...";
  const MENSAJE_RESUMEN = "✨ Analizando tus obligaciones...";
  const MENSAJE_ERROR_RED = "No pude obtener una respuesta en este momento. Intenta nuevamente en unos segundos.";

  const conversacion = panel.querySelector("[data-pr-ia-conversacion]");
  const formulario = panel.querySelector("[data-pr-ia-formulario]");
  const input = panel.querySelector("[data-pr-ia-input]");
  const botonEnviar = panel.querySelector("[data-pr-ia-enviar]");
  const botonResumen = panel.querySelector("[data-pr-ia-resumen]");
  const sugerencias = panel.querySelectorAll("[data-pr-ia-sugerencia]");
  const csrfInput = panel.querySelector('input[name="csrfmiddlewaretoken"]');

  // --- Botón flotante (Dashboard y Estadísticas) ---
  const botonAbrir = document.querySelector("[data-pr-ia-abrir]");
  const botonCerrar = panel.querySelector("[data-pr-ia-cerrar]");
  if (botonAbrir) {
    botonAbrir.addEventListener("click", () => {
      panel.hidden = false;
      botonAbrir.hidden = true;
      input.focus();
    });
  }
  if (botonCerrar) {
    botonCerrar.addEventListener("click", () => {
      panel.hidden = true;
      if (botonAbrir) botonAbrir.hidden = false;
    });
  }

  function fila(esUsuario) {
    const contenedor = document.createElement("div");
    contenedor.className = "pr-ia-fila " + (esUsuario ? "pr-ia-fila-usuario" : "pr-ia-fila-ia");

    if (!esUsuario) {
      const avatar = document.createElement("span");
      avatar.className = "pr-ia-avatar-mini";
      avatar.innerHTML = '<i class="bi bi-robot"></i>';
      contenedor.appendChild(avatar);
    }
    return contenedor;
  }

  // Una línea que es solo un monto ("$3.067.000") se resalta como cifra
  // destacada, para que una respuesta con varios datos se lea como una
  // lista de hechos, no como un párrafo. El texto en sí no cambia.
  const ES_SOLO_CIFRA = /^\$[\d.,]+$/;

  function agregarBurbujaTexto(texto, esUsuario) {
    const contenedor = fila(esUsuario);
    const burbuja = document.createElement("div");
    burbuja.className = "pr-ia-burbuja " + (esUsuario ? "pr-ia-burbuja-usuario" : "pr-ia-burbuja-ia");

    texto.split("\n").forEach((linea) => {
      const contenido = linea.trim();
      if (!contenido) return;
      const parrafo = document.createElement("p");
      parrafo.className = "pr-ia-linea" + (ES_SOLO_CIFRA.test(contenido) ? " pr-ia-linea-cifra" : "");
      parrafo.textContent = contenido;
      burbuja.appendChild(parrafo);
    });

    contenedor.appendChild(burbuja);
    conversacion.appendChild(contenedor);
    conversacion.scrollTop = conversacion.scrollHeight;
    return contenedor;
  }

  function mostrarCargando(mensaje) {
    const contenedor = fila(false);
    const burbuja = document.createElement("div");
    burbuja.className = "pr-ia-burbuja pr-ia-burbuja-ia";
    burbuja.setAttribute("data-pr-ia-cargando", "");

    const texto = document.createElement("p");
    texto.className = "pr-ia-cargando-texto mb-1";
    texto.textContent = mensaje;

    const puntos = document.createElement("div");
    puntos.className = "pr-ia-cargando";
    puntos.innerHTML = "<span></span><span></span><span></span>";

    burbuja.appendChild(texto);
    burbuja.appendChild(puntos);
    contenedor.appendChild(burbuja);
    conversacion.appendChild(contenedor);
    conversacion.scrollTop = conversacion.scrollHeight;
    return contenedor;
  }

  function fijarCargando(activo) {
    input.disabled = activo;
    botonEnviar.disabled = activo;
    botonResumen.disabled = activo;
    sugerencias.forEach((boton) => { boton.disabled = activo; });
  }

  async function enviar(pregunta, esResumen) {
    if (!esResumen) agregarBurbujaTexto(pregunta, true);
    fijarCargando(true);
    const filaCargando = mostrarCargando(esResumen ? MENSAJE_RESUMEN : MENSAJE_ANALIZANDO);

    const cuerpo = new URLSearchParams();
    cuerpo.set("csrfmiddlewaretoken", csrfInput.value);
    if (esResumen) {
      cuerpo.set("resumen", "1");
    } else {
      cuerpo.set("pregunta", pregunta);
    }

    try {
      const respuesta = await fetch(URL_ASISTENTE, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: cuerpo,
      });
      const datos = await respuesta.json();

      filaCargando.remove();

      if (!respuesta.ok) {
        agregarBurbujaTexto(datos.error || MENSAJE_ERROR_RED, false);
        return;
      }
      agregarBurbujaTexto(datos.respuesta, false);
    } catch (error) {
      filaCargando.remove();
      agregarBurbujaTexto(MENSAJE_ERROR_RED, false);
    } finally {
      fijarCargando(false);
      input.focus();
    }
  }

  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const pregunta = input.value.trim();
    if (!pregunta) return;
    input.value = "";
    enviar(pregunta, false);
  });

  sugerencias.forEach((boton) => {
    boton.addEventListener("click", () => {
      const pregunta = boton.dataset.pregunta || boton.textContent.trim();
      enviar(pregunta, false);
    });
  });

  botonResumen.addEventListener("click", () => {
    agregarBurbujaTexto("✨ Generar resumen financiero", true);
    enviar(null, true);
  });
})();
