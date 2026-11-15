/* MODAL TICKET */

const TICKET_TIMEOUT_MS = 20000;

let ticketSolicitudActual = 0;
let ticketControlador = null;
let ticketCargado = false;

function ticketModalAbierto() {
    const overlay = document.getElementById('modalTicketOverlay');
    return !!(overlay && overlay.classList.contains('active'));
}

function mostrarMensajeTicket(contenido, texto, url, conReintento) {
    contenido.innerHTML = '';

    const caja = document.createElement('div');
    caja.style.cssText = 'text-align:center;color:#dc3545;padding:25px;';

    const parrafo = document.createElement('div');
    parrafo.textContent = texto;
    caja.appendChild(parrafo);

    if (conReintento) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'btn btn-secondary btn-sm';
        boton.style.marginTop = '12px';
        boton.textContent = 'Reintentar';
        boton.addEventListener('click', function () {
            abrirTicketModal(url);
        });
        caja.appendChild(boton);
    }

    contenido.appendChild(caja);
}

function abrirTicketModal(url) {

    const overlay = document.getElementById('modalTicketOverlay');
    const contenido = document.getElementById('contenido-ticket-modal');

    overlay.classList.add('active');

    // Si había una carga anterior en curso, se cancela.
    if (ticketControlador) {
        ticketControlador.abortadoPorNuevaSolicitud = true;
        ticketControlador.abort();
    }

    const solicitud = ++ticketSolicitudActual;
    const controlador = new AbortController();
    ticketControlador = controlador;
    ticketCargado = false;

    contenido.innerHTML =
        '<div style="text-align:center;padding:30px;color:#666;">' +
        '<div style="margin-bottom:8px;">Cargando ticket...</div>' +
        '</div>';

    // Si el servidor no responde, no se queda cargando para siempre.
    let vencio = false;
    const temporizador = setTimeout(function () {
        vencio = true;
        controlador.abort();
    }, TICKET_TIMEOUT_MS);

    fetch(url, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        cache: 'no-store',
        credentials: 'same-origin',
        signal: controlador.signal
    })
    .then(function (response) {

        if (response.status === 401) {
            throw new Error('SESION');
        }

        if (response.status === 403) {
            throw new Error('PERMISO');
        }

        if (!response.ok) {
            throw new Error('HTTP ' + response.status);
        }

        return response.text();
    })
    .then(function (html) {

        // Llegó una respuesta vieja: se ignora.
        if (solicitud !== ticketSolicitudActual) {
            return;
        }

        contenido.innerHTML = html;
        ticketCargado = true;
    })
    .catch(function (error) {

        if (solicitud !== ticketSolicitudActual) {
            return;
        }

        if (error.name === 'AbortError' && !vencio) {
            return;
        }

        console.error('Error cargando ticket:', error);

        let texto = 'No se pudo cargar el ticket.';

        if (vencio) {
            texto = 'El ticket tardó demasiado en cargar.';
        } else if (error.message === 'SESION') {
            texto = 'Tu sesión expiró. Volvé a iniciar sesión.';
        } else if (error.message === 'PERMISO') {
            texto = 'No tenés permiso para ver este ticket.';
        }

        mostrarMensajeTicket(contenido, texto, url, !(error.message === 'SESION' || error.message === 'PERMISO'));
    })
    .finally(function () {
        clearTimeout(temporizador);
    });
}

function cerrarTicketModal() {

    if (ticketControlador) {
        ticketControlador.abortadoPorNuevaSolicitud = true;
        ticketControlador.abort();
        ticketControlador = null;
    }

    ticketSolicitudActual++;

    const overlay = document.getElementById('modalTicketOverlay');

    if (overlay) {
        overlay.classList.remove('active');
    }
}

function textoCssTicket(contenido) {

    // Copia las reglas de la hoja del ticket que ya cargó la página, para que
    // la impresión no dependa de volver a descargarla.
    const enlace = contenido.querySelector('link[rel="stylesheet"]');
    let css = '';

    try {
        if (enlace && enlace.sheet) {
            Array.prototype.forEach.call(
                enlace.sheet.cssRules,
                function (regla) {
                    css += regla.cssText + '\n';
                }
            );
        }
    } catch (error) {
        css = '';
    }

    return {
        css: css,
        urlCss: enlace ? enlace.href : ''
    };
}

