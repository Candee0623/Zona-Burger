document.addEventListener('DOMContentLoaded', function () {

    // ============================================================
    // MENÚ MÓVIL
    // ============================================================

    const menuToggle = document.getElementById('menu-toggle');
    const navMenu = document.getElementById('nav-menu');

    if (menuToggle && navMenu) {
        menuToggle.addEventListener('click', function () {
            navMenu.classList.toggle('active');
            menuToggle.classList.toggle('is-active');
        });
    }


    // ============================================================
    // ELEMENTOS DEL MENÚ
    // ============================================================

    const menuDinamico = document.getElementById(
        'menu-dinamico'
    );

    const categoriasDinamicas = document.getElementById(
        'categorias-dinamicas'
    );

    const menuActualizacionesUrl =
        window.MENU_ACTUALIZACIONES_URL;


    // ============================================================
    // OBSERVER DE CATEGORÍAS
    // ============================================================

    let observerCategorias = null;


    function inicializarNavegacionCategorias() {

        const chips = document.querySelectorAll(
            '.categoria-chip'
        );

        const secciones = document.querySelectorAll(
            '.categoria-seccion'
        );


        // --------------------------------------------------------
        // Click en una categoría
        // --------------------------------------------------------

        chips.forEach(function (chip) {

            chip.addEventListener('click', function (event) {

                event.preventDefault();

                const targetId =
                    this.getAttribute('href') ||
                    `#${this.getAttribute('data-target')}`;

                const targetSection =
                    document.querySelector(targetId);


                if (targetSection) {

                    targetSection.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });

                }


                chips.forEach(function (categoria) {
                    categoria.classList.remove('active');
                });


                this.classList.add('active');


                this.scrollIntoView({
                    behavior: 'smooth',
                    inline: 'center',
                    block: 'nearest'
                });

            });

        });


        // --------------------------------------------------------
        // Reiniciamos el observer porque las secciones pueden
        // haber sido reemplazadas dinámicamente.
        // --------------------------------------------------------

        if (observerCategorias) {
            observerCategorias.disconnect();
        }


        const observerOptions = {
            root: null,
            rootMargin: '-20% 0px -60% 0px',
            threshold: 0
        };


        observerCategorias =
            new IntersectionObserver(
                function (entries) {

                    entries.forEach(function (entry) {

                        if (!entry.isIntersecting) {
                            return;
                        }


                        const id =
                            entry.target.getAttribute('id');


                        chips.forEach(function (chip) {

                            const chipTarget =
                                chip.getAttribute('href') === `#${id}` ||
                                chip.getAttribute('data-target') === id;


                            if (chipTarget) {

                                chip.classList.add('active');

                                chip.scrollIntoView({
                                    behavior: 'smooth',
                                    inline: 'center',
                                    block: 'nearest'
                                });

                            } else {

                                chip.classList.remove('active');

                            }

                        });

                    });

                },
                observerOptions
            );


        secciones.forEach(function (section) {
            observerCategorias.observe(section);
        });

    }


    // Inicializamos las categorías al cargar la página.
    inicializarNavegacionCategorias();


    // ============================================================
    // ACTUALIZACIÓN AUTOMÁTICA
    // ============================================================

    let menuVersion = null;

    let sincronizandoMenu = false;


    async function sincronizarMenu() {

        // Evita consultas simultáneas.
        if (sincronizandoMenu) {
            return;
        }


        // No hacemos consultas si la pestaña está oculta.
        if (document.hidden) {
            return;
        }


        if (
            !menuDinamico ||
            !categoriasDinamicas ||
            !menuActualizacionesUrl
        ) {
            console.warn(
                'No se encontraron los elementos necesarios para actualizar el menú.'
            );

            return;
        }


        sincronizandoMenu = true;


        try {

            // ----------------------------------------------------
            // Cabeceras de la petición.
            // ----------------------------------------------------

            const headers = {
                'X-Requested-With': 'XMLHttpRequest'
            };


            if (menuVersion) {

                headers['X-Menu-Version'] =
                    menuVersion;

            }


            // ----------------------------------------------------
            // Consultamos Django.
            // ----------------------------------------------------

            const response = await fetch(
                menuActualizacionesUrl,
                {
                    method: 'GET',
                    headers: headers,
                    cache: 'no-store'
                }
            );


            if (!response.ok) {

                console.warn(
                    'El servidor respondió:',
                    response.status
                );

                return;
            }


            const data = await response.json();


            // ----------------------------------------------------
            // Primera consulta.
            //
            // El HTML que ya está en pantalla corresponde a esta
            // versión, por lo que simplemente la guardamos.
            // ----------------------------------------------------

            if (!menuVersion) {

                menuVersion = data.version;

                console.log(
                    'Versión inicial del menú:',
                    menuVersion
                );

                return;
            }


            // ----------------------------------------------------
            // No hubo cambios.
            // ----------------------------------------------------

            if (!data.cambios) {

                return;
            }


            // ----------------------------------------------------
            // CAMBIO DETECTADO
            // ----------------------------------------------------

            console.log(
                'Cambio detectado en el menú.'
            );


            console.log(
                'Versión anterior:',
                menuVersion
            );


            console.log(
                'Versión nueva:',
                data.version
            );


            // ----------------------------------------------------
            // Guardamos primero la nueva versión.
            // ----------------------------------------------------

            menuVersion = data.version;


            // ----------------------------------------------------
            // Guardamos la posición del usuario.
            // ----------------------------------------------------

            const scrollActual =
                window.scrollY;


            // ----------------------------------------------------
            // Actualizamos productos.
            // ----------------------------------------------------

            if (
                typeof data.menu === 'string'
            ) {

                menuDinamico.innerHTML =
                    data.menu;

            }


            // ----------------------------------------------------
            // Actualizamos categorías.
            // ----------------------------------------------------

            if (
                typeof data.categorias === 'string'
            ) {

                categoriasDinamicas.innerHTML =
                    data.categorias;

            }


            // ----------------------------------------------------
            // Volvemos a conectar los eventos porque acabamos
            // de reemplazar el HTML.
            // ----------------------------------------------------

            inicializarNavegacionCategorias();


            // ----------------------------------------------------
            // Recuperamos la posición anterior.
            // ----------------------------------------------------

            window.scrollTo(
                0,
                scrollActual
            );


            console.log(
                'Menú actualizado correctamente.'
            );


        } catch (error) {

            console.error(
                'Error actualizando el menú:',
                error
            );

        } finally {

            sincronizandoMenu = false;

        }

    }


    // ============================================================
    // INICIO
    // ============================================================

    /*
     * Hacemos una consulta inmediatamente.
     */
    sincronizarMenu();


    /*
     * Después comprobamos cada 2 segundos.
     */
    setInterval(
        sincronizarMenu,
        2000
    );

});