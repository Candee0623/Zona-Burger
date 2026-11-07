
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
        statusTexto: document.getElementById('hero-status-texto'),
        seccionPromociones: document.getElementById('promociones'),
        listaPromociones: document.getElementById('index-promociones'),
        listaHorarios: document.getElementById('index-horarios'),
        listaZonas: document.getElementById('index-zonas')
    };

    let intervaloId = null;
    let consultaEnCurso = false;
    let erroresConsecutivos = 0;

    /* CREACIÓN SEGURA DE ELEMENTOS */

    function crearElemento(tag, texto, clase = '') {
        const elemento = document.createElement(tag);
        elemento.textContent = texto == null ? '' : String(texto);

        if (clase) {
            elemento.className = clase;
        }

        return elemento;
    }

    function crearIcono(clase) {
        const icono = document.createElement('i');
        icono.className = clase;
        icono.setAttribute('aria-hidden', 'true');
        return icono;
    }

    /* ESTADO DEL LOCAL */

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

        if (elementos.kickerIcono) {
            elementos.kickerIcono.className = 'fa-solid fa-circle';
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

    /* PROMOCIONES */

    function actualizarPromociones(promociones) {
        const contenedor = elementos.listaPromociones;
        const seccion = elementos.seccionPromociones;

        if (!contenedor || !Array.isArray(promociones)) {
            return;
        }

        if (seccion) {
            seccion.hidden = promociones.length === 0;
        }

        const fragmento = document.createDocumentFragment();

        promociones.forEach(promo => {
            const tarjeta = document.createElement('article');
            tarjeta.className = 'promotion-card';
            tarjeta.dataset.promoId = promo.id ?? '';

            const contenido = document.createElement('div');

            const codigo = crearElemento(
                'div',
                promo.palabraclave || '',
                'promotion-code'
            );
            codigo.prepend(crearIcono('fa-solid fa-ticket'));

            contenido.appendChild(codigo);

            contenido.appendChild(
                crearElemento(
                    'h3',
                    promo.descripcion_amigable || ''
                )
            );

            const fecha = crearElemento(
                'div',
                '',
                'promotion-date'
            );

            fecha.appendChild(
                crearIcono('fa-solid fa-calendar-days')
            );

            fecha.appendChild(
                crearElemento(
                    'span',
                    promo.fechafin
                        ? `Válido hasta el ${formatearFecha(promo.fechafin)}`
                        : '¡Tiempo limitado!'
                )
            );

            contenido.appendChild(fecha);
            tarjeta.appendChild(contenido);

            const productosContenedor = crearElemento(
                'div',
                '',
                'promotion-products'
            );

            productosContenedor.appendChild(
                crearElemento(
                    'span',
                    'Productos participantes',
                    'promotion-products-title'
                )
            );

            const etiquetas = crearElemento(
                'div',
                '',
                'promotion-tags'
            );

            if (
                Array.isArray(promo.productos) &&
                promo.productos.length > 0
            ) {
                promo.productos.forEach(producto => {
                    const etiqueta = crearElemento(
                        'span',
                        '',
                        'promotion-tag'
                    );

                    etiqueta.appendChild(
                        crearIcono('fa-solid fa-burger')
                    );

                    etiqueta.appendChild(
                        document.createTextNode(
                            typeof producto === 'string'
                                ? producto
                                : (
                                    producto.nombre ||
                                    producto.nombre_producto ||
                                    producto.producto_nombre ||
                                    producto.producto?.nombre ||
                                    producto.idproducto?.nombre ||
                                    producto.producto ||
                                    'Producto participante'
                                )
                        )
                    );

                    etiquetas.appendChild(etiqueta);
                });
            } else {
                etiquetas.appendChild(
                    crearElemento(
                        'span',
                        'Aplica de forma general en el carrito',
                        'promotion-empty'
                    )
                );
            }

            productosContenedor.appendChild(etiquetas);
            tarjeta.appendChild(productosContenedor);
            fragmento.appendChild(tarjeta);
        });

        contenedor.replaceChildren(fragmento);
    }

    function formatearFecha(fecha) {
        if (!fecha) {
            return '';
        }

        const partes = String(fecha).split('-');

        if (partes.length !== 3) {
            return fecha;
        }

        return `${partes[2]}/${partes[1]}/${partes[0]}`;
    }

    /* HORARIOS */

    function actualizarHorarios(horarios) {
        const contenedor = elementos.listaHorarios;

        if (!contenedor || !Array.isArray(horarios)) {
            return;
        }

        const fragmento = document.createDocumentFragment();

        if (horarios.length === 0) {
            const li = document.createElement('li');

            li.appendChild(
                crearElemento(
                    'span',
                    'No hay horarios configurados.'
                )
            );

            fragmento.appendChild(li);
        } else {
            horarios.forEach(horario => {
                const li = document.createElement('li');

                li.appendChild(
                    crearElemento(
                        'span',
                        horario.diasemana || ''
                    )
                );

                li.appendChild(
                    crearElemento(
                        'span',
                        `${horario.horaapertura || ''} - ${horario.horacierre || ''}`,
                        'info-value'
                    )
                );

                fragmento.appendChild(li);
            });
        }

        contenedor.replaceChildren(fragmento);
    }

    /* ZONAS DE ENTREGA */

    function actualizarZonas(zonas) {
        const contenedor = elementos.listaZonas;

        if (!contenedor || !Array.isArray(zonas)) {
            return;
        }

        const fragmento = document.createDocumentFragment();

        if (zonas.length === 0) {
            const li = document.createElement('li');

            li.appendChild(
                crearElemento(
                    'span',
                    'No hay zonas de entrega configuradas.'
                )
            );

            fragmento.appendChild(li);
        } else {
            zonas.forEach(zona => {
                const li = document.createElement('li');

                li.appendChild(
                    crearElemento('span', zona.nombre || '')
                );

                let costo;

                if (Number(zona.costoenvio) === 0) {
                    costo = 'GRATIS';
                } else if (zona.costoenvio == null) {
                    costo = 'Consultar';
                } else {
                    costo = `$${zona.costoenvio}`;
                }

                li.appendChild(
                    crearElemento('span', costo, 'info-value')
                );

                fragmento.appendChild(li);
            });
        }

        contenedor.replaceChildren(fragmento);
    }

    /* CONSULTA A DJANGO */

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
            actualizarPromociones(data.promociones);
            actualizarHorarios(data.horarios);
            actualizarZonas(data.zonas);

        } catch (error) {
            erroresConsecutivos++;

            if (erroresConsecutivos === 1) {
                console.warn(
                    'No se pudo actualizar la información del local.',
                    error
                );
            }
        } finally {
            consultaEnCurso = false;
        }
    }

    /* ACTUALIZACIÓN PERIÓDICA */

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

    /* GUARDAR Y RECUPERAR SCROLL */

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
                    behavior: 'auto'
                });
            });
        } catch (error) {
            console.warn(
                'No se pudo recuperar la posición de la página.',
                error
            );
        }
    }

    /* CICLO DE VIDA DE LA PESTAÑA */

    document.addEventListener(
        'visibilitychange',
        () => {
            if (document.hidden) {
                detenerActualizacion();
            } else {
                iniciarActualizacion();
            }
        }
    );

    window.addEventListener('pagehide', guardarScroll);

    window.addEventListener('pageshow', () => {
        if (!document.hidden) {
            iniciarActualizacion();
        }
    });

    /* INICIALIZACIÓN */

    recuperarScroll();
    iniciarActualizacion();

})();
