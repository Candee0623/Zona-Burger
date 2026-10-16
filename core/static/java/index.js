'use strict';

(() => {
    const CONFIG = {
        endpointEstado: '/api/negocio/estado/',
        intervalo: 5000,
        claveScroll: 'index_scroll_temporal'
    };

    const elementos = {
        kicker: document.getElementById('hero-kicker-estado'),
        kickerTexto: document.getElementById('hero-kicker-texto'),
        kickerIcono: document.getElementById('hero-kicker-icon'),
        statusDot: document.getElementById('hero-status-dot'),
        statusTexto: document.getElementById('hero-status-texto')
    };

    let intervaloId = null;
    let consultaEnCurso = false;
    let paginaActiva = !document.hidden;
    let erroresConsecutivos = 0;

    /*
     * ESTADO DEL LOCAL
     */

    function aplicarEstado(data) {
        if (!data || typeof data.abierto !== 'boolean') {
            return;
        }

        const abierto = data.abierto;

        if (elementos.kicker) {
            elementos.kicker.classList.remove('loading');

            elementos.kicker.classList.toggle('abierto', abierto);
            elementos.kicker.classList.toggle('cerrado', !abierto);
        }

        if (elementos.kickerTexto) {
            elementos.kickerTexto.textContent =
                abierto ? 'Abierto' : 'Cerrado';
        }

        if (elementos.statusDot) {
            elementos.statusDot.classList.remove(
                'dot-loading',
                'dot-abierto',
                'dot-cerrado'
            );

            elementos.statusDot.classList.add(
                abierto ? 'dot-abierto' : 'dot-cerrado'
            );
        }

        if (elementos.statusTexto) {
            elementos.statusTexto.textContent =
                data.mensaje ||
                (abierto
                    ? 'Estamos abiertos'
                    : 'En este momento estamos cerrados');
        }
    }

    /*
     * CONSULTA A DJANGO
     */

    async function sincronizarEstado() {
        if (consultaEnCurso || document.hidden) {
            return;
        }

        consultaEnCurso = true;

        try {
            const respuesta = await fetch(
                CONFIG.endpointEstado,
                {
                    method: 'GET',
                    headers: {
                        Accept: 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    cache: 'no-store',
                    credentials: 'same-origin'
                }
            );

            if (!respuesta.ok) {
                throw new Error(`HTTP ${respuesta.status}`);
            }

            const data = await respuesta.json();

            if (
                !data ||
                typeof data.abierto !== 'boolean'
            ) {
                throw new Error(
                    'La respuesta no contiene un estado válido.'
                );
            }

            erroresConsecutivos = 0;
            aplicarEstado(data);

        } catch (error) {
            erroresConsecutivos++;

            if (erroresConsecutivos === 1) {
                console.warn(
                    'No se pudo actualizar el estado del local.',
                    error
                );
            }

        } finally {
            consultaEnCurso = false;
        }
    }

    /*
     * ACTUALIZACIÓN PERIÓDICA
     */

    function iniciarActualizacion() {
        detenerActualizacion();

        if (document.hidden) {
            return;
        }

        sincronizarEstado();

        intervaloId = window.setInterval(
            sincronizarEstado,
            CONFIG.intervalo
        );
    }

    function detenerActualizacion() {
        if (intervaloId !== null) {
            window.clearInterval(intervaloId);
            intervaloId = null;
        }
    }

    /*
     * PERSISTENCIA TEMPORAL DE LA POSICIÓN DE SCROLL
     *
     * sessionStorage permite conservar la posición después
     * de recargar la página en esta pestaña.
     *
     * No guarda productos, precios ni stock.
     */

    function guardarScroll() {
        try {
            sessionStorage.setItem(
                CONFIG.claveScroll,
                String(window.scrollY)
            );
        } catch (error) {
            console.warn(
                'No se pudo guardar la posición de la página.',
                error
            );
        }
    }

    function recuperarScroll() {
        try {
            const valor = sessionStorage.getItem(
                CONFIG.claveScroll
            );

            if (valor === null) {
                return;
            }

            const posicion = Number(valor);

            sessionStorage.removeItem(CONFIG.claveScroll);

            if (!Number.isFinite(posicion) || posicion < 0) {
                return;
            }

            requestAnimationFrame(() => {
                window.scrollTo({
                    top: posicion,
                    left: 0,
                    behavior: 'instant'
                });
            });

        } catch (error) {
            console.warn(
                'No se pudo recuperar la posición de la página.',
                error
            );
        }
    }

    /*
     * CICLO DE VIDA DE LA PESTAÑA
     */

    document.addEventListener(
        'visibilitychange',
        () => {
            paginaActiva = !document.hidden;

            if (paginaActiva) {
                iniciarActualizacion();
            } else {
                detenerActualizacion();
            }
        }
    );

    window.addEventListener(
        'pagehide',
        guardarScroll
    );

    window.addEventListener(
        'pageshow',
        () => {
            if (document.visibilityState === 'visible') {
                iniciarActualizacion();
            }
        }
    );

    /*
     * INICIALIZACIÓN
     */

    recuperarScroll();
    iniciarActualizacion();

})();