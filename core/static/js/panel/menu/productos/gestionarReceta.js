(function () {
    'use strict';

    const botonGuardar = document.getElementById(
        'guardar-todas-las-cantidades'
    );
    const estado = document.getElementById('estado-guardado');

    let guardando = false;
    window.recetaGuardandoCambios = false;

    const formularios = Array.from(
        document.querySelectorAll('.form-editar-cantidad')
    );

    function normalizar(valor) {
        const numero = Number(valor);
        return Number.isFinite(numero)
            ? String(Math.round(numero * 100) / 100)
            : '';
    }

    function tieneCambios(formulario) {
        const input = formulario.querySelector('[name="cantidadinsumo"]');

        return input &&
            normalizar(input.value) !==
            normalizar(formulario.dataset.cantidadOriginal);
    }

    function cambiosPendientes() {
        return formularios.some(tieneCambios);
    }

    function actualizarInterfaz() {
        const hayCambios = cambiosPendientes();

        botonGuardar.hidden = !hayCambios;
        botonGuardar.disabled = guardando;

        if (!guardando && estado.dataset.tipo !== 'error') {
            estado.hidden = true;
            estado.textContent = '';
        }
    }

    formularios.forEach(function (formulario) {
        const input = formulario.querySelector('[name="cantidadinsumo"]');

        input.addEventListener('input', function () {
            estado.hidden = true;
            estado.dataset.tipo = '';
            actualizarInterfaz();
        });
    });

    // Guarda todas las cantidades modificadas.
    // Devuelve true si se guardó todo (o no había nada para guardar).
    async function guardarCambios() {
        const modificados = formularios.filter(tieneCambios);

        if (!modificados.length) return true;

        for (const formulario of modificados) {
            const input = formulario.querySelector('[name="cantidadinsumo"]');

            if (!formulario.checkValidity()) {
                input.reportValidity();
                input.focus();
                return false;
            }
        }

        guardando = true;
        botonGuardar.disabled = true;
        botonGuardar.textContent = 'Guardando...';
        estado.hidden = true;
        estado.dataset.tipo = '';

        try {
            for (const formulario of modificados) {
                const respuesta = await fetch(formulario.action, {
                    method: 'POST',
                    body: new FormData(formulario),
                    credentials: 'same-origin',
                    redirect: 'follow',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (!respuesta.ok || respuesta.redirected &&
                    new URL(respuesta.url).pathname.includes('/login')) {
                    throw new Error('No se pudo guardar una de las cantidades.');
                }
            }

            return true;

        } catch (error) {
            estado.textContent =
                'No se pudieron guardar todos los cambios. Revisá tu conexión e intentá nuevamente.';
            estado.dataset.tipo = 'error';
            estado.hidden = false;

            return false;

        } finally {
            guardando = false;
            botonGuardar.disabled = false;
            botonGuardar.textContent = 'Guardar cambios';
            actualizarInterfaz();
        }
    }

    // Botón "Guardar cambios": pide confirmación, guarda y recarga.
    botonGuardar.addEventListener('click', async function () {
        if (guardando) return;

        if (!cambiosPendientes()) {
            actualizarInterfaz();
            return;
        }

        const confirmado = window.confirm(
            '¿Querés guardar los cambios en las cantidades?'
        );

        if (!confirmado) return;

        if (await guardarCambios()) {
            // Recargar desde el servidor para mostrar los valores guardados.
            window.recetaGuardandoCambios = true;
            window.location.reload();
        }
    });

    // Al ir a otra página con cantidades sin guardar:
    //  - Aceptar: guarda y después te lleva a donde querías ir.
    //  - Cancelar: no guarda y te lleva igual.
    document.addEventListener('click', async function (evento) {
        const enlace = evento.target.closest('a[href]');

        if (!enlace) return;
        if (evento.defaultPrevented || evento.button !== 0) return;
        if (evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
        if (enlace.target && enlace.target !== '_self') return;
        if (enlace.hasAttribute('download')) return;

        const destino = new URL(enlace.href, window.location.href);

        if (!/^https?:$/.test(destino.protocol)) return;

        const mismaPagina =
            destino.href.split('#')[0] === window.location.href.split('#')[0];

        if (mismaPagina && destino.hash) return;
        if (!cambiosPendientes()) return;

        evento.preventDefault();

        if (guardando) return;

        const guardar = window.confirm(
            '¿Querés guardar los cambios antes de salir?\n\n' +
            'Aceptar: guardar y salir.\n' +
            'Cancelar: salir sin guardar.'
        );

        if (guardar) {
            const guardado = await guardarCambios();

            // Si falló, se queda en la receta para no perder los cambios.
            if (!guardado) return;
        }

        window.recetaGuardandoCambios = true;
        window.location.assign(destino.href);
    });

    // Confirmar únicamente la eliminación de un ingrediente.
    document.querySelectorAll('.form-quitar-insumo').forEach(function (formulario) {
        formulario.addEventListener('submit', function (evento) {
            if (!window.confirm('¿Querés quitar este ingrediente de la receta?')) {
                evento.preventDefault();
                return;
            }

            window.recetaGuardandoCambios = true;
        });
    });

    // Cerrar la pestaña, recargar o salir por otro medio (formularios, botón
    // atrás): el navegador no permite mostrar un diálogo propio ni guardar
    // en ese momento, solo su aviso estándar.
    window.addEventListener('beforeunload', function (evento) {
        if (window.recetaGuardandoCambios || !cambiosPendientes()) return;

        evento.preventDefault();
        evento.returnValue = '';
    });

    actualizarInterfaz();
})();
