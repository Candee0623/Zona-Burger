document.addEventListener('DOMContentLoaded', function () {

    const form = document.querySelector('#checkout-form');

    if (!form) {
        return;
    }

    const promoInput =
        document.getElementById('codigo_promocion');

    const promoButton =
        document.getElementById('btn-aplicar-promo');

    const promoStatus =
        document.getElementById('promo-status');

    const descuentoRow =
        document.getElementById('descuento-row');

    const descuentoValor =
        document.getElementById('descuento-valor');

    const totalElement =
        document.getElementById('total-final');

    const costoEnvioElement =
        document.getElementById('costo-envio');


    const subtotal =
        parseFloat(
            '{{ total_carrito|floatformat:"2" }}'
        ) || 0;

    let descuento =
        parseFloat(
            '{{ descuento_promocion|default:"0.00" }}'
        ) || 0;

    let costoEnvio = 0;


    const mensajes = {
        nombre: 'Ingresá tu nombre.',
        apellido: 'Ingresá tu apellido.',
        telefono_vacio: 'Ingresá tu número de teléfono.',
        telefono_invalido: 'Ingresá un teléfono válido (solo números, entre 8 y 15 dígitos).',
        calle: 'Ingresá la calle.',
        numero: 'Ingresá el número de la calle.',
        localidad: 'Ingresá tu localidad.',
        medio_pago: 'Seleccioná un método de pago.'
    };


    const patronTelefono =
        /^[0-9\s\-()+]{8,15}$/;


    function mostrarError(campo, mensaje) {

        const errorEl =
            form.querySelector(
                `.form-error[data-for="${campo}"]`
            );

        if (errorEl) {

            errorEl.textContent =
                mensaje;

            errorEl.style.display =
                'block';

        }


        const inputEl =
            form.querySelector(
                `[name="${campo}"]`
            );

        if (inputEl) {

            inputEl.classList.add(
                'input-error'
            );

        }

    }


    function ocultarError(campo) {

        const errorEl =
            form.querySelector(
                `.form-error[data-for="${campo}"]`
            );

        if (errorEl) {

            errorEl.textContent =
                '';

            errorEl.style.display =
                'none';

        }


        const inputEl =
            form.querySelector(
                `[name="${campo}"]`
            );

        if (inputEl) {

            inputEl.classList.remove(
                'input-error'
            );

        }

    }


    function actualizarTotal() {

        const total =
            Math.max(
                0,
                subtotal +
                costoEnvio -
                descuento
            );


        if (totalElement) {

            totalElement.textContent =
                '$' +
                total.toFixed(2);

        }


        if (costoEnvioElement) {

            if (costoEnvio === 0) {

                costoEnvioElement.textContent =
                    'Envío gratis';

            } else {

                costoEnvioElement.textContent =
                    '$' +
                    costoEnvio.toFixed(2);

            }

        }


        if (
            descuento > 0 &&
            descuentoRow
        ) {

            descuentoRow.style.display =
                'flex';

        } else if (descuentoRow) {

            descuentoRow.style.display =
                'none';

        }


        if (descuentoValor) {

            descuentoValor.textContent =
                '-$' +
                descuento.toFixed(2);

        }

    }


    function guardarCheckout() {

        try {

            const datos = {};

            form.querySelectorAll(
                'input, select, textarea'
            ).forEach(function (elemento) {

                if (
                    elemento.name &&
                    elemento.name !== 'csrfmiddlewaretoken'
                ) {

                    if (
                        elemento.type === 'radio' ||
                        elemento.type === 'checkbox'
                    ) {

                        if (elemento.checked) {

                            datos[elemento.name] =
                                elemento.value;

                        }

                    } else {

                        datos[elemento.name] =
                            elemento.value;

                    }

                }

            });


            localStorage.setItem(
                'checkout_datos',
                JSON.stringify(datos)
            );

        } catch (error) {

            console.error(
                'No se pudieron guardar los datos:',
                error
            );

        }

    }


    function cargarCheckout() {

        try {

            const datosGuardados =
                localStorage.getItem(
                    'checkout_datos'
                );

            if (!datosGuardados) {
                return;
            }


            const datos =
                JSON.parse(datosGuardados);


            Object.keys(datos).forEach(
                function (nombre) {

                    const elementos =
                        form.querySelectorAll(
                            `[name="${nombre}"]`
                        );

                    if (!elementos.length) {
                        return;
                    }


                    elementos.forEach(
                        function (elemento) {

                            if (
                                elemento.type === 'radio' ||
                                elemento.type === 'checkbox'
                            ) {

                                elemento.checked =
                                    elemento.value ===
                                    datos[nombre];

                            } else {

                                elemento.value =
                                    datos[nombre];

                            }

                        }
                    );

                }
            );

        } catch (error) {

            console.error(
                'No se pudieron cargar los datos:',
                error
            );

        }

    }


    cargarCheckout();


    const mapElement =
        document.getElementById('map');


    if (
        mapElement &&
        typeof L !== 'undefined'
    ) {

        const latitudInput =
            document.getElementById('latitud');

        const longitudInput =
            document.getElementById('longitud');


        let lat =
            parseFloat(
                latitudInput.value
            );

        let lng =
            parseFloat(
                longitudInput.value
            );


        if (
            isNaN(lat) ||
            isNaN(lng)
        ) {

            lat = -34.6037;
            lng = -58.3816;

        }


        const map =
            L.map('map').setView(
                [lat, lng],
                13
            );


        L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            {
                maxZoom: 19,
                attribution:
                    '&copy; OpenStreetMap'
            }
        ).addTo(map);


        let marcador =
            L.marker(
                [lat, lng],
                {
                    draggable: true
                }
            ).addTo(map);


        function actualizarUbicacion(
            posicion
        ) {

            latitudInput.value =
                posicion.lat;

            longitudInput.value =
                posicion.lng;

            guardarCheckout();

        }


        marcador.on(
            'dragend',
            function (evento) {

                actualizarUbicacion(
                    evento.target.getLatLng()
                );

            }
        );


        map.on(
            'click',
            function (evento) {

                marcador.setLatLng(
                    evento.latlng
                );

                actualizarUbicacion(
                    evento.latlng
                );

            }
        );

    }


    if (promoButton) {

        promoButton.addEventListener(
            'click',
            async function () {

                const codigo =
                    promoInput.value
                        .trim()
                        .toUpperCase();


                if (!codigo) {

                    descuento = 0;

                    promoStatus.textContent =
                        'Ingresá una palabra clave.';

                    actualizarTotal();

                    return;

                }


                promoInput.value =
                    codigo;


                promoButton.disabled =
                    true;


                promoStatus.textContent =
                    'Verificando promoción...';


                try {

                    const csrfToken =
                        form.querySelector(
                            '[name="csrfmiddlewaretoken"]'
                        ).value;


                    const respuesta =
                        await fetch(
                            "{% url 'aplicar_promocion' %}",
                            {
                                method: 'POST',

                                headers: {
                                    'Content-Type':
                                        'application/x-www-form-urlencoded; charset=UTF-8',

                                    'X-CSRFToken':
                                        csrfToken,

                                    'X-Requested-With':
                                        'XMLHttpRequest'
                                },

                                body:
                                    new URLSearchParams({
                                        codigo_promocion:
                                            codigo
                                    })
                            }
                        );


                    if (!respuesta.ok) {

                        throw new Error(
                            'HTTP ' +
                            respuesta.status
                        );

                    }


                    const datos =
                        await respuesta.json();


                    if (!datos.ok) {

                        descuento = 0;

                        promoStatus.textContent =
                            datos.mensaje ||
                            'La promoción no se puede aplicar.';

                        actualizarTotal();

                        guardarCheckout();

                        return;

                    }


                    descuento =
                        Number(
                            datos.descuento
                        ) || 0;


                    promoStatus.textContent =
                        datos.mensaje ||
                        'Promoción aplicada correctamente.';


                    if (descuentoRow) {

                        descuentoRow.style.display =
                            descuento > 0
                                ? 'flex'
                                : 'none';

                    }


                    if (descuentoValor) {

                        descuentoValor.textContent =
                            '-$' +
                            descuento.toFixed(2);

                    }


                    actualizarTotal();

                    guardarCheckout();

                } catch (error) {

                    console.error(
                        'Error al aplicar promoción:',
                        error
                    );


                    descuento = 0;


                    promoStatus.textContent =
                        'No se pudo verificar la promoción.';


                    actualizarTotal();

                } finally {

                    promoButton.disabled =
                        false;

                }

            }
        );

    }


    form.addEventListener(
        'submit',
        function (e) {

            let esValido = true;

            let primerCampoInvalido = null;


            const camposTexto = [
                'nombre',
                'apellido',
                'calle',
                'numero',
                'localidad'
            ];


            camposTexto.forEach(
                function (campo) {

                    const input =
                        form.querySelector(
                            `[name="${campo}"]`
                        );


                    if (!input) {
                        return;
                    }


                    if (!input.value.trim()) {

                        mostrarError(
                            campo,
                            mensajes[campo]
                        );

                        esValido = false;

                        if (!primerCampoInvalido) {
                            primerCampoInvalido =
                                input;
                        }

                    } else {

                        ocultarError(
                            campo
                        );

                    }

                }
            );


            const telefonoInput =
                form.querySelector(
                    '[name="telefono"]'
                );


            if (telefonoInput) {

                const telefonoValor =
                    telefonoInput.value.trim();


                if (!telefonoValor) {

                    mostrarError(
                        'telefono',
                        mensajes.telefono_vacio
                    );

                    esValido = false;

                    if (!primerCampoInvalido) {
                        primerCampoInvalido =
                            telefonoInput;
                    }

                } else if (
                    !patronTelefono.test(
                        telefonoValor
                    )
                ) {

                    mostrarError(
                        'telefono',
                        mensajes.telefono_invalido
                    );

                    esValido = false;

                    if (!primerCampoInvalido) {
                        primerCampoInvalido =
                            telefonoInput;
                    }

                } else {

                    ocultarError(
                        'telefono'
                    );

                }

            }


            const medioPago =
                form.querySelector(
                    '[name="medio_pago"]:checked'
                );


            if (!medioPago) {

                mostrarError(
                    'medio_pago',
                    mensajes.medio_pago
                );

                esValido = false;

                if (!primerCampoInvalido) {

                    primerCampoInvalido =
                        form.querySelector(
                            '[name="medio_pago"]'
                        );

                }

            } else {

                ocultarError(
                    'medio_pago'
                );

            }


            if (!esValido) {

                e.preventDefault();

                if (primerCampoInvalido) {
                    primerCampoInvalido.focus();
                }

                return;

            }


            guardarCheckout();

        }
    );


    form.querySelectorAll(
        'input, select, textarea'
    ).forEach(
        function (elemento) {

            elemento.addEventListener(
                'input',
                function () {

                    ocultarError(
                        elemento.name
                    );

                }
            );


            elemento.addEventListener(
                'change',
                function () {

                    ocultarError(
                        elemento.name
                    );

                }
            );

        }
    );


    actualizarTotal();

});