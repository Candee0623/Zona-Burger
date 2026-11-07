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

        const confirmado = await ZB.confirmar({
            titulo: 'Guardar cambios',
            mensaje: '¿Querés guardar los cambios en las cantidades?',
            textoConfirmar: 'Guardar'
        });

        if (!confirmado) return;

        if (await guardarCambios()) {
            window.recetaGuardandoCambios = true;
            window.location.reload();
        }
    });

    // Al ir a otra página con cantidades sin guardar:
    //  - Guardar y salir: guarda y después te lleva a donde querías ir.
    //  - Salir sin guardar: te lleva igual, sin guardar.
    //  - Seguir editando: te quedás en la receta.
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

        const decision = await ZB.dialogo({
            titulo: 'Cambios sin guardar',
            mensaje:
                'Modificaste cantidades de la receta que todavía no guardaste. ' +
                '¿Querés guardarlas antes de salir?',
            tipo: 'info',
            valorCancelar: 'quedarme',
            botones: [
                { texto: 'Seguir editando', valor: 'quedarme', estilo: 'sutil' },
                { texto: 'Salir sin guardar', valor: 'salir', estilo: 'secundario' },
                { texto: 'Guardar y salir', valor: 'guardar', estilo: 'primario', porDefecto: true }
            ]
        });

        if (decision === 'quedarme') return;

        if (decision === 'guardar') {
            const guardado = await guardarCambios();

            // Si falló, se queda en la receta para no perder los cambios.
            if (!guardado) return;
        }

        window.recetaGuardandoCambios = true;
        window.location.assign(destino.href);
    });

    document.querySelectorAll('.form-quitar-insumo').forEach(function (formulario) {
        // La confirmación la muestra dialogos.js (data-confirmar).
        formulario.setAttribute('data-confirmar', '¿Querés quitar este ingrediente de la receta?');
        formulario.setAttribute('data-confirmar-titulo', 'Quitar ingrediente');
        formulario.setAttribute('data-confirmar-boton', 'Quitar');
        formulario.setAttribute('data-confirmar-tipo', 'peligro');

        formulario.addEventListener('submit', function () {
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
