document.addEventListener("DOMContentLoaded", function () {

    /* ========================================
       ELEMENTOS PRINCIPALES
    ======================================== */

    const menuToggle = document.getElementById("menuToggle");
    const panelContainer = document.getElementById("panelContainer");
    const sidebar = document.getElementById("sidebar");

    const userButton = document.getElementById("userButton");
    const userDropdown = document.getElementById("userDropdown");


    /* ========================================
       CONFIGURACIÓN
    ======================================== */

    const MOBILE_BREAKPOINT = 850;


    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }


    /* ========================================
       ACTUALIZAR BOTÓN HAMBURGUESA
       
       Cerrado = ☰
       Abierto = ✕
    ======================================== */

    function actualizarBotonMenu() {

        if (!menuToggle || !panelContainer) {
            return;
        }

        const menuAbierto =
            panelContainer.classList.contains("sidebar-mobile-open");

        if (menuAbierto && isMobile()) {

            menuToggle.textContent = "✕";
            menuToggle.setAttribute(
                "aria-label",
                "Cerrar menú"
            );

        } else {

            menuToggle.textContent = "☰";
            menuToggle.setAttribute(
                "aria-label",
                "Abrir menú"
            );

        }

    }


    /* ========================================
       ABRIR / CERRAR MENÚ LATERAL
    ======================================== */

    if (menuToggle && panelContainer) {

        menuToggle.addEventListener("click", function (event) {

            /*
             * Evita que el click llegue al document
             * y cierre inmediatamente el menú.
             */
            event.stopPropagation();


            if (isMobile()) {

                /*
                 * En móvil/tablet alternamos el sidebar.
                 */
                panelContainer.classList.toggle(
                    "sidebar-mobile-open"
                );

                /*
                 * Actualizamos ☰ / ✕.
                 */
                actualizarBotonMenu();

            } else {

                /*
                 * En escritorio usamos el sidebar
                 * contraído.
                 */
                panelContainer.classList.toggle(
                    "sidebar-collapsed"
                );

            }

        });

    }


    /* ========================================
       CERRAR SIDEBAR AL HACER CLICK AFUERA
    ======================================== */

    document.addEventListener("click", function (event) {

        if (!isMobile()) {
            return;
        }

        if (!panelContainer) {
            return;
        }

        if (
            !panelContainer.classList.contains(
                "sidebar-mobile-open"
            )
        ) {
            return;
        }


        /*
         * Si el click fue dentro del sidebar
         * no hacemos nada.
         */
        if (
            sidebar &&
            sidebar.contains(event.target)
        ) {
            return;
        }


        /*
         * Si el click fue sobre el botón tampoco
         * hacemos nada porque el propio botón
         * controla la apertura/cierre.
         */
        if (
            menuToggle &&
            menuToggle.contains(event.target)
        ) {
            return;
        }


        /*
         * Click fuera del menú:
         * cerramos el sidebar.
         */
        panelContainer.classList.remove(
            "sidebar-mobile-open"
        );

        actualizarBotonMenu();

    });


    /* ========================================
       CERRAR AL SELECCIONAR UNA OPCIÓN
    ======================================== */

    if (sidebar) {

        const sidebarLinks =
            sidebar.querySelectorAll("a");

        sidebarLinks.forEach(function (link) {

            link.addEventListener("click", function () {

                if (!isMobile()) {
                    return;
                }

                panelContainer.classList.remove(
                    "sidebar-mobile-open"
                );

                actualizarBotonMenu();

            });

        });

    }


    /* ========================================
       CAMBIO DE TAMAÑO DE PANTALLA
    ======================================== */

    window.addEventListener("resize", function () {

        if (!panelContainer) {
            return;
        }


        /*
         * Si volvemos a escritorio,
         * quitamos el estado móvil.
         */
        if (!isMobile()) {

            panelContainer.classList.remove(
                "sidebar-mobile-open"
            );

        }


        actualizarBotonMenu();

    });


    /* ========================================
       MENÚ DE USUARIO
    ======================================== */

    if (userButton && userDropdown) {

        userButton.addEventListener("click", function (event) {

            event.stopPropagation();

            userDropdown.classList.toggle("show");

        });


        /*
         * Click fuera del menú de usuario.
         */
        document.addEventListener("click", function () {

            userDropdown.classList.remove("show");

        });


        /*
         * Evita que un click dentro del dropdown
         * lo cierre.
         */
        userDropdown.addEventListener("click", function (event) {

            event.stopPropagation();

        });

    }


    /* ========================================
       TECLA ESCAPE
    ======================================== */

    document.addEventListener("keydown", function (event) {

        if (event.key !== "Escape") {
            return;
        }


        /*
         * Cerrar sidebar.
         */
        if (panelContainer) {

            panelContainer.classList.remove(
                "sidebar-mobile-open"
            );

        }


        /*
         * Volver el botón a ☰.
         */
        actualizarBotonMenu();


        /*
         * Cerrar menú de usuario.
         */
        if (userDropdown) {

            userDropdown.classList.remove("show");

        }

    });


    /* ========================================
       ESTADO INICIAL DEL BOTÓN
    ======================================== */

    actualizarBotonMenu();

});