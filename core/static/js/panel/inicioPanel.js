/* =========================================================
   MODAL TICKET
========================================================= */

function abrirTicketModal(url) {

    const overlay =
        document.getElementById(
            'modalTicketOverlay'
        );

    const contenido =
        document.getElementById(
            'contenido-ticket-modal'
        );

    overlay.classList.add('active');

    contenido.innerHTML =
        '<div style="text-align:center;padding:30px;color:#666;">' +
        '<div style="margin-bottom:8px;">Cargando ticket...</div>' +
        '</div>';

    fetch(
        url,
        {
            method: 'GET',

            headers: {
                'X-Requested-With':
                    'XMLHttpRequest'
            },

            cache: 'no-store'
        }
    )
    .then(
        response => {

            if (!response.ok) {

                throw new Error(
                    'HTTP ' +
                    response.status
                );

            }

            return response.text();

        }
    )
    .then(
        html => {

            contenido.innerHTML =
                html;

        }
    )
    .catch(
        error => {

            console.error(
                'Error cargando ticket:',
                error
            );

            contenido.innerHTML =
                '<div style="text-align:center;color:#dc3545;padding:25px;">' +
                'No se pudo cargar el ticket.' +
                '</div>';

        }
    );

}


function cerrarTicketModal() {

    document
        .getElementById(
            'modalTicketOverlay'
        )
        .classList.remove(
            'active'
        );

}


function imprimirModal() {

    const contenido =
        document.getElementById(
            'contenido-ticket-modal'
        ).innerHTML;

    const ventana =
        window.open(
            '',
            '_blank',
            'height=700,width=450'
        );

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
        '<html>' +
        '<head>' +
        '<title>Ticket</title>' +
        '<style>' +
        'body{' +
        'margin:0;' +
        'padding:5px;' +
        'font-family:"Courier New",Courier,monospace;' +
        '}' +
        '</style>' +
        '</head>' +
        '<body>' +
        contenido +
        '</body>' +
        '</html>'
    );

    ventana.document.close();

    ventana.focus();

    setTimeout(
        function () {

            ventana.print();

            ventana.close();

        },
        300
    );

}


/* =========================================================
   MODAL CAMBIAR ESTADO
========================================================= */

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


/* =========================================================
   CERRAR MODALES
========================================================= */

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


/* =========================================================
   WHATSAPP
========================================================= */

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


/* =========================================================
   ACTUALIZACIÓN AUTOMÁTICA
========================================================= */

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


        /*
         * Primera sincronización.
         */

        sincronizarPanel();


        /*
         * Actualización automática cada 2 segundos.
         */

        setInterval(
            sincronizarPanel,
            2000
        );

    }
);
