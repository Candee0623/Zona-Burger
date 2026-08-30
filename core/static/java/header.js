document.addEventListener("DOMContentLoaded", function () {
    const toggleButton = document.getElementById("menu-toggle");
    const navMenu = document.getElementById("nav-menu");

    if (toggleButton && navMenu) {
        toggleButton.addEventListener("click", function () {
            navMenu.classList.toggle("active");
        });
    }
});