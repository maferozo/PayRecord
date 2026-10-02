/* Complemento para Chart.js: escribe un texto (normalmente un porcentaje)
   en el centro de una dona. Se registra una sola vez y lo usan tanto
   dashboard.js como estadisticas.js — deben cargar este archivo antes.

   Uso: options.plugins.textoCentral = { texto: "45%", color: "#141A2E" } */

(function () {
  "use strict";

  if (typeof Chart === "undefined") return;

  Chart.register({
    id: "textoCentral",
    afterDraw(chart) {
      const opciones = chart.config.options.plugins && chart.config.options.plugins.textoCentral;
      if (!opciones || !opciones.texto) return;

      const { ctx, chartArea } = chart;
      const { width, height, top, left } = chartArea;

      ctx.save();
      ctx.font = `700 ${opciones.tamano || 24}px ${getComputedStyle(document.body).fontFamily}`;
      ctx.fillStyle = opciones.color || "#141A2E";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(opciones.texto, left + width / 2, top + height / 2 - (opciones.subtexto ? 8 : 0));

      if (opciones.subtexto) {
        ctx.font = `500 12px ${getComputedStyle(document.body).fontFamily}`;
        ctx.fillStyle = opciones.colorSubtexto || opciones.color || "#141A2E";
        ctx.fillText(opciones.subtexto, left + width / 2, top + height / 2 + 14);
      }
      ctx.restore();
    },
  });
})();
