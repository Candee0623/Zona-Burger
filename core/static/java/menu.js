document.addEventListener(
    'DOMContentLoaded',
    function () {


        // ============================================================
        // ELEMENTOS DEL MENÚ
        // ============================================================

        const menuDinamico =
            document.getElementById(
                'menu-dinamico'
            );


        const categoriasDinamicas =
            document.getElementById(
                'categorias-dinamicas'
            );


        const menuActualizacionesUrl =
            window.MENU_ACTUALIZACIONES_URL;



        // ============================================================
        // OBSERVER DE CATEGORÍAS
        // ============================================================

        let observerCategorias = null;



        function inicializarNavegacionCategorias() {


            const chips =
                document.querySelectorAll(
                    '.categoria-chip'
                );


            const secciones =
                document.querySelectorAll(
                    '.categoria-seccion'
                );



            // --------------------------------------------------------
            // CLICK EN UNA CATEGORÍA
            // --------------------------------------------------------

            chips.forEach(
                function (chip) {

                    chip.addEventListener(
                        'click',
                        function (event) {

                            event.preventDefault();


                            const targetId =
                                this.getAttribute(
                                    'href'
                                ) ||
                                `#${this.getAttribute(
                                    'data-target'
                                )}`;


                            const targetSection =
                                document.querySelector(
                                    targetId
                                );


                            if (targetSection) {

                                targetSection.scrollIntoView(
                                    {
                                        behavior: 'smooth',
                                        block: 'start'
                                    }
                                );

                            }



                            // ------------------------------------------------
                            // ACTUALIZAR CATEGORÍA ACTIVA
                            // ------------------------------------------------

                            chips.forEach(
                                function (categoria) {

                                    categoria.classList.remove(
                                        'active'
                                    );

                                }
                            );


                            this.classList.add(
                                'active'
                            );



                            // ------------------------------------------------
                            // CENTRAR CATEGORÍA
                            // ------------------------------------------------

                            const contenedor =
                                categoriasDinamicas;


                            if (contenedor) {

                                const chipLeft =
                                    this.offsetLeft;


                                const chipWidth =
                                    this.offsetWidth;


                                const contenedorWidth =
                                    contenedor.clientWidth;


                                const posicion =
                                    chipLeft -
                                    (
                                        contenedorWidth / 2
                                    ) +
                                    (
                                        chipWidth / 2
                                    );


                                contenedor.scrollTo(
                                    {
                                        left:
                                            Math.max(
                                                0,
                                                posicion
                                            ),

                                        behavior:
                                            'smooth'
                                    }
                                );

                            }

                        }
                    );

                }
            );



            // --------------------------------------------------------
            // REINICIAR OBSERVER
            // --------------------------------------------------------

            if (observerCategorias) {

                observerCategorias.disconnect();

            }



            // --------------------------------------------------------
            // INTERSECTION OBSERVER
            // --------------------------------------------------------

            const observerOptions = {

                root: null,

                rootMargin:
                    '-20% 0px -60% 0px',

                threshold: 0

            };



            observerCategorias =
                new IntersectionObserver(
                    function (entries) {

                        entries.forEach(
                            function (entry) {

                                if (
                                    !entry.isIntersecting
                                ) {

                                    return;

                                }


                                const id =
                                    entry.target.getAttribute(
                                        'id'
                                    );


                                chips.forEach(
                                    function (chip) {

                                        const href =
                                            chip.getAttribute(
                                                'href'
                                            );


                                        const dataTarget =
                                            chip.getAttribute(
                                                'data-target'
                                            );


                                        const chipTarget =
                                            href === `#${id}` ||
                                            dataTarget === id;


                                        if (chipTarget) {

                                            chip.classList.add(
                                                'active'
                                            );

                                        } else {

                                            chip.classList.remove(
                                                'active'
                                            );

                                        }

                                    }
                                );

                            }
                        );

                    },
                    observerOptions
                );



            // --------------------------------------------------------
            // OBSERVAR SECCIONES
            // --------------------------------------------------------

            secciones.forEach(
                function (section) {

                    observerCategorias.observe(
                        section
                    );

                }
            );

        }



        // ============================================================
        // INICIALIZAR CATEGORÍAS
        // ============================================================

        inicializarNavegacionCategorias();



        // ============================================================
        // ACTUALIZACIÓN AUTOMÁTICA
        // ============================================================

        let menuVersion = null;

        let sincronizandoMenu = false;



        async function sincronizarMenu() {


            // --------------------------------------------------------
            // EVITAR CONSULTAS SIMULTÁNEAS
            // --------------------------------------------------------

            if (sincronizandoMenu) {

                return;

            }



            // --------------------------------------------------------
            // NO CONSULTAR SI LA PESTAÑA ESTÁ OCULTA
            // --------------------------------------------------------

            if (document.hidden) {

                return;

            }



            // --------------------------------------------------------
            // VERIFICAR ELEMENTOS
            // --------------------------------------------------------

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
                // CABECERAS
                // ----------------------------------------------------

                const headers = {

                    'X-Requested-With':
                        'XMLHttpRequest'

                };


                if (menuVersion) {

                    headers[
                        'X-Menu-Version'
                    ] = menuVersion;

                }



                // ----------------------------------------------------
                // CONSULTAR DJANGO
                // ----------------------------------------------------

                const response =
                    await fetch(
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



                const data =
                    await response.json();



                // ----------------------------------------------------
                // PRIMERA CONSULTA
                // ----------------------------------------------------

                if (!menuVersion) {

                    menuVersion =
                        data.version;


                    console.log(
                        'Versión inicial del menú:',
                        menuVersion
                    );


                    return;

                }



                // ----------------------------------------------------
                // NO HUBO CAMBIOS
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
                // GUARDAR SCROLL VERTICAL
                // ----------------------------------------------------

                const scrollActual =
                    window.scrollY;



                // ----------------------------------------------------
                // GUARDAR SCROLL HORIZONTAL
                // ----------------------------------------------------

                const scrollCategorias =
                    categoriasDinamicas.scrollLeft;



                // ----------------------------------------------------
                // GUARDAR SECCIÓN VISIBLE
                // ----------------------------------------------------

                const seccionVisible =
                    document.querySelector(
                        '.categoria-seccion'
                    );


                /*
                 * Se conserva la referencia para no
                 * cambiar el comportamiento original.
                 */

                void seccionVisible;



                // ----------------------------------------------------
                // GUARDAR NUEVA VERSIÓN
                // ----------------------------------------------------

                menuVersion =
                    data.version;



                // ----------------------------------------------------
                // ACTUALIZAR PRODUCTOS
                // ----------------------------------------------------

                if (
                    typeof data.menu ===
                    'string'
                ) {

                    menuDinamico.innerHTML =
                        data.menu;

                }



                // ----------------------------------------------------
                // ACTUALIZAR CATEGORÍAS
                // ----------------------------------------------------

                if (
                    typeof data.categorias ===
                    'string'
                ) {

                    categoriasDinamicas.innerHTML =
                        data.categorias;

                }



                // ----------------------------------------------------
                // RECONSTRUIR EVENTOS
                // ----------------------------------------------------

                inicializarNavegacionCategorias();



                // ----------------------------------------------------
                // RESTAURAR SCROLL HORIZONTAL
                // ----------------------------------------------------

                categoriasDinamicas.scrollLeft =
                    scrollCategorias;



                // ----------------------------------------------------
                // RESTAURAR SCROLL VERTICAL
                // ----------------------------------------------------

                requestAnimationFrame(
                    function () {

                        window.scrollTo(
                            {
                                top:
                                    scrollActual,

                                left: 0,

                                behavior:
                                    'instant'
                            }
                        );

                    }
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

        sincronizarMenu();



        // ============================================================
        // ACTUALIZACIÓN CADA 2 SEGUNDOS
        // ============================================================

        setInterval(
            sincronizarMenu,
            2000
        );

    }
);