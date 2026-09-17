document.addEventListener("DOMContentLoaded", function () {


    /* ========================================
       MENÚ LATERAL
    ======================================== */

    const menuToggle = document.getElementById("menuToggle");
    const panelContainer = document.getElementById("panelContainer");


    if (menuToggle && panelContainer) {

        menuToggle.addEventListener("click", function () {

            if (window.innerWidth <= 700) {

                panelContainer.classList.toggle(
                    "sidebar-mobile-open"
                );

            } else {

                panelContainer.classList.toggle(
                    "sidebar-collapsed"
                );

            }

        });

    }


    /* ========================================
       MENÚ USUARIO
    ======================================== */

    const userButton = document.getElementById("userButton");
    const userDropdown = document.getElementById("userDropdown");


    if (userButton && userDropdown) {

        userButton.addEventListener("click", function (event) {

            event.stopPropagation();

            userDropdown.classList.toggle("show");

        });


        document.addEventListener("click", function () {

            userDropdown.classList.remove("show");

        });


        userDropdown.addEventListener("click", function (event) {

            event.stopPropagation();

        });

    }


});