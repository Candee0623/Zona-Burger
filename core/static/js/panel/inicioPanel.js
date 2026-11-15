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

/* AVISOS (toast y diálogo) */

function zbToastPanel(texto, enlace) {

    let cont = document.getElementById('zb-toasts-panel');

    if (!cont) {
        cont = document.createElement('div');
        cont.id = 'zb-toasts-panel';
        cont.className = 'zb-toasts-panel';
        cont.setAttribute('aria-live', 'polite');
        document.body.appendChild(cont);
    }

    const toast = document.createElement('div');
    toast.className = 'zb-toast-panel';

    const span = document.createElement('span');
    span.textContent = texto;
    toast.appendChild(span);

    if (enlace && enlace.href) {
        const a = document.createElement('a');
        a.href = enlace.href;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = enlace.texto || 'Abrir';
        toast.appendChild(a);
    }

    cont.appendChild(toast);

    setTimeout(function () {
        toast.classList.add('saliendo');
        setTimeout(function () {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, enlace ? 12000 : 4000);
}

function zbAvisoPanel(nivel, texto) {

    // Un aviso en el borde superior no se ve si la persona está más abajo en
    // la lista: lo exitoso va en un cartel pequeño y lo que requiere
    // atención en un diálogo.
    if (nivel === 'success') {
        zbToastPanel(texto);
        return;
    }

    if (window.ZB && typeof ZB.avisar === 'function') {
        ZB.avisar({
            titulo: nivel === 'warning' ? 'Atención' : 'No se pudo completar',
            mensaje: texto,
            tipo: nivel === 'warning' ? 'info' : 'peligro'
        });
    } else {
        zbToastPanel(texto);
    }
}

/* ACTUALIZACIÓN AUTOMÁTICA SIN MOVER LA PANTALLA */

(function actualizacionDelPanel() {

    const BLOQUES = ['metricas-panel', 'estados-panel', 'pedidos-panel'];
    const INTERVALO_MS = 5000;

    let sincronizando = false;
    let repetir = false;

    // Sube cada vez que la persona cambia algo (pago o estado): una
    // respuesta de refresco pedida ANTES del cambio ya está vieja y no
    // debe pisar lo nuevo.
    let generacion = 0;

    function indicador() {
        return document.getElementById('panel-sync-indicator');
    }

    function ponerIndicador(texto, actualizando) {

        const el = indicador();

        if (!el) {
            return;
        }

        el.innerHTML =
            '<span class="panel-sync-dot"></span>' +
            '<span>' + texto + '</span>';

        el.classList.toggle('actualizando', !!actualizando);
    }

    /* Cada fila lleva un token CSRF que cambia en CADA respuesta del
       servidor. Si se compara tal cual, el panel siempre "parece"
       distinto y se redibuja entero cada 5 segundos (y la tabla pierde su
       posición). Se compara sin esos valores. */

    function firma(html) {
        return html.replace(
            /(name="csrfmiddlewaretoken"\s+value=")[^"]*"/g,
            '$1"'
        );
    }

    function contenedorPrincipal() {
        return document.querySelector('.main-content');
    }

    /* El que se desplaza en este diseño es .main-content (no la ventana) y,
       además, la tabla tiene su propio scroll horizontal. Todo eso se
       guarda antes de redibujar y se devuelve en el mismo instante, antes
       de que el navegador pinte, así no se ve ningún salto. */

    function capturarPosiciones() {

        const posiciones = {
            ventana: [window.scrollX, window.scrollY],
            ancestros: [],
            internos: []
        };

        let el = document.getElementById('pedidos-panel');

        while (el && el !== document.documentElement) {
            posiciones.ancestros.push([el, el.scrollLeft, el.scrollTop]);
            el = el.parentElement;
        }

        BLOQUES.forEach(function (id) {

            const bloque = document.getElementById(id);

            if (!bloque) {
                return;
            }

            // El propio bloque puede tener scroll (p. ej. los filtros en
            // pantallas chicas).
            posiciones.ancestros.push([bloque, bloque.scrollLeft, bloque.scrollTop]);

            const nodos = bloque.getElementsByTagName('*');

            for (let i = 0; i < nodos.length; i++) {
                if (nodos[i].scrollLeft || nodos[i].scrollTop) {
                    posiciones.internos.push(
                        [id, i, nodos[i].scrollLeft, nodos[i].scrollTop]
                    );
                }
            }
        });

        return posiciones;
    }

    function restaurarPosiciones(posiciones) {

        posiciones.internos.forEach(function (dato) {

            const bloque = document.getElementById(dato[0]);
            const nodo = bloque
                ? bloque.getElementsByTagName('*')[dato[1]]
                : null;

            if (nodo) {
                nodo.scrollLeft = dato[2];
                nodo.scrollTop = dato[3];
            }
        });

        posiciones.ancestros.forEach(function (dato) {
            dato[0].scrollLeft = dato[1];
            dato[0].scrollTop = dato[2];
        });

        window.scrollTo({
            left: posiciones.ventana[0],
            top: posiciones.ventana[1],
            behavior: 'instant'
        });
    }

    function aplicarBloques(documento) {

        const nuevos = [];

        for (let i = 0; i < BLOQUES.length; i++) {

            const actual = document.getElementById(BLOQUES[i]);
            const nuevo = documento.getElementById(BLOQUES[i]);

            if (!actual || !nuevo) {
                console.warn('La respuesta no contiene los bloques esperados.');
                return;
            }

            if (firma(actual.innerHTML) !== firma(nuevo.innerHTML)) {
                nuevos.push([actual, nuevo]);
            }
        }

        // Nada cambió: no se toca el DOM (ni se mueve nada).
        if (!nuevos.length) {
            return;
        }

        const posiciones = capturarPosiciones();

        nuevos.forEach(function (par) {
            par[0].innerHTML = par[1].innerHTML;
        });

        restaurarPosiciones(posiciones);
    }

    async function sincronizarPanel() {

        if (sincronizando) {
            repetir = true;
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
        repetir = false;

        const miGeneracion = generacion;

        try {

            ponerIndicador('Actualizando...', true);

            const response = await fetch(window.location.href, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Cache-Control': 'no-cache'
                },
                cache: 'no-store',
                credentials: 'same-origin'
            });

            if (response.status === 401) {
                ponerIndicador('Sesión vencida', false);
                return;
            }

            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }

            const html = await response.text();

            // La persona cambió algo mientras llegaba esta respuesta: se
            // descarta y se pide una nueva.
            if (miGeneracion !== generacion) {
                repetir = true;
                return;
            }

            const documento = new DOMParser().parseFromString(html, 'text/html');

            aplicarBloques(documento);

            ponerIndicador('Sincronizado', false);

        } catch (error) {

            console.error('Error actualizando panel:', error);

            ponerIndicador('Sin conexión', false);

        } finally {

            sincronizando = false;

            const el = indicador();

            if (el) {
                el.classList.remove('actualizando');
            }

            if (repetir) {
                repetir = false;
                sincronizarPanel();
            }
        }
    }

    window.ZBPanelSync = {
        sincronizar: sincronizarPanel,
        cambioLocal: function () {
            generacion++;
        }
    };

    document.addEventListener('DOMContentLoaded', function () {

        /* Primera sincronización. */

        sincronizarPanel();

        /* Si entra un pedido nuevo, se actualiza la lista enseguida
           (el aviso con sonido lo da NotificacionPedidos.js). */

        document.addEventListener('zb:pedido-nuevo', function () {
            sincronizarPanel();
        });

        /* Al volver a esta pestaña se actualiza sin esperar. */

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) {
                sincronizarPanel();
            }
        });

        /* Actualización automática cada 5 segundos. */

        setInterval(sincronizarPanel, INTERVALO_MS);
    });

})();

