/* Cambio entre tema claro y oscuro.

   El tema se aplica en <html data-bs-theme>. La elección se guarda en
   localStorage; si el usuario nunca ha elegido, se sigue la preferencia
   del sistema operativo.

   El script que evita el parpadeo inicial está incrustado en <head>
   (ver templates/base.html): tiene que ejecutarse antes de pintar. */

(function () {
  "use strict";

  const CLAVE = "payrecord-tema";
  const raiz = document.documentElement;

  function preferenciaDelSistema() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function temaGuardado() {
    try {
      return localStorage.getItem(CLAVE);
    } catch (error) {
      return null;   // modo privado o almacenamiento bloqueado
    }
  }

  function aplicar(tema) {
    raiz.setAttribute("data-bs-theme", tema);

    document.querySelectorAll("[data-accion='cambiar-tema']").forEach((boton) => {
      const esOscuro = tema === "dark";
      const icono = boton.querySelector("i");

      if (icono) {
        icono.className = esOscuro ? "bi bi-sun" : "bi bi-moon-stars";
      }
      boton.setAttribute(
        "aria-label",
        esOscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro"
      );
      boton.setAttribute("title", boton.getAttribute("aria-label"));
    });

    // Los gráficos ya dibujados necesitan repintarse con los colores nuevos.
    document.dispatchEvent(new CustomEvent("payrecord:tema", { detail: { tema } }));
  }

  function alternar() {
    const nuevo = raiz.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(CLAVE, nuevo);
    } catch (error) {
      /* si no se puede guardar, el cambio vale solo para esta página */
    }
    aplicar(nuevo);
  }

  document.addEventListener("DOMContentLoaded", function () {
    aplicar(raiz.getAttribute("data-bs-theme") || temaGuardado() || preferenciaDelSistema());

    document.querySelectorAll("[data-accion='cambiar-tema']").forEach((boton) => {
      boton.addEventListener("click", alternar);
    });
  });

  // Si el usuario no ha elegido, se sigue al sistema cuando este cambie.
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (evento) => {
    if (!temaGuardado()) {
      aplicar(evento.matches ? "dark" : "light");
    }
  });
})();
