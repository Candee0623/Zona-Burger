
'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const INTERVALO_ESTADO = 5000;
    const ENDPOINT_ESTADO = '/api/negocio/estado/';

    const botonCheckout = document.getElementById('btn-checkout');
    const contenedor = document.querySelector('.carrito-container');

    if (!contenedor) return;

    let negocioAbierto = null;
    let temporizadorEstado = null;
    let consultaEnCurso = false;

    // --------------------------------------------------
    // AVISO DE NEGOCIO CERRADO
    // --------------------------------------------------

    let avisoCierre = document.getElementById('aviso-negocio-cerrado');

    if (!avisoCierre) {
        avisoCierre = document.createElement('div');
        avisoCierre.id = 'aviso-negocio-cerrado';
        avisoCierre.setAttribute('role', 'status');
        avisoCierre.setAttribute('aria-live', 'polite');

        avisoCierre.style.cssText = [
            'display:none',
            'align-items:flex-start',
            'gap:12px',
            'padding:16px',
            'border-radius:10px',
            'margin-bottom:20px',
            'background:rgba(220,38,38,.15)',
            'border:1px solid rgba(220,38,38,.45)',
            'color:#fca5a5'
        ].join(';');

        avisoCierre.innerHTML = `
            <i class="fa-solid fa-clock"
               style="font-size:1.2rem;color:#ef4444;margin-top:2px">
            </i>
            <div>
                <strong style="display:block;font-size:.92rem;color:#fff;margin-bottom:4px">
                    El negocio está cerrado en este momento.
                </strong>
                <span style="font-size:.84rem;color:#d1d5db">
                    Podrás realizar tu pedido cuando vuelva a abrir.
                    Tus productos se mantienen en el carrito.
                </span>
            </div>
        `;

        const titulo = contenedor.querySelector('h1');

        if (titulo) {
            titulo.insertAdjacentElement('afterend', avisoCierre);
        }
    }

    // --------------------------------------------------
    // ESTADO DEL NEGOCIO
    // --------------------------------------------------

    function aplicarEstadoNegocio(data) {
        if (!data || typeof data.abierto !== 'boolean') return;

        negocioAbierto = data.abierto;

        // Mostrar u ocultar el aviso.
        if (avisoCierre) {
            avisoCierre.style.display = negocioAbierto ? 'none' : 'flex';
        }

        // Actualizar el botón de checkout sin duplicar texto.
        if (botonCheckout) {
            const textoBoton = botonCheckout.querySelector(
                '[data-texto-boton]'
            );

            const icono = botonCheckout.querySelector('i');

            if (textoBoton) {
                textoBoton.textContent = negocioAbierto
                    ? 'Ir al Checkout'
                    : 'Negocio Cerrado';
            }

            if (icono) {
                icono.className = negocioAbierto
                    ? 'fa-solid fa-arrow-right'
                    : 'fa-solid fa-lock';

                icono.style.marginRight = '8px';
            }

            botonCheckout.disabled = !negocioAbierto;
            botonCheckout.title = negocioAbierto
                ? ''
                : 'El negocio está cerrado en este momento';

            botonCheckout.style.background = negocioAbierto
                ? ''
                : '#2a2a2a';

            botonCheckout.style.color = negocioAbierto
                ? ''
                : '#888';

            botonCheckout.style.borderColor = negocioAbierto
                ? ''
                : '#444';

            botonCheckout.style.cursor = negocioAbierto
                ? ''
                : 'not-allowed';

            botonCheckout.style.boxShadow = negocioAbierto
                ? ''
                : 'none';

            botonCheckout.setAttribute(
                'aria-disabled',
                String(!negocioAbierto)
            );
        }
    }

    async function sincronizarEstadoNegocio() {
        if (consultaEnCurso || document.hidden) return;

        consultaEnCurso = true;

        try {
            const respuesta = await fetch(ENDPOINT_ESTADO, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                cache: 'no-store',
                credentials: 'same-origin'
            });

            if (!respuesta.ok) {
                throw new Error(`HTTP ${respuesta.status}`);
            }

            const data = await respuesta.json();

            if (!data || typeof data.abierto !== 'boolean') {
                throw new Error('Respuesta de estado inválida');
            }

            aplicarEstadoNegocio(data);
        } catch (error) {
            // Si falla la red, no asumir que el negocio cerró.
            console.warn(
                'No se pudo actualizar el estado del negocio.',
                error
            );
        } finally {
            consultaEnCurso = false;
        }
    }

    function detenerActualizacion() {
        if (temporizadorEstado !== null) {
            clearInterval(temporizadorEstado);
            temporizadorEstado = null;
        }
    }

    function iniciarActualizacion() {
        detenerActualizacion();

        if (document.hidden) return;

        // Consultar inmediatamente y luego cada cinco segundos.
        sincronizarEstadoNegocio();

        temporizadorEstado = setInterval(
            sincronizarEstadoNegocio,
            INTERVALO_ESTADO
        );
    }

    // --------------------------------------------------
    // IR AL CHECKOUT
    // --------------------------------------------------

    if (botonCheckout) {
        botonCheckout.addEventListener('click', function () {
            if (negocioAbierto === false) {
                return;
            }

            const url = botonCheckout.dataset.checkoutUrl;

            if (url) {
                window.location.href = url;
            }
        });
    }

    // --------------------------------------------------
    // ACTUALIZACIÓN AL CAMBIAR DE PESTAÑA
    // --------------------------------------------------

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            detenerActualizacion();
        } else {
            iniciarActualizacion();
        }
    });

    window.addEventListener('pageshow', function () {
        if (!document.hidden) {
            iniciarActualizacion();
        }
    });

    window.addEventListener('pagehide', detenerActualizacion);

    // --------------------------------------------------
    // INICIALIZACIÓN
    // --------------------------------------------------

    iniciarActualizacion();
});