/* PAGADO / CAMBIAR ESTADO SIN RECARGAR LA PÁGINA */

/* Antes estos formularios recargaban todo el panel y lo dejaban arriba.
   Ahora se envían en segundo plano y solo se actualiza lo que cambió, así
   la pantalla queda exactamente donde estaba. */

(function accionesSinRecargar() {

    async function enviar(form) {

        const respuesta = await fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            },
            credentials: 'same-origin'
        });

        let datos = null;

        try {
            datos = await respuesta.json();
        } catch (error) {
            datos = null;
        }

        if (respuesta.status === 401) {
            return {
                ok: false,
                nivel: 'error',
                mensaje: 'Tu sesión expiró. Volvé a iniciar sesión.'
            };
        }

        if (!respuesta.ok || !datos) {
            return {
                ok: false,
                nivel: 'error',
                mensaje: (datos && datos.message) ||
                    'No se pudo completar la acción. Intentá de nuevo.'
            };
        }

        return { ok: true, datos: datos };
    }

    function bloquear(form, bloqueado) {

        const botones = form.querySelectorAll('button[type="submit"]');

        botones.forEach(function (boton) {
            boton.disabled = bloqueado;
        });
    }

    function refrescar() {
        window.ZBPanelSync.cambioLocal();
        window.ZBPanelSync.sincronizar();
    }

    document.addEventListener('submit', async function (event) {

        const form = event.target;

        if (!form || !form.matches) {
            return;
        }

        const esPago = form.matches('form[action*="toggle-pagado"]');
        const esEstado = form.id === 'formCambiarEstado';

        if (!esPago && !esEstado) {
            return;
        }

        event.preventDefault();

        if (form.dataset.enviando === '1') {
            return;
        }

        form.dataset.enviando = '1';
        bloquear(form, true);

        try {

            const resultado = await enviar(form);

            if (!resultado.ok) {
                zbAvisoPanel(resultado.nivel, resultado.mensaje);
                return;
            }

            const datos = resultado.datos;

            if (esPago) {

                if (datos.success === false) {
                    zbAvisoPanel('error', datos.message || 'No se pudo actualizar el pago.');
                    return;
                }

                refrescar();
                return;
            }

            /* Cambio de estado. */

            if (!datos.success) {
                // El servidor explica por qué no se pudo (otro empleado
                // ya lo cambió, transición no permitida, falta motivo...).
                zbAvisoPanel(datos.level || 'error', datos.message);
                refrescar();
                return;
            }

            cerrarEstadoModal();
            refrescar();

            if (datos.wa_url) {

                const ventana = window.open(datos.wa_url, '_blank');

                if (!ventana) {
                    // El navegador bloqueó la ventana emergente.
                    zbToastPanel(
                        datos.message,
                        { href: datos.wa_url, texto: 'Abrir WhatsApp' }
                    );
                    return;
                }
            }

            zbAvisoPanel('success', datos.message);

        } catch (error) {

            console.error('Error enviando la acción del panel:', error);

            zbAvisoPanel(
                'error',
                'No se pudo conectar con el servidor. Revisá tu conexión e intentá de nuevo.'
            );

        } finally {

            delete form.dataset.enviando;
            bloquear(form, false);
        }
    });

})();
