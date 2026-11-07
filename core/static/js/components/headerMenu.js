document.addEventListener("DOMContentLoaded", function () {

    const menuToggle = document.getElementById("zb-menu-toggle");
    const navMenu = document.getElementById("zb-nav-menu");

    if (!menuToggle || !navMenu) {
        return;
    }

    /* ABRIR / CERRAR MENÚ */

    menuToggle.addEventListener("click", function (event) {

        event.stopPropagation();

        const abierto = navMenu.classList.toggle("active");

        menuToggle.classList.toggle("active", abierto);

        menuToggle.setAttribute(
            "aria-expanded",
            abierto ? "true" : "false"
        );

        menuToggle.setAttribute(
            "aria-label",
            abierto ? "Cerrar menú" : "Abrir menú"
        );

    });

    /* CERRAR AL SELECCIONAR UNA OPCIÓN */

    navMenu.querySelectorAll("a").forEach(function (link) {

        link.addEventListener("click", function () {

            navMenu.classList.remove("active");

            menuToggle.classList.remove("active");

            menuToggle.setAttribute(
                "aria-expanded",
                "false"
            );

            menuToggle.setAttribute(
                "aria-label",
                "Abrir menú"
            );

        });

    });

    /* CERRAR AL HACER CLICK AFUERA */

    document.addEventListener("click", function (event) {

        const headerWrapper = document.querySelector(
            ".zb-header-wrapper"
        );

        if (!headerWrapper) {
            return;
        }

        if (!headerWrapper.contains(event.target)) {

            navMenu.classList.remove("active");

            menuToggle.classList.remove("active");

            menuToggle.setAttribute(
                "aria-expanded",
                "false"
            );

            menuToggle.setAttribute(
                "aria-label",
                "Abrir menú"
            );

        }

    });

});
