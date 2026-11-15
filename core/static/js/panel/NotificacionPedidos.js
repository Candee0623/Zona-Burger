/*
 * Aviso con sonido de PEDIDOS NUEVOS (Zona Burger).
 *
 * Funciona en todas las pantallas del panel (se carga desde panel/base.html),
 * así que se escucha aunque la persona esté en Stock, Menú, Reportes, etc.,
 * o en otra pestaña del navegador.
 *
 * - Consulta cada pocos segundos un endpoint liviano (pedidos_nuevos_api).
 * - Suena SOLO cuando entra un pedido nuevo (un id mayor al último visto).
 *   Un cambio de estado de un pedido existente no hace sonar nada.
 * - Con varias pestañas del panel abiertas, el sonido se reparte entre ellas
 *   (localStorage) para que no suene duplicado.
 *
 * Nota sobre el sonido: los navegadores no dejan reproducir audio hasta que la
 * persona interactúa con la página (clic o tecla). Por eso aparece el botón
 * "Activar sonido de pedidos" hasta que se hace el primer clic en cada pantalla.
 */
(function () {
    'use strict';

    var config = document.getElementById('zb-notif-config');
    if (!config) { return; }

    var URL_API = config.getAttribute('data-url');
    var URL_PANEL = config.getAttribute('data-panel') || '/panel/';
    if (!URL_API) { return; }

    var INTERVALO_MS = 5000;
    var CLAVE_ULTIMO = 'zb_ultimo_pedido_visto';
    var CLAVE_SILENCIO = 'zb_sonido_pedidos_silenciado';
    var VIGENCIA_BASE_MS = 10 * 60 * 1000;
    var TITULO_ORIGINAL = document.title;

    var ultimoVisto = null;
    var consultando = false;
    var repetirConsulta = false;
    var detenido = false;
    var audio = null;
    var parpadeo = null;
    var chip = null;
    var contenedorAvisos = null;

    /* ---------- almacenamiento (puede fallar en modo privado) ---------- */

    function leerUltimo() {
        try {
            var crudo = window.localStorage.getItem(CLAVE_ULTIMO);
            if (!crudo) { return null; }
            var dato = JSON.parse(crudo);
            if (dato && typeof dato.id === 'number' && typeof dato.t === 'number') {
                return dato;
            }
        } catch (e) { /* se ignora */ }
        return null;
    }

    function guardarUltimo(id) {
        try {
            window.localStorage.setItem(
                CLAVE_ULTIMO,
                JSON.stringify({ id: id, t: Date.now() })
            );
        } catch (e) { /* se ignora */ }
    }

    function estaSilenciado() {
        try {
            return window.localStorage.getItem(CLAVE_SILENCIO) === '1';
        } catch (e) {
            return false;
        }
    }

    function guardarSilencio(valor) {
        try {
            if (valor) {
                window.localStorage.setItem(CLAVE_SILENCIO, '1');
            } else {
                window.localStorage.removeItem(CLAVE_SILENCIO);
            }
        } catch (e) { /* se ignora */ }
    }

    /* ---------- sonido ---------- */

    function crearAudio() {
        if (audio) { return audio; }
        var Clase = window.AudioContext || window.webkitAudioContext;
        if (!Clase) { return null; }
        try {
            audio = new Clase();
        } catch (e) {
            audio = null;
        }
        return audio;
    }

    function sonidoDisponible() {
        return !!(audio && audio.state === 'running');
    }

    function intentarDesbloquear() {
        var ctx = crearAudio();
        if (!ctx) { return; }
        if (ctx.state === 'suspended') {
            var promesa = ctx.resume();
            if (promesa && promesa.then) {
                promesa.then(actualizarChip, function () { /* sigue bloqueado */ });
            }
        }
        actualizarChip();
    }

    function tono(ctx, frecuencia, inicio, duracion, volumen) {
        var osc = ctx.createOscillator();
        var ganancia = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(frecuencia, inicio);

        ganancia.gain.setValueAtTime(0.0001, inicio);
        ganancia.gain.exponentialRampToValueAtTime(volumen, inicio + 0.02);
        ganancia.gain.exponentialRampToValueAtTime(0.0001, inicio + duracion);

        osc.connect(ganancia);
        ganancia.connect(ctx.destination);
        osc.start(inicio);
        osc.stop(inicio + duracion + 0.05);
    }

    /* Campanita de dos notas; "repeticiones" veces. */
    function reproducirCampana(repeticiones) {
        if (!sonidoDisponible()) { return false; }
        try {
            var base = audio.currentTime + 0.05;
            for (var i = 0; i < repeticiones; i++) {
                var t = base + i * 1.0;
                tono(audio, 880, t, 0.55, 0.55);
                tono(audio, 1318.5, t + 0.3, 0.75, 0.55);
            }
            return true;
        } catch (e) {
            return false;
        }
    }

    /* ---------- botón de sonido ---------- */

    function crearChip() {
        chip = document.createElement('button');
        chip.type = 'button';
        chip.id = 'zb-sonido-chip';
        chip.className = 'zb-sonido-chip';
        chip.addEventListener('click', alHacerClicEnChip);
        document.body.appendChild(chip);
        actualizarChip();
    }

    function actualizarChip() {
        if (!chip) { return; }

        var texto;
        var estado;

        if (!sonidoDisponible()) {
            estado = 'bloqueado';
            texto = 'Activar sonido de pedidos';
            chip.title = 'Hacé clic para que suene el aviso cuando entre un pedido';
        } else if (estaSilenciado()) {
            estado = 'silenciado';
            texto = 'Sonido silenciado';
            chip.title = 'Clic para volver a activar el sonido de pedidos';
        } else {
            estado = 'activo';
            texto = 'Sonido de pedidos activo';
            chip.title = 'Clic para silenciar el aviso de pedidos';
        }

        chip.setAttribute('data-estado', estado);
        chip.innerHTML = '';

        var icono = document.createElement('i');
        icono.className = 'fa-solid ' + (estado === 'activo' ? 'fa-bell' : (estado === 'silenciado' ? 'fa-bell-slash' : 'fa-volume-xmark'));
        icono.setAttribute('aria-hidden', 'true');

        var etiqueta = document.createElement('span');
        etiqueta.textContent = texto;

        chip.appendChild(icono);
        chip.appendChild(etiqueta);
    }

    function pedirPermisoNotificaciones() {
        try {
            if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission();
            }
        } catch (e) { /* se ignora */ }
    }

    function alHacerClicEnChip() {
        if (!sonidoDisponible()) {
            var ctx = crearAudio();
            if (!ctx) { return; }
            var promesa = ctx.resume();
            var despues = function () {
                actualizarChip();
                if (!estaSilenciado()) { reproducirCampana(1); }
            };
            if (promesa && promesa.then) {
                promesa.then(despues, actualizarChip);
            } else {
                despues();
            }
            pedirPermisoNotificaciones();
            return;
        }

        if (estaSilenciado()) {
            guardarSilencio(false);
            actualizarChip();
            reproducirCampana(1);
        } else {
            guardarSilencio(true);
            actualizarChip();
        }
    }

    /* El navegador pide un gesto de la persona: el primero desbloquea el audio. */
    function alPrimerGesto(evento) {
        // El clic en el propio botón ya se encarga de activar el sonido.
        if (evento && chip && evento.target && chip.contains(evento.target)) { return; }
        intentarDesbloquear();
        if (sonidoDisponible()) {
            document.removeEventListener('pointerdown', alPrimerGesto, true);
            document.removeEventListener('keydown', alPrimerGesto, true);
            document.removeEventListener('touchend', alPrimerGesto, true);
        }
    }

    /* ---------- avisos en pantalla ---------- */

    function formatoDinero(valor) {
        if (typeof valor !== 'number') { return ''; }
        try {
            return valor.toLocaleString('es-AR', {
                style: 'currency',
                currency: 'ARS',
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        } catch (e) {
            return '$ ' + valor.toFixed(2);
        }
    }

    function textoDePedido(pedido) {
        var partes = [pedido.cliente || 'Cliente'];
        var dinero = formatoDinero(pedido.total);
        if (dinero) { partes.push(dinero); }
        if (pedido.hora) { partes.push(pedido.hora + ' hs'); }
        return partes.join(' · ');
    }

    function asegurarContenedor() {
        if (contenedorAvisos) { return contenedorAvisos; }
        contenedorAvisos = document.createElement('div');
        contenedorAvisos.id = 'zb-avisos-pedidos';
        contenedorAvisos.className = 'zb-avisos-pedidos';
        contenedorAvisos.setAttribute('aria-live', 'assertive');
        document.body.appendChild(contenedorAvisos);
        return contenedorAvisos;
    }

    function mostrarTarjeta(titulo, detalle) {
        var cont = asegurarContenedor();

        var tarjeta = document.createElement('div');
        tarjeta.className = 'zb-aviso-pedido';
        tarjeta.setAttribute('role', 'alert');

        var icono = document.createElement('div');
        icono.className = 'zb-aviso-icono';
        icono.innerHTML = '<i class="fa-solid fa-bell" aria-hidden="true"></i>';

        var cuerpo = document.createElement('div');
        cuerpo.className = 'zb-aviso-cuerpo';

        var t = document.createElement('strong');
        t.textContent = titulo;
        cuerpo.appendChild(t);

        if (detalle) {
            var d = document.createElement('span');
            d.textContent = detalle;
            cuerpo.appendChild(d);
        }

        var enlace = document.createElement('a');
        enlace.href = URL_PANEL;
        enlace.className = 'zb-aviso-enlace';
        enlace.textContent = 'Ver pedidos';
        cuerpo.appendChild(enlace);

        var cerrar = document.createElement('button');
        cerrar.type = 'button';
        cerrar.className = 'zb-aviso-cerrar';
        cerrar.setAttribute('aria-label', 'Cerrar aviso');
        cerrar.innerHTML = '&times;';

        function quitar() {
            if (tarjeta.parentNode) { tarjeta.parentNode.removeChild(tarjeta); }
        }
        cerrar.addEventListener('click', quitar);

        tarjeta.appendChild(icono);
        tarjeta.appendChild(cuerpo);
        tarjeta.appendChild(cerrar);
        cont.appendChild(tarjeta);

        // Máximo 4 avisos apilados.
        while (cont.children.length > 4) {
            cont.removeChild(cont.firstChild);
        }

        window.setTimeout(quitar, 20000);
    }

    function iniciarParpadeoDeTitulo(texto) {
        if (!document.hidden) { return; }
        detenerParpadeo(false);

        var alterna = false;
        parpadeo = window.setInterval(function () {
            alterna = !alterna;
            document.title = alterna ? texto : TITULO_ORIGINAL;
        }, 1000);
    }

    function detenerParpadeo(restaurar) {
        if (parpadeo) {
            window.clearInterval(parpadeo);
            parpadeo = null;
        }
        if (restaurar !== false) {
            document.title = TITULO_ORIGINAL;
        }
    }

    function notificacionDelSistema(titulo, detalle) {
        try {
            if (!('Notification' in window)) { return; }
            if (Notification.permission !== 'granted') { return; }
            if (!document.hidden) { return; }

            var n = new Notification(titulo, {
                body: detalle || '',
                tag: 'zb-pedido-nuevo',
                renotify: true
            });
            n.onclick = function () {
                try { window.focus(); } catch (e) { /* se ignora */ }
                n.close();
            };
        } catch (e) { /* se ignora */ }
    }

    function avisarPedidosNuevos(datos, hacerSonar) {
        var nuevos = datos.nuevos || [];
        var cantidad = datos.cantidad || nuevos.length || 1;

        var titulo;
        var detalle;

        if (cantidad === 1 && nuevos.length === 1) {
            titulo = 'Nuevo pedido #' + nuevos[0].id;
            detalle = textoDePedido(nuevos[0]);
        } else {
            titulo = cantidad + ' pedidos nuevos';
            detalle = nuevos.length
                ? nuevos.map(function (p) { return '#' + p.id; }).join(', ')
                : '';
        }

        mostrarTarjeta(titulo, detalle);
        iniciarParpadeoDeTitulo('🔔 ' + titulo);
        notificacionDelSistema(titulo, detalle);

        if (hacerSonar) {
            reproducirCampana(3);
        }

        document.dispatchEvent(new CustomEvent('zb:pedido-nuevo', { detail: datos }));
    }

    /* ---------- consulta al servidor ---------- */

    function consultar() {
        if (detenido || consultando) { return; }
        consultando = true;

        var url = URL_API;
        if (ultimoVisto !== null) {
            url += (url.indexOf('?') === -1 ? '?' : '&') + 'desde=' + encodeURIComponent(ultimoVisto);
        }

        fetch(url, {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
            credentials: 'same-origin',
            cache: 'no-store'
        })
            .then(function (respuesta) {
                if (respuesta.status === 401 || respuesta.status === 403) {
                    // Sin sesión o sin permiso: no tiene sentido seguir consultando.
                    detenido = true;
                    return null;
                }
                if (!respuesta.ok) { return null; }
                return respuesta.json();
            })
            .then(function (datos) {
                if (!datos || typeof datos.ultimo_id !== 'number') { return; }
                procesarRespuesta(datos);
            })
            .catch(function () { /* sin conexión: se reintenta en el próximo ciclo */ })
            .then(function () {
                consultando = false;
                if (repetirConsulta) {
                    repetirConsulta = false;
                    consultar();
                }
            });
    }

    function procesarRespuesta(datos) {
        var ultimo = datos.ultimo_id;

        // Punto de partida: no se avisa por pedidos que ya existían al abrir la página.
        if (ultimoVisto === null) {
            var guardado = leerUltimo();
            var vigente = guardado && (Date.now() - guardado.t) < VIGENCIA_BASE_MS && guardado.id <= ultimo;
            ultimoVisto = vigente ? guardado.id : ultimo;

            if (ultimo > ultimoVisto) {
                // Entró un pedido mientras se cambiaba de pantalla: se vuelve a
                // consultar enseguida (ya con "desde") para avisarlo.
                repetirConsulta = true;
                return;
            }
            guardarUltimo(ultimoVisto);
            return;
        }

        if (ultimo > ultimoVisto) {
            var guardadoAhora = leerUltimo();
            var yaAvisadoPorOtraPestana = guardadoAhora && guardadoAhora.id >= ultimo;
            var puedeSonar = sonidoDisponible() && !estaSilenciado();
            var sonar = false;

            if (!yaAvisadoPorOtraPestana && puedeSonar) {
                guardarUltimo(ultimo);
                sonar = true;
            }

            ultimoVisto = ultimo;
            avisarPedidosNuevos(datos, sonar);
            return;
        }

        // Sin pedidos nuevos: se renueva la marca para que las demás pestañas
        // sepan que esta sigue al día.
        var actual = leerUltimo();
        guardarUltimo(Math.max(ultimoVisto, actual ? actual.id : 0));
    }

    /* ---------- reloj de consulta (no se frena tanto en segundo plano) ---------- */

    function iniciarReloj() {
        var respaldo = null;

        function usarIntervalo() {
            if (!respaldo) { respaldo = window.setInterval(consultar, INTERVALO_MS); }
        }

        try {
            var codigo = 'setInterval(function(){postMessage(1);},' + INTERVALO_MS + ');';
            var blob = new Blob([codigo], { type: 'application/javascript' });
            var enlace = window.URL.createObjectURL(blob);
            var trabajador = new Worker(enlace);
            trabajador.onmessage = consultar;
            trabajador.onerror = function () {
                try { trabajador.terminate(); } catch (e) { /* se ignora */ }
                usarIntervalo();
            };
        } catch (e) {
            usarIntervalo();
        }
    }

    /* ---------- arranque ---------- */

    function arrancar() {
        crearChip();

        document.addEventListener('pointerdown', alPrimerGesto, true);
        document.addEventListener('keydown', alPrimerGesto, true);
        document.addEventListener('touchend', alPrimerGesto, true);

        // Si el navegador ya permite audio (clic previo), queda activo solo.
        intentarDesbloquear();

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) {
                detenerParpadeo(true);
                intentarDesbloquear();
                consultar();
            }
        });
        window.addEventListener('focus', function () {
            detenerParpadeo(true);
        });
        window.addEventListener('online', consultar);

        consultar();
        iniciarReloj();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();