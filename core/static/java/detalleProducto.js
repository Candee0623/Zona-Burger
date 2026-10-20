'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const MAX_CANTIDAD_EXTRA = 5;
    const INTERVALO_ESTADO = 5000;
    const ENDPOINT_ESTADO = '/api/negocio/estado/';

    const form = document.getElementById('form-personalizar');
    if (!form) return;

    const elementoPrecioBase = document.querySelector('.detalle-precio-base');
    const precioBase = elementoPrecioBase
        ? numero(elementoPrecioBase.dataset.precioBase)
        : 0;

    const spanTotal = document.getElementById('precio-total');
    const aviso = document.getElementById('aviso-obligatorio');
    const botonEnviar = document.getElementById('btn-confirmar-pedido');

    const grupos = [
        ...form.querySelectorAll('.grupo-opcion-seccion[data-min]')
    ];

    const inputsOpciones = [
        ...form.querySelectorAll(
            'input[type="radio"], input[type="checkbox"]'
        )
    ];

    const inputsCantidad = [
        ...form.querySelectorAll('.cantidad-extra')
    ];

    const productoId = form.dataset.productoId || 'producto';
    const editId = form.dataset.editId || 'nuevo';

    const claveEstado = `detalle_producto_${productoId}_${editId}`;

    let intentoEnvio = false;
    let temporizadorAviso = null;
    let temporizadorEstado = null;
    let consultaEnCurso = false;
    let negocioAbierto = null;

    // --------------------------------------------------
    // AVISO DE NEGOCIO CERRADO
    // --------------------------------------------------

    let avisoCierre = document.getElementById(
        'aviso-negocio-cerrado'
    );

    if (!avisoCierre) {
        avisoCierre = document.createElement('div');
        avisoCierre.id = 'aviso-negocio-cerrado';
        avisoCierre.setAttribute('role', 'status');
        avisoCierre.setAttribute('aria-live', 'polite');

        avisoCierre.style.cssText = [
            'display:none',
            'align-items:flex-start',
            'gap:12px',
            'padding:14px 16px',
            'border-radius:10px',
            'margin-bottom:20px',
            'background:rgba(220,38,38,.15)',
            'border:1px solid rgba(220,38,38,.45)',
            'color:#fca5a5'
        ].join(';');

        avisoCierre.innerHTML = `
            <i class="fa-solid fa-clock"
               style="font-size:1.15rem;color:#ef4444;margin-top:2px">
            </i>
            <div>
                <strong style="display:block;font-size:.9rem;color:#fff;margin-bottom:3px">
                    En este momento el negocio está cerrado.
                </strong>
                <span style="font-size:.82rem;color:#d1d5db">
                    No es posible agregar productos al carrito.
                    Podrás realizar tu pedido cuando vuelva a abrir.
                </span>
            </div>
        `;

        form.parentNode.insertBefore(avisoCierre, form);
    }

    // --------------------------------------------------
    // UTILIDADES
    // --------------------------------------------------

    function numero(valor) {
        const resultado = Number.parseFloat(valor);
        return Number.isFinite(resultado) ? resultado : 0;
    }

    function limitarCantidad(valor) {
        const cantidad = Number.parseInt(valor, 10);

        if (!Number.isFinite(cantidad)) return 1;

        return Math.max(1, Math.min(cantidad, MAX_CANTIDAD_EXTRA));
    }

    function guardarEstadoSeguro() {
        try {
            const estado = {
                inputs: inputsOpciones.map(function (input) {
                    return {
                        name: input.name,
                        value: input.value,
                        checked: input.checked
                    };
                }),
                cantidades: {}
            };

            inputsCantidad.forEach(function (input) {
                estado.cantidades[input.name] = input.value;
            });

            sessionStorage.setItem(
                claveEstado,
                JSON.stringify(estado)
            );

            return true;
        } catch (error) {
            console.warn(
                'No se pudo guardar la personalización.',
                error
            );

            return false;
        }
    }

    // --------------------------------------------------
    // CÁLCULO DEL PRECIO
    // --------------------------------------------------

    function calcularTotal() {
        let total = precioBase;

        inputsOpciones.forEach(function (input) {
            if (!input.checked) return;

            const precio = numero(input.dataset.precio);
            const fila = input.closest('.opcion-item');
            const campoCantidad = fila
                ? fila.querySelector('.cantidad-extra')
                : null;

            const cantidad =
                input.classList.contains('extra-checkbox') &&
                campoCantidad
                    ? limitarCantidad(campoCantidad.value)
                    : 1;

            total += precio * cantidad;
        });

        if (spanTotal) {
            spanTotal.textContent = total.toFixed(2);
        }
    }

    // --------------------------------------------------
    // VALIDACIÓN DE GRUPOS
    // --------------------------------------------------

    function seleccionadasEnGrupo(seccion) {
        return seccion.querySelectorAll(
            'input[type="radio"]:checked, input[type="checkbox"]:checked'
        ).length;
    }

    
    function validarGrupos() {
        const incompletos = [];

        grupos.forEach(function (seccion) {
            const minimo = parseInt(seccion.dataset.min, 10) || 0;
            const maximo = parseInt(seccion.dataset.max, 10) || 0;
            const cantidad = seleccionadasEnGrupo(seccion);

            const faltaMinimo = minimo > 0 && cantidad < minimo;
            const superaMaximo = maximo > 0 && cantidad > maximo;
            const invalido = faltaMinimo || superaMaximo;

            if (invalido) {
                incompletos.push(seccion);
            }

            // Mostrar el estado de error al intentar enviar,
            // o cuando el usuario ya empezó a corregir ese grupo.
            seccion.classList.toggle(
                'grupo-incompleto',
                invalido && intentoEnvio
            );

            seccion.classList.toggle(
                'grupo-completo',
                intentoEnvio && !invalido && minimo > 0
            );

            // Actualizar el mensaje de validación si existe.
            const mensaje = seccion.querySelector(
                '.mensaje-validacion-grupo'
            );

            if (mensaje) {
                mensaje.style.display = faltaMinimo && intentoEnvio
                    ? 'flex'
                    : 'none';
            }
        });

        return incompletos;
    }


    function mostrarAviso(texto) {
        if (!aviso) return;

        aviso.textContent = texto;
        aviso.classList.add('visible');

        clearTimeout(temporizadorAviso);

        temporizadorAviso = setTimeout(function () {
            aviso.classList.remove('visible');
        }, 4000);
    }

    function irAlGrupoIncompleto(seccion) {
        const minimo = parseInt(seccion.dataset.min, 10) || 0;
        const maximo = parseInt(seccion.dataset.max, 10) || 0;
        const seleccionadas = seleccionadasEnGrupo(seccion);
        const nombre = seccion.dataset.nombre || 'Este grupo';

        seccion.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        seccion.classList.remove('grupo-sacudir');
        void seccion.offsetWidth;
        seccion.classList.add('grupo-sacudir');

        setTimeout(function () {
            seccion.classList.remove('grupo-sacudir');
        }, 2000);

        const primerInput = seccion.querySelector('input');

        if (primerInput) {
            primerInput.focus({ preventScroll: true });
        }

        if (seleccionadas < minimo) {
            mostrarAviso(
                `"${nombre}" es obligatorio: elegí al menos ${minimo} ` +
                (minimo === 1 ? 'opción.' : 'opciones.')
            );
        } else {
            mostrarAviso(
                `"${nombre}" permite un máximo de ${maximo} opciones.`
            );
        }
    }

    // Evitar que se supere el máximo al marcar opciones.
    function controlarMaximo(seccion, inputModificado) {
        const maximo = parseInt(seccion.dataset.max, 10) || 0;

        if (maximo <= 0 || !inputModificado.checked) return true;

        const marcados = [
            ...seccion.querySelectorAll(
                'input[type="radio"]:checked, input[type="checkbox"]:checked'
            )
        ];

        if (marcados.length <= maximo) return true;

        inputModificado.checked = false;

        mostrarAviso(
            `"${seccion.dataset.nombre || 'Este grupo'}" permite un máximo de ` +
            `${maximo} ${maximo === 1 ? 'opción.' : 'opciones.'}`
        );

        return false;
    }

    // --------------------------------------------------
    // GUARDAR Y RESTAURAR OPCIONES DEL CLIENTE
    // --------------------------------------------------

    function restaurarEstado() {
        try {
            const guardado = sessionStorage.getItem(claveEstado);
            if (!guardado) return;

            const estado = JSON.parse(guardado);

            if (!estado || !Array.isArray(estado.inputs)) return;

            // Restaurar tanto las opciones marcadas como las desmarcadas.
            estado.inputs.forEach(function (dato) {
                const input = inputsOpciones.find(function (elemento) {
                    return elemento.name === dato.name &&
                        elemento.value === dato.value;
                });

                if (input) {
                    input.checked = Boolean(dato.checked);
                }
            });

            // Restaurar cantidades de extras.
            if (estado.cantidades) {
                inputsCantidad.forEach(function (input) {
                    if (
                        Object.prototype.hasOwnProperty.call(
                            estado.cantidades,
                            input.name
                        )
                    ) {
                        input.value = limitarCantidad(
                            estado.cantidades[input.name]
                        );
                    }
                });
            }

            // Corregir selecciones que ya no respeten el máximo.
            grupos.forEach(function (seccion) {
                const maximo = parseInt(seccion.dataset.max, 10) || 0;
                if (maximo <= 0) return;

                const marcados = [
                    ...seccion.querySelectorAll(
                        'input[type="radio"]:checked, input[type="checkbox"]:checked'
                    )
                ];

                marcados.slice(maximo).forEach(function (input) {
                    input.checked = false;
                });
            });
        } catch (error) {
            console.warn(
                'No se pudo restaurar la personalización.',
                error
            );
        }
    }

    // Guardar cada modificación sin esperar al envío.
    
    form.addEventListener('change', function (event) {
        const input = event.target;

        if (
            input.matches('input[type="radio"], input[type="checkbox"]')
        ) {
            const seccion = input.closest(
                '.grupo-opcion-seccion[data-min]'
            );

            if (seccion) {
                const maximoRespetado = controlarMaximo(
                    seccion,
                    input
                );

                // Si se supera el máximo, controlarMaximo
                // desmarca la opción recién seleccionada.
                if (!maximoRespetado) {
                    calcularTotal();
                    validarGrupos();
                    guardarEstadoSeguro();
                    return;
                }
            }
        }

        if (input.matches('.cantidad-extra')) {
            input.value = limitarCantidad(input.value);
        }

        calcularTotal();
        validarGrupos();
        guardarEstadoSeguro();
    });


    form.addEventListener('input', function (event) {
        if (event.target.matches('.cantidad-extra')) {
            const cantidadAnterior = event.target.value;
            const cantidadNueva = limitarCantidad(cantidadAnterior);

            if (String(cantidadNueva) !== cantidadAnterior) {
                event.target.value = cantidadNueva;
            }

            calcularTotal();
            guardarEstadoSeguro();
        }
    });

    // Guardar también al abandonar o recargar la página.
    window.addEventListener('beforeunload', guardarEstadoSeguro);

    // --------------------------------------------------
    // ACTUALIZACIÓN DEL ESTADO DEL NEGOCIO
    // --------------------------------------------------

    function aplicarEstadoNegocio(data) {
        if (!data || typeof data.abierto !== 'boolean') return;

        negocioAbierto = data.abierto;

        if (botonEnviar) {
            const textoBoton = botonEnviar.querySelector(
                '[data-texto-boton]'
            );

            const icono = botonEnviar.querySelector('i');

            // No crear otro span: usar el que existe en el HTML.
            if (textoBoton) {
                textoBoton.textContent = negocioAbierto
                    ? (
                        form.dataset.editId
                            ? 'Guardar Cambios'
                            : 'Añadir al Pedido'
                    )
                    : 'Negocio Cerrado';
            }

            if (icono) {
                icono.className = negocioAbierto
                    ? 'fa-solid fa-cart-shopping'
                    : 'fa-solid fa-lock';
            }

            botonEnviar.type = negocioAbierto ? 'submit' : 'button';
            botonEnviar.disabled = !negocioAbierto;

            botonEnviar.title = negocioAbierto
                ? ''
                : 'En este momento el negocio está cerrado';

            botonEnviar.style.cursor = negocioAbierto
                ? ''
                : 'not-allowed';

            botonEnviar.style.opacity = negocioAbierto
                ? ''
                : '0.55';

            botonEnviar.style.backgroundColor = negocioAbierto
                ? ''
                : '#2a2a2a';

            botonEnviar.style.color = negocioAbierto
                ? ''
                : '#888';

            botonEnviar.style.borderColor = negocioAbierto
                ? ''
                : '#444';
        }

        if (avisoCierre) {
            avisoCierre.style.display = negocioAbierto ? 'none' : 'flex';
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
            // No cambiar el estado visual si falla la conexión.
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

        sincronizarEstadoNegocio();

        temporizadorEstado = setInterval(
            sincronizarEstadoNegocio,
            INTERVALO_ESTADO
        );
    }

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
    // VALIDACIÓN FINAL ANTES DE ENVIAR
    // --------------------------------------------------

    form.addEventListener('submit', function (event) {
        if (negocioAbierto === false) {
            event.preventDefault();

            mostrarAviso(
                'El negocio está cerrado. No podés enviar el pedido en este momento.'
            );

            return;
        }

        intentoEnvio = true;

        const incompletos = validarGrupos();

        if (incompletos.length > 0) {
            event.preventDefault();
            irAlGrupoIncompleto(incompletos[0]);
            return;
        }

        // Mantener la personalización por si el servidor devuelve un error.
        guardarEstadoSeguro();
    });

    // --------------------------------------------------
    // INICIALIZACIÓN
    // --------------------------------------------------

    restaurarEstado();
    calcularTotal();
    validarGrupos();
    iniciarActualizacion();
});