function imprimirModal() {

    const contenido = document.getElementById('contenido-ticket-modal');
    const ticket = contenido.querySelector('.ticket-cocina');

    // Solo se imprime si el ticket ya cargó de verdad.
    if (!ticketCargado || !ticket) {
        ZB.avisar({
            titulo: 'El ticket todavía no está listo',
            mensaje: 'Esperá a que termine de cargar para imprimirlo.',
            tipo: 'info'
        });
        return;
    }

    const estilos = textoCssTicket(contenido);

    // Se imprime desde un marco oculto de esta misma página: no depende de
    // ventanas emergentes (que el navegador suele bloquear) ni de que otra
    // ventana termine de cargar.
    const anterior = document.getElementById('zb-marco-impresion');
    if (anterior) {
        anterior.remove();
    }

    const marco = document.createElement('iframe');
    marco.id = 'zb-marco-impresion';
    marco.setAttribute('aria-hidden', 'true');
    marco.title = 'Impresión del ticket';
    marco.style.cssText =
        'position:fixed;right:0;bottom:0;width:0;height:0;border:0;';

    let impreso = false;

    function limpiar() {
        if (marco.parentNode) {
            marco.parentNode.removeChild(marco);
        }
    }

    marco.onload = function () {

        if (impreso) {
            return;
        }
        impreso = true;

        // Pequeña espera para que el marco termine de pintar el contenido.
        setTimeout(function () {
            try {
                const ventana = marco.contentWindow;
                ventana.onafterprint = function () {
                    setTimeout(limpiar, 500);
                };
                ventana.focus();
                ventana.print();
            } catch (error) {
                console.error('Error al imprimir el ticket:', error);
                limpiar();
                ZB.avisar({
                    titulo: 'No se pudo imprimir',
                    mensaje: 'Ocurrió un problema al abrir la impresión. Intentá de nuevo.',
                    tipo: 'info'
                });
                return;
            }

            // Respaldo por si el navegador nunca avisa que terminó de imprimir.
            setTimeout(limpiar, 120000);
        }, 150);
    };

    marco.srcdoc =
        '<!DOCTYPE html><html><head><meta charset="UTF-8">' +
        '<title>Ticket</title>' +
        (estilos.css
            ? '<style>' + estilos.css + '</style>'
            : (estilos.urlCss
                ? '<link rel="stylesheet" href="' + estilos.urlCss + '">'
                : '')) +
        '<style>' +
        '@page{size:58mm auto;margin:0;}' +
        'html,body{margin:0;padding:0;background:#fff;}' +
        'body{font-family:Arial,Helvetica,sans-serif;}' +
        '</style></head><body>' +
        ticket.outerHTML +
        '</body></html>';

    document.body.appendChild(marco);
}

/* MODAL CAMBIAR ESTADO */

const URL_CAMBIAR_ESTADO_TEMPLATE =
    window.ZB_PANEL_INICIO.urlCambiarEstado;

function abrirEstadoModal(
    idPedido,
    estadoActualId
) {

    const overlay =
        document.getElementById(
            'modalEstadoOverlay'
        );

    const form =
        document.getElementById(
            'formCambiarEstado'
        );

    const select =
        document.getElementById(
            'selectNuevoEstado'
        );

    form.action =
        URL_CAMBIAR_ESTADO_TEMPLATE.replace(
            '/0/',
            '/' +
            idPedido +
            '/'
        );

    document.getElementById('inputEstadoEsperado').value =
        estadoActualId ? String(estadoActualId) : '';

    document.getElementById('inputJustificacion').value = '';

    if (estadoActualId) {

        select.value =
            String(
                estadoActualId
            );

    }

    verificarEstadoCancelado(
        select
    );

    overlay.classList.add(
        'active'
    );

}

function cerrarEstadoModal() {

    document
        .getElementById(
            'modalEstadoOverlay'
        )
        .classList.remove(
            'active'
        );

}

