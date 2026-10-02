/* Gráficos del módulo de estadísticas (§18).

   Los datos llegan desde el servidor con json_script, nunca interpolados
   dentro del HTML.

   Los gráficos se redibujan cuando cambia el tema: los ejes y las leyendas
   heredan su color de las variables CSS, y Chart.js no las relee solo. */

(function () {
  "use strict";

  function leer(id) {
    const nodo = document.getElementById(id);
    if (!nodo) return null;
    try {
      return JSON.parse(nodo.textContent);
    } catch (error) {
      return null;
    }
  }

  function token(nombre, respaldo) {
    const valor = getComputedStyle(document.documentElement)
      .getPropertyValue(nombre)
      .trim();
    return valor || respaldo;
  }

  // Formato de pesos colombianos para ejes y tooltips.
  const pesos = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });

  const datos = {
    estado: leer("datosEstado"),
    categoria: leer("datosCategoria"),
    comprometido: leer("datosComprometido"),
  };

  let graficos = [];

  function dibujar() {
    // Chart.js no permite dos instancias sobre el mismo lienzo.
    graficos.forEach((grafico) => grafico.destroy());
    graficos = [];

    const texto = token("--pr-texto-suave", "#5A6683");
    const rejilla = token("--pr-borde", "#E0E5F2");

    const comun = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8, color: texto } },
      },
    };

    // --- Gráfica 3: Estado de mis obligaciones ---
    const lienzoEstado = document.getElementById("graficoEstado");
    if (datos.estado && lienzoEstado) {
      // El color sale del tema activo: los tonos oscuros del tema claro
      // no se distinguirían sobre el fondo oscuro.
      const tokensEstado = {
        PENDIENTE: "--pr-pendiente",
        PROXIMA_VENCER: "--pr-proximo",
        VENCIDA: "--pr-vencido",
        PAGADA: "--pr-pagado",
      };
      const colores = (datos.estado.claves || []).map(
        (clave, i) => token(tokensEstado[clave], datos.estado.colores[i])
      );

      const totalObligaciones = datos.estado.cantidades.reduce((a, b) => a + b, 0);

      graficos.push(new Chart(lienzoEstado, {
        type: "doughnut",
        data: {
          labels: datos.estado.etiquetas,
          datasets: [{
            data: datos.estado.cantidades,
            backgroundColor: colores.length ? colores : datos.estado.colores,
            borderWidth: 0,
          }],
        },
        options: {
          ...comun,
          cutout: "68%",
          plugins: {
            legend: {
              position: "bottom",
              labels: { usePointStyle: true, boxWidth: 8, color: texto },
            },
            textoCentral: {
              texto: String(totalObligaciones),
              subtexto: totalObligaciones === 1 ? "obligación" : "obligaciones",
              color: token("--pr-texto", "#141A2E"),
              colorSubtexto: texto,
              tamano: 24,
            },
          },
        },
      }));
    }

    // --- Gráfica 1: Dinero comprometido por mes ---
    const lienzoComprometido = document.getElementById("graficoComprometido");
    if (datos.comprometido && lienzoComprometido) {
      // El mes en curso en un tono más fuerte que los que ya generó por
      // adelantado el motor de obligaciones mensuales.
      const fuerte = token("--pr-acento", "#5B5BD6");
      const suave = token("--pr-acento-claro", "#8B8BF0");
      const colores = (datos.comprometido.mes_actual || []).map(
        (esActual) => (esActual ? fuerte : suave)
      );

      graficos.push(new Chart(lienzoComprometido, {
        type: "bar",
        data: {
          labels: datos.comprometido.etiquetas,
          datasets: [{
            label: "Comprometido",
            data: datos.comprometido.valores,
            backgroundColor: colores.length ? colores : fuerte,
            borderRadius: 6,
          }],
        },
        options: {
          ...comun,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => pesos.format(ctx.parsed.y) } },
          },
          scales: {
            x: { ticks: { color: texto }, grid: { display: false } },
            y: {
              ticks: { callback: (valor) => pesos.format(valor), color: texto },
              grid: { color: rejilla },
            },
          },
        },
      }));
    }

    // --- Gráfica 2: ¿En qué categorías tengo más dinero comprometido? ---
    const lienzoCategoria = document.getElementById("graficoCategoria");
    if (datos.categoria && lienzoCategoria) {
      graficos.push(new Chart(lienzoCategoria, {
        type: "bar",
        data: {
          labels: datos.categoria.etiquetas,
          datasets: [{
            label: "Valor",
            data: datos.categoria.valores,
            backgroundColor: datos.categoria.colores,
            borderRadius: 6,
          }],
        },
        options: {
          ...comun,
          indexAxis: "y",
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                // La cantidad va en el tooltip: evita una torta aparte solo
                // para mostrar ese mismo dato de otra forma.
                label: (ctx) => {
                  const cantidad = datos.categoria.cantidades[ctx.dataIndex];
                  const obligaciones = cantidad === 1 ? "obligación" : "obligaciones";
                  return `${pesos.format(ctx.parsed.x)} · ${cantidad} ${obligaciones}`;
                },
              },
            },
          },
          scales: {
            x: {
              ticks: { callback: (valor) => pesos.format(valor), color: texto },
              grid: { color: rejilla },
            },
            y: { ticks: { color: texto }, grid: { display: false } },
          },
        },
      }));
    }
  }

  document.addEventListener("DOMContentLoaded", dibujar);
  document.addEventListener("payrecord:tema", dibujar);
})();
