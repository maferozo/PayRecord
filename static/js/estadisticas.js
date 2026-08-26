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
    evolucion: leer("datosEvolucion"),
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

    // --- Obligaciones por estado ---
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
          cutout: "64%",
          plugins: {
            legend: {
              position: "bottom",
              labels: { usePointStyle: true, boxWidth: 8, color: texto },
            },
          },
        },
      }));
    }

    // --- Valor por categoría ---
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
            tooltip: { callbacks: { label: (ctx) => pesos.format(ctx.parsed.x) } },
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

    // --- Evolución mensual ---
    const lienzoEvolucion = document.getElementById("graficoEvolucion");
    if (datos.evolucion && lienzoEvolucion) {
      graficos.push(new Chart(lienzoEvolucion, {
        type: "bar",
        data: {
          labels: datos.evolucion.etiquetas,
          datasets: [
            {
              label: "Pagado",
              data: datos.evolucion.pagado,
              backgroundColor: token("--pr-pagado", "#15803D"),
              borderRadius: 6,
            },
            {
              label: "Sin pagar",
              data: datos.evolucion.sin_pagar,
              backgroundColor: token("--pr-proximo", "#B45309"),
              borderRadius: 6,
            },
          ],
        },
        options: {
          ...comun,
          plugins: {
            ...comun.plugins,
            tooltip: {
              callbacks: {
                label: (ctx) => `${ctx.dataset.label}: ${pesos.format(ctx.parsed.y)}`,
              },
            },
          },
          scales: {
            x: { stacked: true, ticks: { color: texto }, grid: { display: false } },
            y: {
              stacked: true,
              ticks: { callback: (valor) => pesos.format(valor), color: texto },
              grid: { color: rejilla },
            },
          },
        },
      }));
    }
  }

  document.addEventListener("DOMContentLoaded", dibujar);
  document.addEventListener("payrecord:tema", dibujar);
})();
