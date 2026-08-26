/* Sidebar plegable en pantallas pequeñas.

   En escritorio el menú lateral está siempre visible y este código no
   hace nada. Por debajo de 992 px se abre sobre el contenido con un velo
   detrás. */

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const sidebar = document.getElementById("sidebar");
    const velo = document.getElementById("velo");
    const boton = document.getElementById("botonMenu");

    if (!sidebar || !velo || !boton) return;

    function abrir() {
      sidebar.classList.add("abierto");
      velo.classList.add("visible");
      boton.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    }

    function cerrar() {
      sidebar.classList.remove("abierto");
      velo.classList.remove("visible");
      boton.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }

    boton.addEventListener("click", function () {
      sidebar.classList.contains("abierto") ? cerrar() : abrir();
    });

    velo.addEventListener("click", cerrar);

    // Escape cierra el menú, como cualquier capa superpuesta.
    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && sidebar.classList.contains("abierto")) {
        cerrar();
        boton.focus();
      }
    });

    // Al navegar a otra sección no debe quedarse abierto.
    sidebar.querySelectorAll("a").forEach(function (enlace) {
      enlace.addEventListener("click", cerrar);
    });

    // Si se agranda la ventana, el estado móvil deja de tener sentido.
    window.matchMedia("(min-width: 992px)").addEventListener("change", function (evento) {
      if (evento.matches) cerrar();
    });
  });
})();
