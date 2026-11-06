'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const MAX_CANTIDAD_EXTRA = 5;
    const INTERVALO_ESTADO = 5000;       // abierto / cerrado
    const INTERVALO_CONTENIDO = 10000;   // producto, precios, opciones, extras
    const ENDPOINT_ESTADO = '/api/negocio/estado/';
    const SEL_INPUTS = 'input[type="radio"], input[type="checkbox"]';
    const SEL_MARCADOS = 'input[type="radio"]:checked, input[type="checkbox"]:checked';
    const SEL_GRUPO = '.grupo-opcion-seccion[data-min]';

    const form = document.getElementById('form-personalizar');
    if (!form) return;

    const contInfo = document.getElementById('producto-info');
    const contOpciones = document.getElementById('opciones-dinamicas');
    const spanTotal = document.getElementById('precio-total');
    const aviso = document.getElementById('aviso-obligatorio');
    const botonEnviar = document.getElementById('btn-confirmar-pedido');
    const avisoCierre = document.getElementById('aviso-negocio-cerrado');

    const claveEstado = `detalle_producto_${form.dataset.productoId || 'producto'}_${form.dataset.editId || 'nuevo'}`;

    // Firma del contenido tal como lo envió el servidor (antes de que el JS lo toque).
    let firmaContenido = firmaDe(contInfo, contOpciones);

    let intentoEnvio = false;
    let temporizadorAviso = null;
    let negocioAbierto = form.dataset.abierto !== '0';
    let productoDisponible = true;

    // --------------------------------------------------
    // UTILIDADES
    // --------------------------------------------------

    const obtenerInputs = () => [...form.querySelectorAll(SEL_INPUTS)];
    const obtenerInputsCantidad = () => [...form.querySelectorAll('[data-cantidad]')];
    const obtenerGrupos = () => [...form.querySelectorAll(SEL_GRUPO)];
    const claveInput = (input) => `${input.name}|${input.value}`;
    const minimoDe = (seccion) => parseInt(seccion.dataset.min, 10) || 0;
    const maximoDe = (seccion) => parseInt(seccion.dataset.max, 10) || 0;
    const seleccionadasEnGrupo = (seccion) => seccion.querySelectorAll(SEL_MARCADOS).length;

    function numero(valor) {
        const resultado = Number.parseFloat(valor);
        return Number.isFinite(resultado) ? resultado : 0;
    }

    function limitarCantidad(valor) {
        const cantidad = Number.parseInt(valor, 10);
        if (!Number.isFinite(cantidad)) return 1;
        return Math.max(1, Math.min(cantidad, MAX_CANTIDAD_EXTRA));
    }

    function precioBase() {
        const el = document.querySelector('.detalle-precio-base');
        return el ? numero(el.dataset.precioBase) : 0;
    }

    function textoMaximo(seccion) {
        const max = maximoDe(seccion);
        return `"${seccion.dataset.nombre || 'Este grupo'}" permite un máximo de ` +
            `${max} ${max === 1 ? 'opción.' : 'opciones.'}`;
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

    // Firma del contenido ignorando lo que cambia el cliente (checks y cantidades).
    function firmaDe(...nodos) {
        return nodos.map(function (nodo) {
            const copia = nodo.cloneNode(true);
            copia.querySelectorAll('[checked]').forEach((e) => e.removeAttribute('checked'));
            copia.querySelectorAll('[data-cantidad]').forEach((e) => e.removeAttribute('value'));
            copia.querySelectorAll('[data-contador]').forEach((e) => { e.textContent = ''; });
            return copia.innerHTML;
        }).join('\u0000');
    }

    // --------------------------------------------------
    // GUARDAR / RESTAURAR SELECCIÓN DEL CLIENTE
    // --------------------------------------------------

    function guardarEstadoSeguro() {
        try {
            const estado = {
                inputs: obtenerInputs().map((i) => ({ name: i.name, value: i.value, checked: i.checked })),
                cantidades: {}
            };
            obtenerInputsCantidad().forEach((i) => { estado.cantidades[i.name] = i.value; });
            sessionStorage.setItem(claveEstado, JSON.stringify(estado));
            return true;
        } catch (error) {
            console.warn('No se pudo guardar la personalización.', error);
            return false;
        }
    }

    function restaurarEstado() {
        try {
            const guardado = sessionStorage.getItem(claveEstado);
            if (!guardado) return;

            const estado = JSON.parse(guardado);
            if (!estado || !Array.isArray(estado.inputs)) return;

            const inputs = obtenerInputs();
            estado.inputs.forEach(function (dato) {
                const input = inputs.find((i) => i.name === dato.name && i.value === dato.value);
                if (input) input.checked = Boolean(dato.checked);
            });

            if (estado.cantidades) {
                obtenerInputsCantidad().forEach(function (input) {
                    if (input.name in estado.cantidades) {
                        input.value = limitarCantidad(estado.cantidades[input.name]);
                    }
                });
            }

            // Un estado viejo no puede superar el máximo actual.
            obtenerGrupos().forEach(function (seccion) {
                const maximo = maximoDe(seccion);
                if (maximo <= 0) return;
                [...seccion.querySelectorAll(SEL_MARCADOS)].slice(maximo).forEach((i) => { i.checked = false; });
            });
        } catch (error) {
            console.warn('No se pudo restaurar la personalización.', error);
        }
    }

    // --------------------------------------------------
    // PRECIO, CANTIDADES Y VALIDACIÓN
    // --------------------------------------------------

    function calcularTotal() {
        let total = precioBase();

        obtenerInputs().forEach(function (input) {
            if (!input.checked) return;

            const fila = input.closest('.opcion-item');
            const campoCantidad = fila ? fila.querySelector('[data-cantidad]') : null;
            const cantidad = input.hasAttribute('data-extra') && campoCantidad
                ? limitarCantidad(campoCantidad.value)
                : 1;

            total += numero(input.dataset.precio) * cantidad;
        });

        if (spanTotal) spanTotal.textContent = total.toFixed(2);
    }

    function actualizarBotonesCantidad() {
        form.querySelectorAll('[data-stepper]').forEach(function (stepper) {
            const valor = limitarCantidad(stepper.querySelector('[data-cantidad]').value);
            stepper.querySelector('[data-accion="restar"]').disabled = valor <= 1;
            stepper.querySelector('[data-accion="sumar"]').disabled = valor >= MAX_CANTIDAD_EXTRA;
        });
    }

    function validarGrupos() {
        const incompletos = [];

        obtenerGrupos().forEach(function (seccion) {
            const minimo = minimoDe(seccion);
            const maximo = maximoDe(seccion);
            const cantidad = seleccionadasEnGrupo(seccion);

            const faltaMinimo = minimo > 0 && cantidad < minimo;
            const superaMaximo = maximo > 0 && cantidad > maximo;
            const invalido = faltaMinimo || superaMaximo;

            if (invalido) incompletos.push(seccion);

            seccion.classList.toggle('grupo-incompleto', invalido && intentoEnvio);
            seccion.classList.toggle('grupo-completo', intentoEnvio && !invalido && minimo > 0);

            const mensaje = seccion.querySelector('.mensaje-validacion-grupo');
            if (mensaje) mensaje.style.display = faltaMinimo && intentoEnvio ? 'flex' : 'none';

            // Contador y bloqueo visual cuando se llegó al máximo:
            // las no marcadas quedan atenuadas, las marcadas siguen pudiéndose desmarcar.
            const contador = seccion.querySelector('[data-contador]');
            if (contador && maximo > 0) contador.textContent = `${cantidad}/${maximo}`;

            seccion.querySelectorAll('.opcion-item').forEach(function (item) {
                const input = item.querySelector(SEL_INPUTS);
                item.classList.toggle(
                    'opcion-bloqueada',
                    Boolean(maximo > 0 && cantidad >= maximo && input && !input.checked)
                );
            });
        });

        return incompletos;
    }

    function irAlGrupoIncompleto(seccion) {
        const minimo = minimoDe(seccion);
        const nombre = seccion.dataset.nombre || 'Este grupo';

        seccion.scrollIntoView({ behavior: 'smooth', block: 'center' });

        seccion.classList.remove('grupo-sacudir');
        void seccion.offsetWidth;
        seccion.classList.add('grupo-sacudir');
        setTimeout(() => seccion.classList.remove('grupo-sacudir'), 2000);

        const primerInput = seccion.querySelector('input');
        if (primerInput) primerInput.focus({ preventScroll: true });

        if (seleccionadasEnGrupo(seccion) < minimo) {
            mostrarAviso(
                `"${nombre}" es obligatorio: elegí al menos ${minimo} ` +
                (minimo === 1 ? 'opción.' : 'opciones.')
            );
        } else {
            mostrarAviso(textoMaximo(seccion));
        }
    }

    function refrescar(guardar = true) {
        calcularTotal();
        validarGrupos();
        actualizarBotonesCantidad();
        if (guardar) guardarEstadoSeguro();
    }

    // --------------------------------------------------
    // EVENTOS DEL FORMULARIO (delegados: sobreviven al refresco en vivo)
    // --------------------------------------------------

    form.addEventListener('click', function (event) {
        // Botones + / - de cantidad
        const boton = event.target.closest('[data-accion]');
        if (boton) {
            event.preventDefault();
            const campo = boton.closest('[data-stepper]').querySelector('[data-cantidad]');
            const delta = boton.dataset.accion === 'sumar' ? 1 : -1;
            campo.value = limitarCantidad((Number.parseInt(campo.value, 10) || 1) + delta);
            campo.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }

        // Máximo por grupo: no deja marcar más, pero siempre deja desmarcar.
        const input = event.target.closest(SEL_INPUTS);
        if (!input || !input.checked) return;

        const seccion = input.closest(SEL_GRUPO);
        if (!seccion) return;

        const maximo = maximoDe(seccion);
        if (maximo > 0 && seleccionadasEnGrupo(seccion) > maximo) {
            event.preventDefault(); // revierte la marca
            mostrarAviso(textoMaximo(seccion));
        }
    });

    form.addEventListener('change', function (event) {
        if (event.target.matches('[data-cantidad]')) {
            event.target.value = limitarCantidad(event.target.value);
        }
        refrescar();
    });

    window.addEventListener('beforeunload', guardarEstadoSeguro);

    form.addEventListener('submit', function (event) {
        if (!negocioAbierto || !productoDisponible) {
            event.preventDefault();
            mostrarAviso(
                productoDisponible
                    ? 'El negocio está cerrado. No podés enviar el pedido en este momento.'
                    : 'Este producto ya no está disponible.'
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

        guardarEstadoSeguro();
    });

    // --------------------------------------------------
    // ESTADO DEL NEGOCIO Y BOTÓN
    // --------------------------------------------------

    function actualizarBoton() {
        const habilitado = negocioAbierto && productoDisponible;

        if (avisoCierre) avisoCierre.hidden = negocioAbierto;
        if (!botonEnviar) return;

        const texto = botonEnviar.querySelector('[data-texto-boton]');
        const icono = botonEnviar.querySelector('i');

        if (texto) {
            texto.textContent = !productoDisponible
                ? 'Producto no disponible'
                : negocioAbierto
                    ? (form.dataset.editId ? 'Guardar Cambios' : 'Añadir al Pedido')
                    : 'Negocio Cerrado';
        }

        if (icono) icono.className = habilitado ? 'fa-solid fa-cart-shopping' : 'fa-solid fa-lock';

        botonEnviar.type = habilitado ? 'submit' : 'button';
        botonEnviar.disabled = !habilitado;
        botonEnviar.classList.toggle('cerrado', !habilitado);
        botonEnviar.title = habilitado
            ? ''
            : (productoDisponible ? 'En este momento el negocio está cerrado' : 'Este producto ya no está disponible');
    }

    async function sincronizarEstadoNegocio() {
        const respuesta = await fetch(ENDPOINT_ESTADO, {
            method: 'GET',
            headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            cache: 'no-store',
            credentials: 'same-origin'
        });

        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);

        const data = await respuesta.json();
        if (!data || typeof data.abierto !== 'boolean') throw new Error('Respuesta de estado inválida');

        negocioAbierto = data.abierto;
        actualizarBoton();
    }

    // --------------------------------------------------
    // ACTUALIZACIÓN EN VIVO DEL PRODUCTO
    // (nombre, descripción, imagen, precio, grupos, extras, ingredientes)
    // --------------------------------------------------

    function marcarNoDisponible() {
        if (!productoDisponible) return;
        productoDisponible = false;
        actualizarBoton();
        mostrarAviso('Este producto ya no está disponible.');
    }

    function aplicarContenido(nuevoInfo, nuevasOpciones, titulo) {
        // 1) Foto de lo que el cliente tiene elegido ahora.
        const previos = new Map(obtenerInputs().map((i) => [claveInput(i), i.checked]));
        const cantidades = new Map(obtenerInputsCantidad().map((i) => [i.name, i.value]));
        const activo = document.activeElement && document.activeElement.matches(SEL_INPUTS)
            ? claveInput(document.activeElement)
            : null;

        // 2) Reemplazar el HTML.
        const clonar = (nodo) => [...nodo.childNodes].map((n) => document.importNode(n, true));
        contInfo.replaceChildren(...clonar(nuevoInfo));
        contOpciones.replaceChildren(...clonar(nuevasOpciones));
        if (titulo) document.title = titulo;

        // 3) Reaplicar la selección del cliente sobre lo nuevo.
        const nuevos = new Map(obtenerInputs().map((i) => [claveInput(i), i]));
        let perdidas = false;

        previos.forEach(function (marcado, clave) {
            if (nuevos.has(clave)) nuevos.get(clave).checked = marcado;
            else if (marcado) perdidas = true;
        });

        obtenerInputsCantidad().forEach(function (input) {
            if (cantidades.has(input.name)) input.value = limitarCantidad(cantidades.get(input.name));
        });

        if (activo && nuevos.has(activo)) nuevos.get(activo).focus({ preventScroll: true });

        refrescar();

        mostrarAviso(
            perdidas
                ? 'El producto se actualizó y algunas opciones que elegiste ya no están disponibles.'
                : 'La información del producto se actualizó.'
        );
    }

    async function sincronizarContenido() {
        const respuesta = await fetch(window.location.href, {
            method: 'GET',
            headers: { 'Accept': 'text/html', 'X-Requested-With': 'XMLHttpRequest' },
            cache: 'no-store',
            credentials: 'same-origin'
        });

        const otraRuta = new URL(respuesta.url).pathname !== window.location.pathname;

        if (respuesta.status === 404 || respuesta.status === 410 || otraRuta) {
            marcarNoDisponible();
            return;
        }

        if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);

        const doc = new DOMParser().parseFromString(await respuesta.text(), 'text/html');
        const nuevoInfo = doc.getElementById('producto-info');
        const nuevasOpciones = doc.getElementById('opciones-dinamicas');

        if (!nuevoInfo || !nuevasOpciones) throw new Error('Contenido del producto inválido');

        if (!productoDisponible) {
            productoDisponible = true;
            actualizarBoton();
        }

        const firma = firmaDe(nuevoInfo, nuevasOpciones);
        if (firma === firmaContenido) return;

        firmaContenido = firma;
        aplicarContenido(nuevoInfo, nuevasOpciones, doc.title);
    }

    // --------------------------------------------------
    // SONDEOS (se pausan con la pestaña oculta)
    // --------------------------------------------------

    function crearSondeo(tarea, intervalo) {
        let id = null;
        let ocupado = false;

        async function ejecutar() {
            if (ocupado || document.hidden) return;
            ocupado = true;
            try {
                await tarea();
            } catch (error) {
                // Si falla la conexión no se toca lo que ya se está mostrando.
                console.warn('No se pudo actualizar la información.', error);
            } finally {
                ocupado = false;
            }
        }

        return {
            iniciar(inmediato = true) {
                this.detener();
                if (document.hidden) return;
                if (inmediato) ejecutar();
                id = setInterval(ejecutar, intervalo);
            },
            detener() {
                if (id !== null) {
                    clearInterval(id);
                    id = null;
                }
            }
        };
    }

    const sondeoEstado = crearSondeo(sincronizarEstadoNegocio, INTERVALO_ESTADO);
    const sondeoContenido = crearSondeo(sincronizarContenido, INTERVALO_CONTENIDO);

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            sondeoEstado.detener();
            sondeoContenido.detener();
        } else {
            sondeoEstado.iniciar();
            sondeoContenido.iniciar();
        }
    });

    window.addEventListener('pageshow', function (event) {
        if (event.persisted && !document.hidden) {
            sondeoEstado.iniciar();
            sondeoContenido.iniciar();
        }
    });

    window.addEventListener('pagehide', function () {
        sondeoEstado.detener();
        sondeoContenido.detener();
    });

    // --------------------------------------------------
    // INICIALIZACIÓN
    // --------------------------------------------------

    restaurarEstado();
    refrescar(false);
    actualizarBoton();
    sondeoEstado.iniciar();
    sondeoContenido.iniciar(false); // el contenido ya viene recién renderizado
});