function verificarEstadoCancelado(
    selectElement
) {

    const grupo =
        document.getElementById(
            'grupoJustificacion'
        );

    const input =
        document.getElementById(
            'inputJustificacion'
        );

    const opcion =
        selectElement.options[
            selectElement.selectedIndex
        ];

    const texto =
        opcion
            ? opcion.text
            : '';

    const estaCancelado =
        texto
            .toLowerCase()
            .includes(
                'cancelado'
            );

    if (estaCancelado) {

        grupo.style.display =
            'block';

        input.required =
            true;

    } else {

        grupo.style.display =
            'none';

        input.required =
            false;

        input.value =
            '';

    }

}

/* CERRAR MODALES */

document.addEventListener(
    'click',
    function (event) {

        const ticketOverlay =
            document.getElementById(
                'modalTicketOverlay'
            );

        const estadoOverlay =
            document.getElementById(
                'modalEstadoOverlay'
            );

        if (
            event.target ===
            ticketOverlay
        ) {

            cerrarTicketModal();

        }

        if (
            event.target ===
            estadoOverlay
        ) {

            cerrarEstadoModal();

        }

    }
);

document.addEventListener(
    'keydown',
    function (event) {

        if (
            event.key ===
            'Escape'
        ) {

            cerrarTicketModal();

            cerrarEstadoModal();

        }

    }
);

/* WHATSAPP */

(function abrirWhatsAppSiCorresponde() {

    const params =
        new URLSearchParams(
            window.location.search
        );

    const waUrl =
        params.get(
            'wa_url'
        );

    if (!waUrl) {
        return;
    }

    window.open(
        waUrl,
        '_blank'
    );

    params.delete(
        'wa_url'
    );

    const nuevaUrl =
        window.location.pathname +
        (
            params.toString()
                ? '?' +
                  params.toString()
                : ''
        ) +
        window.location.hash;

    window.history.replaceState(
        {},
        document.title,
        nuevaUrl
    );

})();

/* ACTUALIZACIÓN AUTOMÁTICA */

document.addEventListener(
    'DOMContentLoaded',
    function () {

        const indicador =
            document.getElementById(
                'panel-sync-indicator'
            );

        let sincronizando = false;

        async function sincronizarPanel() {

            if (sincronizando) {
                return;
            }

            if (document.hidden) {
                return;
            }

            // Con el ticket abierto no se compite por el servidor.
            if (ticketModalAbierto()) {
                return;
            }

            sincronizando = true;

            const posiciones = [];
            let el = document.getElementById('pedidos-panel');

            while (el) {
                posiciones.push([el, el.scrollLeft, el.scrollTop]);
                el = el.parentElement;
            }

            const restaurarScroll = () => {
                posiciones.forEach(([nodo, left, top]) => {
                    nodo.scrollLeft = left;
                    nodo.scrollTop = top;
                });
            };

            try {

                indicador.innerHTML =
                    '<span class="panel-sync-dot"></span>' +
                    '<span>Actualizando...</span>';

                indicador.classList.add(
                    'actualizando'
                );

                const response =
                    await fetch(
                        window.location.href,
                        {
                            method: 'GET',

                            headers: {
                                'X-Requested-With':
                                    'XMLHttpRequest',

                                'Cache-Control':
                                    'no-cache'
                            },

                            cache: 'no-store'
                        }
                    );

                if (!response.ok) {

                    throw new Error(
                        'HTTP ' +
                        response.status
                    );

                }

                const html =
                    await response.text();

                const parser =
                    new DOMParser();

                const documento =
                    parser.parseFromString(
                        html,
                        'text/html'
                    );

                const nuevasMetricas =
                    documento.getElementById(
                        'metricas-panel'
                    );

                const nuevosEstados =
                    documento.getElementById(
                        'estados-panel'
                    );

                const nuevosPedidos =
                    documento.getElementById(
                        'pedidos-panel'
                    );

                if (
                    !nuevasMetricas ||
                    !nuevosEstados ||
                    !nuevosPedidos
                ) {

                    console.warn(
                        'La respuesta no contiene los bloques esperados.'
                    );

                    return;

                }

                const metricasActuales =
                    document.getElementById(
                        'metricas-panel'
                    );

                const estadosActuales =
                    document.getElementById(
                        'estados-panel'
                    );

                const pedidosActuales =
                    document.getElementById(
                        'pedidos-panel'
                    );

                if (
                    metricasActuales.innerHTML !==
                    nuevasMetricas.innerHTML
                ) {

                    metricasActuales.innerHTML =
                        nuevasMetricas.innerHTML;

                }

                if (
                    estadosActuales.innerHTML !==
                    nuevosEstados.innerHTML
                ) {

                    estadosActuales.innerHTML =
                        nuevosEstados.innerHTML;

                }

                if (
                    pedidosActuales.innerHTML !==
                    nuevosPedidos.innerHTML
                ) {

                    pedidosActuales.innerHTML =
                        nuevosPedidos.innerHTML;

                }

                window.scrollTo({
                    left: scrollX,
                    top: scrollY,
                    behavior: 'instant'
                });

                indicador.innerHTML =
                    '<span class="panel-sync-dot"></span>' +
                    '<span>Sincronizado</span>';

            } catch (error) {

                console.error(
                    'Error actualizando panel:',
                    error
                );

                indicador.innerHTML =
                    '<span class="panel-sync-dot"></span>' +
                    '<span>Sin conexión</span>';

            } finally {

                indicador.classList.remove(
                    'actualizando'
                );

                sincronizando = false;

            }

        }

        /* Primera sincronización. */

        sincronizarPanel();

        /* Si entra un pedido nuevo, se actualiza la lista enseguida
           (el aviso con sonido lo da notificacionPedidos.js). */

        document.addEventListener(
            'zb:pedido-nuevo',
            function () {
                sincronizarPanel();
            }
        );

        /* Al volver a esta pestaña se actualiza sin esperar. */

        document.addEventListener(
            'visibilitychange',
            function () {
                if (!document.hidden) {
                    sincronizarPanel();
                }
            }
        );

        /* Actualización automática cada 5 segundos. */

        setInterval(
            sincronizarPanel,
            5000
        );

    }
);

