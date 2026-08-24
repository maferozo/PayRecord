/* Gráficos del módulo de estadísticas (§18).
   Los datos llegan desde el servidor con json_script, nunca interpolados
   dentro del HTML. */

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

  // Formato de pesos colombianos para ejes y tooltips.
  const pesos = new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  });

  const comun = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { usePointStyle: true, boxWidth: 8 } },
    },
  };

  // --- Obligaciones por estado ---
  const estado = leer("datosEstado");
  const lienzoEstado = document.getElementById("graficoEstado");

  if (estado && lienzoEstado) {
    new Chart(lienzoEstado, {
      type: "doughnut",
      data: {
        labels: estado.etiquetas,
        datasets: [{
          data: estado.cantidades,
          backgroundColor: estado.colores,
          borderWidth: 0,
        }],
      },
      options: {
        ...comun,
        cutout: "62%",
        plugins: {
          ...comun.plugins,
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
        },
      },
    });
  }

  // --- Valor por categoría ---
  const categoria = leer("datosCategoria");
  const lienzoCategoria = document.getElementById("graficoCategoria");

  if (categoria && lienzoCategoria) {
    new Chart(lienzoCategoria, {
      type: "bar",
      data: {
        labels: categoria.etiquetas,
        datasets: [{
          label: "Valor",
          data: categoria.valores,
          backgroundColor: categoria.colores,
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
              label: (ctx) => pesos.format(ctx.parsed.x),
            },
          },
        },
        scales: {
          x: {
            ticks: { callback: (valor) => pesos.format(valor) },
            grid: { color: "#EEF1F5" },
          },
          y: { grid: { display: false } },
        },
      },
    });
  }

  // --- Evolución mensual ---
  const evolucion = leer("datosEvolucion");
  const lienzoEvolucion = document.getElementById("graficoEvolucion");

  if (evolucion && lienzoEvolucion) {
    new Chart(lienzoEvolucion, {
      type: "bar",
      data: {
        labels: evolucion.etiquetas,
        datasets: [
          {
            label: "Pagado",
            data: evolucion.pagado,
            backgroundColor: "#16A34A",
            borderRadius: 6,
          },
          {
            label: "Sin pagar",
            data: evolucion.sin_pagar,
            backgroundColor: "#B45309",
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
          x: { stacked: true, grid: { display: false } },
          y: {
            stacked: true,
            ticks: { callback: (valor) => pesos.format(valor) },
            grid: { color: "#EEF1F5" },
          },
        },
      },
    });
  }
})();
