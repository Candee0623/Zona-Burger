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

    // Ruta absoluta de la hoja de estilos del ticket (la ventana nueva está vacía).
    const enlaceCss = contenido.querySelector('link[rel="stylesheet"]');
    const urlCss = enlaceCss ? enlaceCss.href : '';

    const ventana = window.open('', '_blank', 'height=700,width=450');

    if (!ventana) {
        ZB.avisar({
            titulo: 'No se pudo imprimir',
            mensaje:
                'El navegador bloqueó la ventana de impresión. ' +
                'Permití las ventanas emergentes para este sitio e intentá de nuevo.',
            tipo: 'info'
        });
        return;
    }

    ventana.document.write(
        '<!DOCTYPE html><html><head><meta charset="UTF-8">' +
        '<title>Ticket</title>' +
        (urlCss ? '<link rel="stylesheet" href="' + urlCss + '">' : '') +
        '<style>' +
        '@page{size:58mm auto;margin:0;}' +
        'body{margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;}' +
        '</style></head><body>' +
        ticket.outerHTML +
        '</body></html>'
    );

    ventana.document.close();
    ventana.focus();

    let impreso = false;

    function imprimir() {
        if (impreso) {
            return;
        }
        impreso = true;
        ventana.onafterprint = function () {
            ventana.close();
        };
        ventana.print();
    }

    // Se imprime cuando la hoja de estilos terminó de cargar
    // (si por algún motivo no avisa, se imprime igual a los 1,5 s).
    const enlaceNuevo = ventana.document.querySelector('link[rel="stylesheet"]');

    if (enlaceNuevo) {
        enlaceNuevo.onload = imprimir;
        enlaceNuevo.onerror = imprimir;
    }

    setTimeout(imprimir, enlaceNuevo ? 1500 : 100);
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

        /* Actualización automática cada 5 segundos. */

        setInterval(
            sincronizarPanel,
            5000
        );

    }
);
