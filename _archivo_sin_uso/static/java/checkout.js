document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    const form = document.querySelector('#checkout-form');

    if (!form) return;

    const $ = (id) => document.getElementById(id);

    const promoInput = $('codigo_promocion');
    const promoButton = $('btn-aplicar-promo');
    const promoStatus = $('promo-status');

    const descuentoRow = $('descuento-row');
    const descuentoValor = $('descuento-valor');

    // Admite los dos IDs usados en las versiones del HTML.
    const totalElement = $('total-estimado') || $('total-final');
    const costoEnvioElement = $('costo-envio');

    const localidadInput = $('input-localidad');
    const localidadHidden = $('localidad');

    const calleInput = $('calle');
    const numeroInput = $('numero');
    const telefonoInput = $('telefono');

    const botonConfirmar = $('btn-confirmar-pedido');
    const textoConfirmar = $('texto-confirmar-pedido');

    const validationSummary = $('validation-summary');
    const validationSummaryList = $('validation-summary-list');

    const mapStatus = $('map-status');

    const subtotal =
        parseFloat('{{ total_carrito|default:"0.00" }}') || 0;

    let descuento =
        parseFloat('{{ descuento_promocion|default:"0.00" }}') || 0;

    // null significa que todavía no se conoce el costo de envío.
    let costoEnvio = null;

    const STORAGE_KEY = 'checkout_datos';
    const tieneDatosPrevios =
        '{{ hay_datos_previos|yesno:"true,false" }}' === 'true';

    const mensajes = {
        nombre: 'Ingresá tu nombre.',
        apellido: 'Ingresá tu apellido.',
        telefono_vacio: 'Ingresá tu número de teléfono.',
        telefono_invalido:
            'Ingresá un teléfono válido (solo números, entre 8 y 15 dígitos).',
        calle: 'Ingresá la calle.',
        numero: 'Ingresá el número de la calle.',
        localidad: 'Ingresá tu localidad.',
        medio_pago: 'Seleccioná un método de pago.'
    };

    const patronTelefono = /^[0-9\s\-()+]{8,15}$/;

    let zonas = [];
    let mapa = null;
    let marcador = null;
    let temporizadorBusqueda = null;

    let negocioAbierto = botonConfirmar
        ? !botonConfirmar.disabled
        : true;

    let consultaEstadoEnCurso = false;

    // --------------------------------------------------
    // ZONAS DE ENVÍO
    // --------------------------------------------------

    try {
        const zonasElement = $('zonas-data');

        if (zonasElement) {
            zonas = JSON.parse(zonasElement.textContent) || [];
        }
    } catch (error) {
        console.error('No se pudieron cargar las zonas:', error);
        zonas = [];
    }

    function normalizarTexto(texto) {
        return String(texto || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim()
            .toLowerCase();
    }

    function aplicarZona(localidad) {
        const localidadBuscada = normalizarTexto(localidad);

        const zona = zonas.find(function (item) {
            return normalizarTexto(item.nombre) === localidadBuscada;
        });

        if (!zona) {
            costoEnvio = null;
            actualizarTotal();
            return;
        }

        costoEnvio = Number(zona.costoenvio);

        if (!Number.isFinite(costoEnvio) || costoEnvio < 0) {
            costoEnvio = null;
        }

        actualizarTotal();
    }

    // --------------------------------------------------
    // TOTAL Y DESCUENTO
    // --------------------------------------------------

    function actualizarTotal() {
        const envioCalculado = costoEnvio === null ? 0 : costoEnvio;

        const total = Math.max(
            0,
            subtotal + envioCalculado - descuento
        );

        if (totalElement) {
            totalElement.textContent = '$' + total.toFixed(2);
        }

        if (costoEnvioElement) {
            if (costoEnvio === null) {
                costoEnvioElement.textContent = 'A coordinar';
            } else if (costoEnvio === 0) {
                costoEnvioElement.textContent = 'Envío gratis';
            } else {
                costoEnvioElement.textContent = '$' + costoEnvio.toFixed(2);
            }
        }

        if (descuentoRow) {
            descuentoRow.style.display = descuento > 0 ? 'flex' : 'none';
        }

        if (descuentoValor) {
            descuentoValor.textContent = '-$' + descuento.toFixed(2);
        }
    }

    // --------------------------------------------------
    // ERRORES DE VALIDACIÓN
    // --------------------------------------------------

    function buscarCampo(nombre) {
        return form.querySelector('[name="' + nombre + '"]');
    }

    function buscarCampoVisible(nombre) {
        if (nombre === 'localidad' && localidadInput) {
            return localidadInput;
        }

        return buscarCampo(nombre);
    }

    function mostrarError(campo, mensaje) {
        const input = buscarCampoVisible(campo);

        if (input) {
            input.classList.add('input-error');
            input.setAttribute('aria-invalid', 'true');
        }

        const errorEl = form.querySelector(
            '.form-error[data-for="' + campo + '"]'
        );

        if (errorEl) {
            errorEl.textContent = mensaje;
            errorEl.style.display = 'block';
            return;
        }

        // También funciona con el HTML que usa .field-error.
        if (input) {
            const grupo = input.closest('.form-group');

            if (grupo) {
                let errorFrontend = grupo.querySelector(
                    '.field-error[data-frontend="true"]'
                );

                if (!errorFrontend) {
                    errorFrontend = document.createElement('div');
                    errorFrontend.className = 'field-error';
                    errorFrontend.dataset.frontend = 'true';
                    grupo.appendChild(errorFrontend);
                }

                errorFrontend.textContent = mensaje;
            }
        }

        // Método de pago: puede no tener un input visible individual.
        if (campo === 'medio_pago') {
            const pagoError = $('payment-required-message');

            if (pagoError) {
                pagoError.classList.remove('hidden');
                pagoError.style.display = 'block';
            }
        }
    }

    function ocultarError(campo) {
        const input = buscarCampoVisible(campo);

        if (input) {
            input.classList.remove('input-error');
            input.removeAttribute('aria-invalid');
        }

        const errorEl = form.querySelector(
            '.form-error[data-for="' + campo + '"]'
        );

        if (errorEl) {
            errorEl.textContent = '';
            errorEl.style.display = 'none';
        }

        if (input) {
            const grupo = input.closest('.form-group');

            if (grupo) {
                grupo.querySelectorAll(
                    '.field-error[data-frontend="true"]'
                ).forEach(function (error) {
                    error.remove();
                });
            }
        }

        if (campo === 'medio_pago') {
            const pagoError = $('payment-required-message');

            if (pagoError) {
                pagoError.classList.add('hidden');
                pagoError.style.display = '';
            }

            form.querySelectorAll('.payment-option').forEach(function (opcion) {
                opcion.classList.remove('payment-error');
            });
        }
    }

    function limpiarTodosLosErrores() {
        [
            'nombre',
            'apellido',
            'telefono',
            'calle',
            'numero',
            'localidad',
            'medio_pago'
        ].forEach(ocultarError);

        if (validationSummary) {
            validationSummary.classList.remove('visible');
        }

        if (validationSummaryList) {
            validationSummaryList.innerHTML = '';
        }
    }

    function mostrarResumenErrores(errores) {
        if (!validationSummary || !validationSummaryList) return;

        validationSummaryList.innerHTML = '';

        errores.forEach(function (error) {
            const li = document.createElement('li');
            li.textContent = error.mensaje;

            li.addEventListener('click', function () {
                if (error.campo) {
                    error.campo.focus();
                    error.campo.scrollIntoView({
                        behavior: 'smooth',
                        block: 'center'
                    });
                }
            });

            validationSummaryList.appendChild(li);
        });

        validationSummary.classList.add('visible');
        validationSummary.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }

    // --------------------------------------------------
    // GUARDAR Y RECUPERAR DATOS
    // --------------------------------------------------

    function guardarCheckout() {
        try {
            const datos = {};

            form.querySelectorAll('input, select, textarea').forEach(
                function (elemento) {
                    if (
                        !elemento.name ||
                        elemento.name === 'csrfmiddlewaretoken'
                    ) {
                        return;
                    }

                    if (
                        elemento.type === 'radio' ||
                        elemento.type === 'checkbox'
                    ) {
                        if (elemento.checked) {
                            datos[elemento.name] = elemento.value;
                        }
                    } else {
                        datos[elemento.name] = elemento.value;
                    }
                }
            );

            localStorage.setItem(STORAGE_KEY, JSON.stringify(datos));
        } catch (error) {
            console.error('No se pudieron guardar los datos:', error);
        }
    }

    function cargarCheckout() {
        // Si Django ya renderizó datos previos, no los sobrescribimos.
        if (tieneDatosPrevios) return;

        try {
            const datosGuardados = localStorage.getItem(STORAGE_KEY);

            if (!datosGuardados) return;

            const datos = JSON.parse(datosGuardados);

            Object.keys(datos).forEach(function (nombre) {
                const elementos = form.querySelectorAll(
                    '[name="' + nombre + '"]'
                );

                elementos.forEach(function (elemento) {
                    if (
                        elemento.type === 'radio' ||
                        elemento.type === 'checkbox'
                    ) {
                        elemento.checked =
                            elemento.value === String(datos[nombre]);
                    } else {
                        elemento.value = datos[nombre] ?? '';
                    }
                });
            });

            // Sincronizar el campo visible y el campo enviado a Django.
            if (localidadInput && localidadHidden) {
                localidadHidden.value = localidadInput.value;
                aplicarZona(localidadInput.value);
            }

            const aviso = $('restore-notice');

            if (aviso) {
                aviso.classList.add('visible');
            }

            actualizarTotal();
        } catch (error) {
            console.error('No se pudieron cargar los datos:', error);
        }
    }

    const limpiarDatosButton = $('clear-saved-data');

    if (limpiarDatosButton) {
        limpiarDatosButton.addEventListener('click', function () {
            try {
                localStorage.removeItem(STORAGE_KEY);
            } catch (error) {
                console.error(error);
            }

            form.reset();

            if (localidadHidden) {
                localidadHidden.value = '';
            }

            descuento = 0;
            costoEnvio = null;

            const aviso = $('restore-notice');

            if (aviso) {
                aviso.classList.remove('visible');
            }

            if (promoStatus) {
                promoStatus.textContent = '';
            }

            limpiarTodosLosErrores();
            actualizarTotal();
        });
    }

    // --------------------------------------------------
    // MAPA Y COORDENADAS
    // --------------------------------------------------

    const mapElement = $('map');
    const latitudInput = $('latitud');
    const longitudInput = $('longitud');

    if (mapElement && typeof L !== 'undefined') {
        let lat = latitudInput
            ? parseFloat(latitudInput.value)
            : NaN;

        let lng = longitudInput
            ? parseFloat(longitudInput.value)
            : NaN;

        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
            lat = -34.6037;
            lng = -58.3816;
        }

        mapa = L.map('map').setView([lat, lng], 13);

        L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }
        ).addTo(mapa);

        marcador = L.marker(
            [lat, lng],
            { draggable: true }
        ).addTo(mapa);

        function actualizarUbicacion(posicion) {
            if (latitudInput) {
                latitudInput.value = posicion.lat;
            }

            if (longitudInput) {
                longitudInput.value = posicion.lng;
            }

            guardarCheckout();
        }

        marcador.on('dragend', function (evento) {
            actualizarUbicacion(evento.target.getLatLng());
        });

        mapa.on('click', function (evento) {
            marcador.setLatLng(evento.latlng);
            actualizarUbicacion(evento.latlng);
        });

        setTimeout(function () {
            mapa.invalidateSize();
        }, 300);
    }

    async function buscarDireccion(direccion) {
        if (!mapa || !marcador || !direccion.trim()) return;

        if (mapStatus) {
            mapStatus.textContent = 'Buscando ubicación...';
        }

        try {
            const url = 'https://nominatim.openstreetmap.org/search?' +
                new URLSearchParams({
                    format: 'json',
                    addressdetails: '1',
                    limit: '1',
                    q: direccion,
                    'accept-language': 'es'
                });

            const respuesta = await fetch(url);

            if (!respuesta.ok) {
                throw new Error('Error al buscar la dirección');
            }

            const resultados = await respuesta.json();

            if (!resultados.length) {
                if (mapStatus) {
                    mapStatus.textContent = 'No se encontró esa dirección.';
                }
                return;
            }

            const lat = Number(resultados[0].lat);
            const lng = Number(resultados[0].lon);

            const posicion = L.latLng(lat, lng);

            mapa.setView(posicion, 17);
            marcador.setLatLng(posicion);

            actualizarCoordenadas(posicion);
            await obtenerDireccionDesdeCoordenadas(lat, lng);

            if (mapStatus) {
                mapStatus.textContent = 'Ubicación encontrada.';
            }
        } catch (error) {
            console.error(error);

            if (mapStatus) {
                mapStatus.textContent = 'No se pudo buscar la dirección.';
            }
        }
    }

    function actualizarCoordenadas(posicion) {
        if (latitudInput) {
            latitudInput.value = posicion.lat;
        }

        if (longitudInput) {
            longitudInput.value = posicion.lng;
        }

        guardarCheckout();
    }

    async function obtenerDireccionDesdeCoordenadas(lat, lng) {
        try {
            const url = 'https://nominatim.openstreetmap.org/reverse?' +
                new URLSearchParams({
                    format: 'json',
                    lat: String(lat),
                    lon: String(lng),
                    addressdetails: '1',
                    'accept-language': 'es'
                });

            const respuesta = await fetch(url);

            if (!respuesta.ok) {
                throw new Error('Error al obtener la dirección');
            }

            const resultado = await respuesta.json();
            const direccion = resultado.address || {};

            const calle = direccion.road ||
                direccion.pedestrian ||
                direccion.residential ||
                '';

            const numero = direccion.house_number || '';

            const localidad = direccion.suburb ||
                direccion.city_district ||
                direccion.city ||
                direccion.town ||
                direccion.village ||
                '';

            if (calleInput && calle) {
                calleInput.value = calle;
            }

            if (numeroInput && numero) {
                numeroInput.value = numero;
            }

            if (localidadInput && localidad) {
                localidadInput.value = localidad;
            }

            if (localidadHidden && localidadInput) {
                localidadHidden.value = localidadInput.value;
                aplicarZona(localidadHidden.value);
            }

            guardarCheckout();
        } catch (error) {
            console.error(error);

            if (mapStatus) {
                mapStatus.textContent =
                    'No se pudo obtener la dirección de ese punto.';
            }
        }
    }

    if (calleInput && numeroInput) {
        function programarBusquedaDireccion() {
            clearTimeout(temporizadorBusqueda);

            if (
                !calleInput.value.trim() ||
                !numeroInput.value.trim()
            ) {
                return;
            }

            temporizadorBusqueda = setTimeout(function () {
                buscarDireccion(
                    calleInput.value.trim() + ' ' +
                    numeroInput.value.trim() +
                    ', Buenos Aires, Argentina'
                );
            }, 1000);
        }

        calleInput.addEventListener('change', programarBusquedaDireccion);
        numeroInput.addEventListener('change', programarBusquedaDireccion);
    }

    if (localidadInput) {
        localidadInput.addEventListener('input', function () {
            if (localidadHidden) {
                localidadHidden.value = localidadInput.value;
            }

            aplicarZona(localidadInput.value);
            guardarCheckout();
        });

        localidadInput.addEventListener('change', function () {
            if (localidadHidden) {
                localidadHidden.value = localidadInput.value;
            }

            aplicarZona(localidadInput.value);
            guardarCheckout();
        });
    }

    const botonUbicacion = $('btn-ubicacion');

    if (botonUbicacion) {
        botonUbicacion.addEventListener('click', function () {
            if (!navigator.geolocation) {
                if (mapStatus) {
                    mapStatus.textContent =
                        'Tu navegador no permite obtener la ubicación.';
                }
                return;
            }

            if (mapStatus) {
                mapStatus.textContent = 'Obteniendo tu ubicación...';
            }

            navigator.geolocation.getCurrentPosition(
                function (posicion) {
                    const lat = posicion.coords.latitude;
                    const lng = posicion.coords.longitude;

                    if (mapa && marcador) {
                        const punto = L.latLng(lat, lng);

                        mapa.setView(punto, 17);
                        marcador.setLatLng(punto);
                        actualizarCoordenadas(punto);
                    }

                    obtenerDireccionDesdeCoordenadas(lat, lng);
                },
                function () {
                    if (mapStatus) {
                        mapStatus.textContent =
                            'No se pudo obtener tu ubicación. Revisá los permisos del navegador.';
                    }
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }

    // --------------------------------------------------
    // APLICAR PROMOCIÓN
    // --------------------------------------------------

    if (promoButton && promoInput) {
        promoButton.addEventListener('click', async function () {
            const codigo = promoInput.value.trim().toUpperCase();

            if (!codigo) {
                descuento = 0;

                if (promoStatus) {
                    promoStatus.textContent = 'Ingresá una palabra clave.';
                }

                actualizarTotal();
                guardarCheckout();
                return;
            }

            promoInput.value = codigo;
            promoButton.disabled = true;

            if (promoStatus) {
                promoStatus.textContent = 'Verificando promoción...';
            }

            try {
                const csrfInput = form.querySelector(
                    '[name="csrfmiddlewaretoken"]'
                );

                if (!csrfInput) {
                    throw new Error('No se encontró el token CSRF.');
                }

                const respuesta = await fetch(
                    "{% url 'aplicar_promocion' %}",
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type':
                                'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-CSRFToken': csrfInput.value,
                            'X-Requested-With': 'XMLHttpRequest'
                        },
                        body: new URLSearchParams({
                            codigo_promocion: codigo
                        })
                    }
                );

                const datos = await respuesta.json();

                if (!respuesta.ok || !datos.ok) {
                    descuento = 0;

                    if (promoStatus) {
                        promoStatus.textContent =
                            datos.mensaje ||
                            'La promoción no se puede aplicar.';
                    }
                } else {
                    descuento = Math.max(
                        0,
                        Number(datos.descuento) || 0
                    );

                    if (promoStatus) {
                        promoStatus.textContent =
                            datos.mensaje ||
                            'Promoción aplicada correctamente.';
                    }
                }

                actualizarTotal();
                guardarCheckout();
            } catch (error) {
                console.error('Error al aplicar promoción:', error);

                descuento = 0;

                if (promoStatus) {
                    promoStatus.textContent =
                        'No se pudo verificar la promoción.';
                }

                actualizarTotal();
            } finally {
                promoButton.disabled = false;
            }
        });
    }

    // --------------------------------------------------
    // VALIDAR FORMULARIO
    // --------------------------------------------------

    function validarCheckout() {
        limpiarTodosLosErrores();

        let esValido = true;
        let primerCampoInvalido = null;

        const errores = [];

        function registrarError(campo, mensaje) {
            mostrarError(campo, mensaje);

            errores.push({
                campo: buscarCampoVisible(campo),
                mensaje: mensaje
            });

            esValido = false;

            if (!primerCampoInvalido) {
                primerCampoInvalido = buscarCampoVisible(campo);
            }
        }

        ['nombre', 'apellido'].forEach(function (campo) {
            const input = buscarCampo(campo);

            if (!input) return;

            if (!input.value.trim()) {
                registrarError(campo, mensajes[campo]);
            }
        });

        if (telefonoInput) {
            const telefonoValor = telefonoInput.value.trim();

            if (!telefonoValor) {
                registrarError('telefono', mensajes.telefono_vacio);
            } else if (!patronTelefono.test(telefonoValor)) {
                registrarError('telefono', mensajes.telefono_invalido);
            }
        }

        ['calle', 'numero'].forEach(function (campo) {
            const input = buscarCampo(campo);

            if (input && !input.value.trim()) {
                registrarError(campo, mensajes[campo]);
            }
        });

        const localidadValor = localidadHidden
            ? localidadHidden.value.trim()
            : localidadInput
                ? localidadInput.value.trim()
                : '';

        if (!localidadValor) {
            registrarError('localidad', mensajes.localidad);
        }

        const medioPago = form.querySelector(
            '[name="medio_pago"]:checked'
        );

        if (!medioPago) {
            registrarError('medio_pago', mensajes.medio_pago);

            form.querySelectorAll('.payment-option').forEach(
                function (opcion) {
                    opcion.classList.add('payment-error');
                }
            );
        }

        if (!esValido) {
            mostrarResumenErrores(errores);

            if (primerCampoInvalido) {
                primerCampoInvalido.focus({ preventScroll: true });
                primerCampoInvalido.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
            }

            return false;
        }

        return true;
    }

    form.querySelectorAll('input, select, textarea').forEach(
        function (elemento) {
            elemento.addEventListener('input', function () {
                if (elemento.name) {
                    ocultarError(elemento.name);
                }
            });

            elemento.addEventListener('change', function () {
                if (elemento.name) {
                    ocultarError(elemento.name);
                }
            });
        }
    );

    form.addEventListener('submit', function (evento) {
        // Evita enviar el pedido desde la interfaz cuando está cerrado.
        if (!negocioAbierto) {
            evento.preventDefault();
            consultarEstadoNegocio();
            return;
        }

        if (localidadHidden && localidadInput) {
            localidadHidden.value = localidadInput.value.trim();
        }

        if (!validarCheckout()) {
            evento.preventDefault();
            return;
        }

        guardarCheckout();

        if (botonConfirmar) {
            botonConfirmar.disabled = true;

            if (textoConfirmar) {
                textoConfirmar.textContent = 'Procesando pedido...';
            }
        }
    });

    // --------------------------------------------------
    // ESTADO DEL NEGOCIO
    // --------------------------------------------------

    function actualizarEstadoNegocio(abierto, mensaje) {
        negocioAbierto = abierto;

        if (botonConfirmar) {
            botonConfirmar.disabled = !abierto;
            botonConfirmar.setAttribute(
                'aria-disabled',
                String(!abierto)
            );

            botonConfirmar.title = abierto
                ? ''
                : 'El negocio está cerrado en este momento';

            botonConfirmar.style.opacity = abierto ? '' : '.55';
            botonConfirmar.style.cursor = abierto ? '' : 'not-allowed';
        }

        if (textoConfirmar) {
            textoConfirmar.textContent = abierto
                ? 'Confirmar pedido'
                : 'Negocio cerrado';
        }

        let aviso = $('aviso-negocio-cerrado');

        if (!abierto && !aviso) {
            aviso = document.createElement('div');
            aviso.id = 'aviso-negocio-cerrado';
            aviso.setAttribute('role', 'alert');
            aviso.setAttribute('aria-live', 'polite');

            aviso.style.cssText =
                'display:flex;align-items:flex-start;gap:12px;' +
                'padding:16px;border-radius:10px;margin-bottom:20px;' +
                'background:rgba(220,38,38,.15);' +
                'border:1px solid rgba(220,38,38,.45);color:#fca5a5;';

            const icono = document.createElement('i');
            icono.className = 'fa-solid fa-clock';
            icono.setAttribute('aria-hidden', 'true');

            const contenido = document.createElement('div');

            const titulo = document.createElement('strong');
            titulo.textContent =
                'El negocio está cerrado en este momento.';
            titulo.style.cssText =
                'display:block;color:#fff;margin-bottom:4px;';

            const detalle = document.createElement('span');
            detalle.id = 'mensaje-cierre-checkout';
            detalle.style.cssText =
                'font-size:.9rem;color:#d1d5db;';

            contenido.append(titulo, detalle);
            aviso.append(icono, contenido);

            const tituloCheckout = document.querySelector('.checkout-title');

            if (tituloCheckout) {
                tituloCheckout.insertAdjacentElement('afterend', aviso);
            }
        }

        if (abierto && aviso) {
            aviso.remove();
        } else if (!abierto && aviso) {
            const detalle = $('mensaje-cierre-checkout');

            if (detalle) {
                detalle.textContent = mensaje ||
                    'Podrás confirmar tu pedido cuando vuelva a abrir.';
            }
        }
    }

    async function consultarEstadoNegocio() {
        if (consultaEstadoEnCurso || document.hidden) return;

        consultaEstadoEnCurso = true;

        try {
            const respuesta = await fetch(form.action, {
                method: 'GET',
                cache: 'no-store',
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const datos = await respuesta.json();

            if (respuesta.status === 403 && datos.cerrado === true) {
                actualizarEstadoNegocio(false, datos.mensaje);
                return;
            }

            if (respuesta.ok && datos.status === 'success') {
                actualizarEstadoNegocio(true, '');
            }
        } catch (error) {
            console.error(
                'No se pudo consultar el estado del negocio:',
                error
            );
        } finally {
            consultaEstadoEnCurso = false;
        }
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) {
            consultarEstadoNegocio();
        }
    });

    // --------------------------------------------------
    // INICIALIZACIÓN
    // --------------------------------------------------

    cargarCheckout();

    if (localidadInput && localidadHidden) {
        localidadHidden.value = localidadInput.value;
        aplicarZona(localidadInput.value);
    }

    actualizarTotal();
    consultarEstadoNegocio();

    // Consultar cada 15 segundos si el negocio abrió o cerró.
    window.setInterval(consultarEstadoNegocio, 15000);
});