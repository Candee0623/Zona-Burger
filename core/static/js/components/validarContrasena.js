/*
 * Validación de contraseñas en tiempo real (Zona Burger).
 *
 * Uso: agregar data-validar-contrasena al <form> y marcar los campos con
 *   data-pw-nueva       -> campo de la contraseña nueva
 *   data-pw-confirmar   -> campo de confirmación (opcional)
 *   data-pw-actual      -> campo de contraseña actual (opcional, solo al cambiarla)
 * Atributos opcionales del <form>:
 *   data-pw-opcional    -> la contraseña puede quedar vacía (ej.: editar usuario)
 * Si dentro del form hay un elemento [data-pw-reglas], ahí se dibuja la lista
 * de requisitos; si no, se agrega debajo del campo de contraseña nueva.
 *
 * Estas reglas replican las de _error_contrasena_nueva() en views.py.
 * El servidor siempre vuelve a validar.
 */
(function () {
    'use strict';

    var SECUENCIAS = [
        '0123456789',
        'abcdefghijklmnopqrstuvwxyz',
        'qwertyuiop',
        'asdfghjkl',
        'zxcvbnm'
    ];

    function tieneSecuenciaFacil(texto) {
        var minus = texto.toLowerCase();
        for (var s = 0; s < SECUENCIAS.length; s++) {
            var direcciones = [SECUENCIAS[s], SECUENCIAS[s].split('').reverse().join('')];
            for (var d = 0; d < direcciones.length; d++) {
                var tramo = direcciones[d];
                for (var i = 0; i <= tramo.length - 4; i++) {
                    if (minus.indexOf(tramo.substr(i, 4)) !== -1) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    function cantidadDistintos(texto) {
        var vistos = {};
        var total = 0;
        var chars = Array.from(texto.toLowerCase());
        for (var i = 0; i < chars.length; i++) {
            if (!vistos[chars[i]]) {
                vistos[chars[i]] = true;
                total++;
            }
        }
        return total;
    }

    var REGLAS = [
        {
            id: 'largo',
            texto: 'Entre 8 y 128 caracteres',
            cumple: function (p) { return p.length >= 8 && p.length <= 128; }
        },
        {
            id: 'mayuscula',
            texto: 'Al menos una letra mayúscula (A-Z)',
            cumple: function (p) { return /\p{Lu}/u.test(p); }
        },
        {
            id: 'minuscula',
            texto: 'Al menos una letra minúscula (a-z)',
            cumple: function (p) { return /\p{Ll}/u.test(p); }
        },
        {
            id: 'numero',
            texto: 'Al menos un número (0-9)',
            cumple: function (p) { return /\p{Nd}/u.test(p); }
        },
        {
            id: 'simbolo',
            texto: 'Al menos un símbolo (por ejemplo ! # $ % & *)',
            cumple: function (p) { return /[^\p{L}\p{N}\s]/u.test(p); }
        },
        {
            id: 'espacios',
            texto: 'Sin espacios',
            cumple: function (p) { return !/\s/.test(p); }
        },
        {
            id: 'variedad',
            texto: 'Al menos 5 caracteres distintos',
            cumple: function (p) { return cantidadDistintos(p) >= 5; }
        },
        {
            id: 'secuencia',
            texto: 'Sin secuencias fáciles (1234, abcd, qwer...)',
            cumple: function (p) { return !tieneSecuenciaFacil(p); }
        }
    ];

    function crear(tag, clase, texto) {
        var el = document.createElement(tag);
        if (clase) { el.className = clase; }
        if (texto) { el.textContent = texto; }
        return el;
    }

    function contenedorDe(input) {
        return input.closest('.form-group, .crear-empleado-grupo, .empleado-form-group') || input.parentNode;
    }

    function mensajeBajo(input) {
        var contenedor = contenedorDe(input);
        var msg = crear('p', 'pw-mensaje');
        msg.setAttribute('aria-live', 'polite');
        contenedor.appendChild(msg);
        return msg;
    }

    function marcar(input, estado) {
        input.classList.remove('pw-campo-ok', 'pw-campo-error');
        if (estado === 'ok') { input.classList.add('pw-campo-ok'); }
        if (estado === 'error') { input.classList.add('pw-campo-error'); }
        input.setAttribute('aria-invalid', estado === 'error' ? 'true' : 'false');
    }

    function mostrar(msg, estado, texto) {
        msg.textContent = texto || '';
        msg.className = 'pw-mensaje' + (estado ? ' pw-mensaje-' + estado : '');
    }

    function iniciar(form) {
        var nueva = form.querySelector('[data-pw-nueva]');
        if (!nueva) { return; }

        var confirmar = form.querySelector('[data-pw-confirmar]');
        var actual = form.querySelector('[data-pw-actual]');
        var opcional = form.hasAttribute('data-pw-opcional');
        var boton = form.querySelector('button[type="submit"], input[type="submit"]');

        /* Lista de requisitos */
        var reglasDestino = form.querySelector('[data-pw-reglas]');
        if (!reglasDestino) {
            reglasDestino = crear('div');
            contenedorDe(nueva).appendChild(reglasDestino);
        }
        reglasDestino.classList.add('pw-reglas-caja');

        var titulo = crear('p', 'pw-reglas-titulo', 'La contraseña debe tener:');
        var lista = crear('ul', 'pw-reglas');
        lista.setAttribute('aria-live', 'polite');
        var items = {};
        var reglas = REGLAS.slice();

        if (actual) {
            reglas.push({
                id: 'distinta',
                texto: 'Ser distinta de tu contraseña actual',
                cumple: function (p) { return p !== actual.value; }
            });
        }

        reglas.forEach(function (regla) {
            var li = crear('li', 'pw-regla');
            li.setAttribute('data-estado', 'pendiente');
            li.appendChild(crear('span', 'pw-regla-icono'));
            li.appendChild(crear('span', 'pw-regla-texto', regla.texto));
            lista.appendChild(li);
            items[regla.id] = li;
        });

        reglasDestino.appendChild(titulo);
        reglasDestino.appendChild(lista);

        var resumen = crear('p', 'pw-resumen');
        resumen.setAttribute('role', 'alert');
        reglasDestino.appendChild(resumen);

        var msgNueva = null;
        var msgConfirmar = confirmar ? mensajeBajo(confirmar) : null;
        var msgActual = actual ? mensajeBajo(actual) : null;
        var actualTocado = false;

        function evaluar() {
            var p = nueva.value;
            var c = confirmar ? confirmar.value : '';
            var vacioPermitido = opcional && p === '' && c === '';
            var escribio = p.length > 0;
            var todasOk = true;
            var primerErrorCampo = null;

            /* Requisitos de la contraseña nueva */
            reglas.forEach(function (regla) {
                var ok = regla.cumple(p);
                if (!ok) { todasOk = false; }
                var estado = 'pendiente';
                if (escribio) { estado = ok ? 'ok' : 'error'; }
                items[regla.id].setAttribute('data-estado', estado);
            });

            if (!escribio) {
                todasOk = vacioPermitido;
                marcar(nueva, null);
            } else {
                marcar(nueva, todasOk ? 'ok' : 'error');
                if (!todasOk) { primerErrorCampo = primerErrorCampo || nueva; }
            }

            /* Confirmación */
            var coincide = true;
            if (confirmar) {
                if (c === '' && p === '') {
                    coincide = vacioPermitido;
                    marcar(confirmar, null);
                    mostrar(msgConfirmar, null, '');
                } else if (c === '') {
                    coincide = false;
                    marcar(confirmar, null);
                    mostrar(msgConfirmar, null, '');
                } else if (c !== p) {
                    coincide = false;
                    marcar(confirmar, 'error');
                    mostrar(msgConfirmar, 'error', 'Las contraseñas no coinciden.');
                    primerErrorCampo = primerErrorCampo || confirmar;
                } else {
                    marcar(confirmar, 'ok');
                    mostrar(msgConfirmar, 'ok', 'Las contraseñas coinciden.');
                }
            }

            /* Contraseña actual (solo al cambiarla) */
            var actualOk = true;
            if (actual) {
                if (actual.value === '') {
                    actualOk = false;
                    if (actualTocado) {
                        marcar(actual, 'error');
                        mostrar(msgActual, 'error', 'Ingresá tu contraseña actual.');
                        primerErrorCampo = primerErrorCampo || actual;
                    } else {
                        marcar(actual, null);
                        mostrar(msgActual, null, '');
                    }
                } else {
                    marcar(actual, null);
                    mostrar(msgActual, null, '');
                }
            }

            var valido = todasOk && coincide && actualOk;

            if (boton) {
                boton.disabled = !valido;
                boton.setAttribute('aria-disabled', valido ? 'false' : 'true');
            }
            if (valido) { resumen.textContent = ''; }

            return { valido: valido, primerError: primerErrorCampo };
        }

        ['input', 'change', 'keyup'].forEach(function (evento) {
            nueva.addEventListener(evento, evaluar);
            if (confirmar) { confirmar.addEventListener(evento, evaluar); }
            if (actual) { actual.addEventListener(evento, evaluar); }
        });

        if (actual) {
            actual.addEventListener('blur', function () {
                actualTocado = true;
                evaluar();
            });
        }

        form.addEventListener('submit', function (evento) {
            var resultado = evaluar();
            if (!resultado.valido) {
                evento.preventDefault();
                if (actual && actual.value === '') {
                    actualTocado = true;
                    evaluar();
                }
                resumen.textContent = 'Revisá los requisitos marcados en rojo antes de continuar.';
                var foco = resultado.primerError || (actual && actual.value === '' ? actual : nueva);
                if (foco) { foco.focus(); }
            }
        });

        evaluar();
        /* Gestores de contraseñas y autocompletado pueden rellenar sin disparar eventos */
        window.setTimeout(evaluar, 300);
        window.addEventListener('load', evaluar);
    }

    function arrancar() {
        var forms = document.querySelectorAll('form[data-validar-contrasena]');
        for (var i = 0; i < forms.length; i++) { iniciar(forms[i]); }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
