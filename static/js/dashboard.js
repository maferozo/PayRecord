/* Gráficos del dashboard (§11): dinero comprometido por mes y % pagadas.

   Mismo patrón que static/js/estadisticas.js — se redibujan al cambiar de
   tema porque los colores salen de variables CSS que Chart.js no relee solo.
   Requiere que static/js/chart-plugins.js se cargue antes (registra el
   texto centrado de la dona). */

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

  const pesos = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });

  const datos = {
    comprometido: leer("datosComprometidoDashboard"),
    pagadas: leer("datosPagadasDashboard"),
  };

  let graficos = [];

  function dibujar() {
    graficos.forEach((grafico) => grafico.destroy());
    graficos = [];

    const texto = token("--pr-texto-suave", "#5A6683");
    const rejilla = token("--pr-borde", "#E0E5F2");

    // --- Dinero comprometido por mes: el mes en curso en un tono más
    // fuerte que los que el generador de recurrencia ya dejó listos para
    // más adelante. No es solo estética: distingue "esto ya toca" de
    // "esto es lo que viene".
    const lienzoComprometido = document.getElementById("graficoComprometidoDashboard");
    if (datos.comprometido && lienzoComprometido) {
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
            maxBarThickness: 56,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
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

    // --- Obligaciones pagadas: dona con el porcentaje al centro ---
    const lienzoPagadas = document.getElementById("graficoPagadasDashboard");
    if (datos.pagadas && lienzoPagadas && datos.pagadas.porcentaje !== null) {
      const colorTexto = token("--pr-texto", "#141A2E");

      graficos.push(new Chart(lienzoPagadas, {
        type: "doughnut",
        data: {
          labels: ["Pagadas", "Resto"],
          datasets: [{
            data: datos.pagadas.cantidades,
            backgroundColor: [token("--pr-pagado", "#15803D"), token("--pr-pendiente-bg", "#EAEEF6")],
            borderWidth: 0,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "72%",
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false },
            textoCentral: {
              texto: `${datos.pagadas.porcentaje}%`,
              subtexto: "pagadas",
              color: colorTexto,
              colorSubtexto: texto,
              tamano: 26,
            },
          },
        },
      }));
    }
  }

  document.addEventListener("DOMContentLoaded", dibujar);
  document.addEventListener("payrecord:tema", dibujar);
})();