/* MANTENER LA POSICIÓN AL ACTUALIZAR PAGO O ESTADO */

/* "Pagado / Debe" y "Cambiar estado" envían un formulario y el servidor
   redirige al panel, lo que recarga la página y la deja arriba de todo.
   Antes de enviar se guarda dónde estaba la pantalla y, al volver, se
   restaura esa posición. */

(function mantenerPosicionDelPanel() {

    const CLAVE = 'zb:panelInicio:scroll';
    const VIGENCIA_MS = 30000;

    function contenedorPrincipal() {
        return document.querySelector('.main-content');
    }

    document.addEventListener(
        'submit',
        function (event) {

            const form = event.target;

            if (
                !form ||
                !form.matches ||
                !form.matches(
                    'form[action*="toggle-pagado"], #formCambiarEstado'
                )
            ) {
                return;
            }

            const contenedor = contenedorPrincipal();

            try {
                sessionStorage.setItem(
                    CLAVE,
                    JSON.stringify({
                        t: Date.now(),
                        x: window.scrollX,
                        y: window.scrollY,
                        cx: contenedor ? contenedor.scrollLeft : 0,
                        cy: contenedor ? contenedor.scrollTop : 0
                    })
                );
            } catch (error) {
                /* Sin almacenamiento disponible: se sigue sin guardar. */
            }

        }
    );

    function restaurar() {

        let datos = null;

        try {
            const crudo = sessionStorage.getItem(CLAVE);

            if (!crudo) {
                return;
            }

            sessionStorage.removeItem(CLAVE);
            datos = JSON.parse(crudo);
        } catch (error) {
            return;
        }

        // Una posición vieja (de otra visita) no se aplica.
        if (!datos || Date.now() - datos.t > VIGENCIA_MS) {
            return;
        }

        function aplicar() {

            const contenedor = contenedorPrincipal();

            if (contenedor) {
                contenedor.scrollLeft = datos.cx;
                contenedor.scrollTop = datos.cy;
            }

            window.scrollTo({
                left: datos.x,
                top: datos.y,
                behavior: 'instant'
            });

        }

        aplicar();

        // Se repite cuando termina de cargar todo, por si el alto de la
        // página cambia al aplicar los estilos o las imágenes.
        window.addEventListener('load', aplicar, { once: true });

    }

    restaurar();

})();
