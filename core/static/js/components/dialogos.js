/* =========================================================
   ZONA-BURGER
   DIÁLOGOS Y AVISOS PROPIOS (reemplazan los del navegador)

   USO DESDE JAVASCRIPT
     ZB.confirmar({ titulo, mensaje, textoConfirmar, textoCancelar, tipo })
         -> Promise<boolean>
     ZB.avisar({ titulo, mensaje, tipo, textoBoton })
         -> Promise<void>
     ZB.dialogo({ titulo, mensaje, tipo, botones: [...], valorCancelar })
         -> Promise<valor del botón elegido>

   USO DESDE HTML (sin escribir JavaScript)
     <form data-confirmar="¿Seguro?" data-confirmar-titulo="Eliminar"
           data-confirmar-boton="Eliminar" data-confirmar-tipo="peligro">
     <a / button data-confirmar="..."> (igual que el form)

   Además:
     - window.alert() pasa a mostrar un aviso con estilo.
     - Los mensajes de "Completá este campo" del navegador se
       reemplazan por una burbuja con el estilo de la página.
   ========================================================= */

(function () {
    'use strict';

    if (window.ZB && window.ZB.__listo) return;

    // Íconos en SVG propio (no dependen de ninguna librería externa).
    function svg(contenido) {
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" ' +
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + contenido + '</svg>';
    }

    const ICONOS = {
        normal: svg('<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>'),
        peligro: svg('<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>'),
        exito: svg('<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>'),
        info: svg('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>')
    };

    const ICONO_ERROR = svg('<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>');

    let cola = Promise.resolve();
    let contador = 0;

    /* DIÁLOGO BASE */

    function crearElemento(etiqueta, clase, texto) {
        const el = document.createElement(etiqueta);
        if (clase) el.className = clase;
        if (texto !== undefined) el.textContent = texto;
        return el;
    }

    function mostrar(opciones) {
        return new Promise(function (resolver) {
            const id = 'zb-dialogo-' + (++contador);
            const tipo = ICONOS[opciones.tipo] ? opciones.tipo : 'normal';
            const botones = opciones.botones && opciones.botones.length
                ? opciones.botones
                : [{ texto: 'Aceptar', valor: true, estilo: 'primario', porDefecto: true }];

            const previo = document.activeElement;

            const overlay = crearElemento('div', 'zb-overlay');
            const caja = crearElemento('div', 'zb-dialogo zb-dialogo--' + tipo);
            caja.setAttribute('role', 'alertdialog');
            caja.setAttribute('aria-modal', 'true');
            caja.setAttribute('aria-labelledby', id + '-titulo');
            caja.setAttribute('aria-describedby', id + '-mensaje');

            const icono = crearElemento('div', 'zb-dialogo__icono');
            icono.innerHTML = ICONOS[tipo];

            const titulo = crearElemento('h2', 'zb-dialogo__titulo', opciones.titulo || '');
            titulo.id = id + '-titulo';

            const mensaje = crearElemento('p', 'zb-dialogo__mensaje', opciones.mensaje || '');
            mensaje.id = id + '-mensaje';

            const acciones = crearElemento('div', 'zb-dialogo__acciones');
            if (botones.length >= 3) acciones.classList.add('zb-dialogo__acciones--tres');

            const elementosBoton = botones.map(function (b) {
                const boton = crearElemento('button', 'zb-btn zb-btn--' + (b.estilo || 'secundario'), b.texto);
                boton.type = 'button';
                boton.addEventListener('click', function () { cerrar(b.valor); });
                acciones.appendChild(boton);
                return boton;
            });

            caja.appendChild(icono);
            if (opciones.titulo) caja.appendChild(titulo);
            caja.appendChild(mensaje);
            caja.appendChild(acciones);
            overlay.appendChild(caja);

            const valorCancelar = 'valorCancelar' in opciones ? opciones.valorCancelar : false;
            let cerrado = false;

            function cerrar(valor) {
                if (cerrado) return;
                cerrado = true;

                document.removeEventListener('keydown', alTeclear, true);
                overlay.classList.remove('zb-visible');

                setTimeout(function () {
                    overlay.remove();
                    if (!document.querySelector('.zb-overlay')) {
                        document.documentElement.classList.remove('zb-bloqueado');
                    }
                    if (previo && document.contains(previo) && previo.focus) {
                        try { previo.focus({ preventScroll: true }); } catch (e) { /* nada */ }
                    }
                    resolver(valor);
                }, 160);
            }

            function alTeclear(evento) {
                if (evento.key === 'Escape') {
                    evento.preventDefault();
                    evento.stopPropagation();
                    cerrar(valorCancelar);
                    return;
                }

                if (evento.key === 'Tab') {
                    const indice = elementosBoton.indexOf(document.activeElement);
                    let siguiente;

                    if (evento.shiftKey) {
                        siguiente = indice <= 0 ? elementosBoton.length - 1 : indice - 1;
                    } else {
                        siguiente = indice === -1 || indice === elementosBoton.length - 1 ? 0 : indice + 1;
                    }

                    evento.preventDefault();
                    elementosBoton[siguiente].focus();
                }
            }

            // Click en el fondo oscuro = cancelar.
            overlay.addEventListener('mousedown', function (evento) {
                if (evento.target === overlay) cerrar(valorCancelar);
            });

            document.addEventListener('keydown', alTeclear, true);
            document.documentElement.classList.add('zb-bloqueado');
            document.body.appendChild(overlay);

            // En acciones peligrosas el foco empieza en "Cancelar" (más seguro).
            let inicial = elementosBoton[elementosBoton.length - 1];
            const indiceDefecto = botones.findIndex(function (b) { return b.porDefecto; });
            if (indiceDefecto !== -1) inicial = elementosBoton[indiceDefecto];

            requestAnimationFrame(function () {
                overlay.classList.add('zb-visible');
                inicial.focus();
            });
        });
    }

    function dialogo(opciones) {
        const promesa = cola.then(function () { return mostrar(opciones || {}); });
        cola = promesa.catch(function () { /* mantiene la cola viva */ });
        return promesa;
    }

    function confirmar(opciones) {
        opciones = opciones || {};
        const peligro = opciones.tipo === 'peligro';

        return dialogo({
            titulo: opciones.titulo || '¿Confirmás la acción?',
            mensaje: opciones.mensaje || '',
            tipo: opciones.tipo || 'normal',
            valorCancelar: false,
            botones: [
                {
                    texto: opciones.textoCancelar || 'Cancelar',
                    valor: false,
                    estilo: 'secundario',
                    porDefecto: peligro
                },
                {
                    texto: opciones.textoConfirmar || 'Aceptar',
                    valor: true,
                    estilo: 'primario',
                    porDefecto: !peligro
                }
            ]
        });
    }

    function avisar(opciones) {
        if (typeof opciones === 'string') opciones = { mensaje: opciones };
        opciones = opciones || {};

        return dialogo({
            titulo: opciones.titulo || 'Aviso',
            mensaje: opciones.mensaje || '',
            tipo: opciones.tipo || 'info',
            valorCancelar: undefined,
            botones: [
                {
                    texto: opciones.textoBoton || 'Entendido',
                    valor: undefined,
                    estilo: 'primario',
                    porDefecto: true
                }
            ]
        });
    }

    window.ZB = {
        __listo: true,
        dialogo: dialogo,
        confirmar: confirmar,
        avisar: avisar
    };

    window.alert = function (mensaje) {
        avisar({ mensaje: String(mensaje === undefined ? '' : mensaje) });
    };

    /* CONFIRMACIONES DECLARATIVAS (data-confirmar="...") */

    function opcionesDesde(elemento) {
        return {
            titulo: elemento.getAttribute('data-confirmar-titulo') || undefined,
            mensaje: elemento.getAttribute('data-confirmar'),
            textoConfirmar: elemento.getAttribute('data-confirmar-boton') || undefined,
            tipo: elemento.getAttribute('data-confirmar-tipo') || 'normal'
        };
    }

    function enviarFormulario(formulario, boton) {
        formulario.dataset.zbConfirmado = 'true';

        try {
            if (typeof formulario.requestSubmit === 'function') {
                try {
                    boton ? formulario.requestSubmit(boton) : formulario.requestSubmit();
                } catch (e) {
                    formulario.requestSubmit();
                }
            } else {
                formulario.submit();
            }
        } finally {
            setTimeout(function () { delete formulario.dataset.zbConfirmado; }, 0);
        }
    }

    // Formularios: se intercepta antes que cualquier otro "submit".
    document.addEventListener('submit', function (evento) {
        const formulario = evento.target;
        if (!formulario || !formulario.hasAttribute || !formulario.hasAttribute('data-confirmar')) return;

        if (formulario.dataset.zbConfirmado === 'true') return;

        evento.preventDefault();
        evento.stopImmediatePropagation();

        const boton = evento.submitter || null;

        confirmar(opcionesDesde(formulario)).then(function (acepto) {
            if (acepto) enviarFormulario(formulario, boton);
        });
    }, true);

    // Enlaces y botones sueltos.
    document.addEventListener('click', function (evento) {
        const elemento = evento.target.closest && evento.target.closest('[data-confirmar]');
        if (!elemento || elemento.tagName === 'FORM') return;

        if (elemento.dataset.zbConfirmado === 'true') return;

        evento.preventDefault();
        evento.stopImmediatePropagation();

        confirmar(opcionesDesde(elemento)).then(function (acepto) {
            if (!acepto) return;

            if (elemento.tagName === 'A') {
                if (elemento.target && elemento.target !== '_self') {
                    window.open(elemento.href, elemento.target);
                } else {
                    window.location.href = elemento.href;
                }
                return;
            }

            const formulario = elemento.form;
            const esSubmit = formulario && (elemento.type === 'submit' || elemento.tagName === 'BUTTON' && !elemento.hasAttribute('type'));

            if (esSubmit) {
                enviarFormulario(formulario, elemento);
            } else {
                elemento.dataset.zbConfirmado = 'true';
                elemento.click();
                setTimeout(function () { delete elemento.dataset.zbConfirmado; }, 0);
            }
        });
    }, true);

    /* BURBUJA DE VALIDACIÓN (reemplaza la del navegador) */

    let burbuja = null;
    let campoActual = null;
    let temporizadorBurbuja = null;
    let validacionDelUsuario = false;
    let yaMostrada = false;

    function marcarValidacionDelUsuario() {
        validacionDelUsuario = true;
        yaMostrada = false;
        setTimeout(function () {
            validacionDelUsuario = false;
            yaMostrada = false;
        }, 0);
    }

    // El mensaje solo se muestra cuando la persona intenta enviar
    // el formulario (no cuando el código llama a checkValidity()).
    document.addEventListener('click', function (evento) {
        const control = evento.target.closest && evento.target.closest('button, input');
        if (!control || !control.form) return;

        const tipo = (control.getAttribute('type') || (control.tagName === 'BUTTON' ? 'submit' : '')).toLowerCase();
        if (tipo === 'submit' || tipo === 'image') marcarValidacionDelUsuario();
    }, true);

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Enter' && evento.target && evento.target.form) marcarValidacionDelUsuario();
    }, true);

    ['requestSubmit'].forEach(function (nombre) {
        const original = HTMLFormElement.prototype[nombre];
        if (typeof original !== 'function') return;

        HTMLFormElement.prototype[nombre] = function () {
            marcarValidacionDelUsuario();
            return original.apply(this, arguments);
        };
    });

    [HTMLInputElement, HTMLSelectElement, HTMLTextAreaElement].forEach(function (Clase) {
        const original = Clase.prototype.reportValidity;
        if (typeof original !== 'function') return;

        Clase.prototype.reportValidity = function () {
            marcarValidacionDelUsuario();
            return original.apply(this, arguments);
        };
    });

    function mensajeDeValidacion(campo) {
        const v = campo.validity;
        const tipo = (campo.type || '').toLowerCase();

        if (v.customError) return campo.validationMessage;

        if (v.valueMissing) {
            if (tipo === 'checkbox') return 'Marcá esta casilla para continuar.';
            if (tipo === 'radio' || campo.tagName === 'SELECT') return 'Elegí una opción.';
            if (tipo === 'file') return 'Seleccioná un archivo.';
            return 'Completá este campo.';
        }

        if (v.typeMismatch) {
            if (tipo === 'email') return 'Ingresá un email válido.';
            if (tipo === 'url') return 'Ingresá una dirección web válida.';
            return 'El valor ingresado no es válido.';
        }

        if (v.patternMismatch) return campo.title || 'El formato ingresado no es válido.';
        if (v.tooShort) return 'Usá al menos ' + campo.minLength + ' caracteres.';
        if (v.tooLong) return 'Usá como máximo ' + campo.maxLength + ' caracteres.';
        if (v.rangeUnderflow) return 'El valor debe ser mayor o igual a ' + campo.min + '.';
        if (v.rangeOverflow) return 'El valor debe ser menor o igual a ' + campo.max + '.';
        if (v.stepMismatch || v.badInput) return 'Ingresá un valor válido.';

        return campo.validationMessage || 'Revisá este campo.';
    }

    function ocultarBurbuja() {
        clearTimeout(temporizadorBurbuja);

        if (campoActual) {
            campoActual.classList.remove('zb-campo-invalido');
            campoActual = null;
        }

        if (burbuja) {
            const quitar = burbuja;
            burbuja = null;
            quitar.classList.remove('zb-visible');
            setTimeout(function () { quitar.remove(); }, 160);
        }

        window.removeEventListener('scroll', reposicionar, true);
        window.removeEventListener('resize', reposicionar);
    }

    function reposicionar() {
        if (!burbuja || !campoActual || burbuja.classList.contains('zb-burbuja--aviso')) return;

        const campo = campoActual.getBoundingClientRect();
        const ancho = burbuja.offsetWidth;
        const alto = burbuja.offsetHeight;
        const margen = 8;

        let izquierda = Math.min(Math.max(campo.left, margen), window.innerWidth - ancho - margen);
        let arriba = campo.bottom + 10;
        let abajo = true;

        if (arriba + alto > window.innerHeight - margen && campo.top - alto - 10 > margen) {
            arriba = campo.top - alto - 10;
            abajo = false;
        }

        burbuja.style.left = izquierda + 'px';
        burbuja.style.top = arriba + 'px';
        burbuja.style.setProperty('--zb-flecha-x', Math.max(14, Math.min(campo.left - izquierda + 18, ancho - 24)) + 'px');
        burbuja.classList.toggle('zb-burbuja--abajo', abajo);
        burbuja.classList.toggle('zb-burbuja--arriba', !abajo);
    }

    function mostrarBurbuja(campo) {
        ocultarBurbuja();

        const visible = campo.getClientRects().length > 0;

        burbuja = crearElemento('div', 'zb-burbuja' + (visible ? '' : ' zb-burbuja--aviso'));
        burbuja.setAttribute('role', 'alert');

        const icono = crearElemento('span', 'zb-burbuja__icono');
        icono.innerHTML = ICONO_ERROR;
        burbuja.appendChild(icono);
        burbuja.appendChild(crearElemento('span', '', mensajeDeValidacion(campo)));
        document.body.appendChild(burbuja);

        if (visible) {
            campoActual = campo;
            campo.classList.add('zb-campo-invalido');

            try { campo.focus({ preventScroll: true }); } catch (e) { /* nada */ }
            campo.scrollIntoView({ block: 'center', behavior: 'auto' });

            reposicionar();
            window.addEventListener('scroll', reposicionar, true);
            window.addEventListener('resize', reposicionar);

            const limpiar = function () {
                campo.removeEventListener('input', limpiar);
                campo.removeEventListener('change', limpiar);
                campo.removeEventListener('blur', limpiar);
                if (campoActual === campo) ocultarBurbuja();
            };

            campo.addEventListener('input', limpiar);
            campo.addEventListener('change', limpiar);
            campo.addEventListener('blur', limpiar);
        }

        requestAnimationFrame(function () {
            if (burbuja) burbuja.classList.add('zb-visible');
        });

        temporizadorBurbuja = setTimeout(ocultarBurbuja, 6000);
    }

    document.addEventListener('invalid', function (evento) {
        if (!validacionDelUsuario) return;

        // Evita la burbuja del navegador.
        evento.preventDefault();

        // Solo el primer campo inválido de cada intento.
        if (yaMostrada) return;
        yaMostrada = true;

        mostrarBurbuja(evento.target);
    }, true);

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && burbuja) ocultarBurbuja();
    });
})();
