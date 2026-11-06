'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const INTERVALO_ESTADO = 3000;
    const ENDPOINT_ESTADO = '/api/carrito/estado/';
    const ENDPOINT_ACCION = '/api/carrito/accion/';

    const raiz = document.getElementById('carrito-contenido');
    const avisoCierre = document.getElementById('aviso-negocio-cerrado');
    const zonaAvisos = document.getElementById('carrito-avisos');
    if (!raiz) return;

    const urlMenu = raiz.dataset.menuUrl;
    const urlCheckout = raiz.dataset.checkoutUrl;

    let anterior = null;     // último estado recibido
    let temporizador = null;
    let enCurso = false;
    let secuencia = 0;       // sube con cada acción del usuario

    // ---------- utilidades ----------
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));

    const money = (n) => '$' + Number(n).toLocaleString('es-AR', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    });

    const csrf = () =>
        (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';

    function toast(texto, tipo) {
        if (!zonaAvisos) return;
        const colores = {
            info: ['rgba(59,130,246,.18)', '#93c5fd'],
            ok: ['rgba(34,197,94,.18)', '#86efac'],
            warn: ['rgba(234,179,8,.18)', '#fde047'],
            error: ['rgba(220,38,38,.2)', '#fca5a5']
        };
        const [bg, fg] = colores[tipo] || colores.info;
        const el = document.createElement('div');
        el.style.cssText = `padding:12px 14px;border-radius:8px;font-size:.82rem;font-weight:600;
            background:${bg};border:1px solid ${fg}55;color:${fg};backdrop-filter:blur(6px);
            box-shadow:0 8px 24px rgba(0,0,0,.4)`;
        el.textContent = texto;
        zonaAvisos.appendChild(el);
        setTimeout(() => el.remove(), 7000);
    }

    // ---------- render ----------
    function htmlItem(it) {
        const detalles = (it.detalles && it.detalles.length)
            ? `<ul class="carrito-detalles-lista">${it.detalles.map(d => `<li>${esc(d)}</li>`).join('')}</ul>`
            : '';
        return `
        <div class="carrito-item" data-item-id="${esc(it.id)}">
            <div class="carrito-info">
                <h3>${esc(it.nombre)}</h3>
                ${detalles}
                <div class="carrito-acciones">
                    <div class="cantidad-control">
                        <a href="#" data-accion="disminuir" data-item="${esc(it.id)}" class="btn-cant" aria-label="Disminuir cantidad">-</a>
                        <span class="cantidad-val">${it.cantidad}</span>
                        <a href="#" data-accion="aumentar" data-item="${esc(it.id)}" class="btn-cant" aria-label="Aumentar cantidad">+</a>
                    </div>
                    <a href="${esc(it.url_editar)}" class="btn-editar-item"><i class="fa-solid fa-pen"></i> Editar</a>
                    <a href="#" data-accion="eliminar" data-item="${esc(it.id)}" class="btn-eliminar-item"><i class="fa-solid fa-trash"></i> Eliminar</a>
                </div>
            </div>
            <div class="carrito-precio-col">
                <span class="carrito-unitario-ref">${money(it.precio_unitario)} c/u</span>
                <span class="carrito-subtotal-item">${money(it.subtotal)}</span>
            </div>
        </div>`;
    }

    function htmlCarrito(data) {
        if (!data.items.length) {
            return `
            <div class="carrito-card carrito-vacio">
                <div class="carrito-vacio-icono"><i class="fa-solid fa-cart-shopping"></i></div>
                <p>Tu carrito está vacío.</p>
                <a href="${esc(urlMenu)}" class="btn-checkout">Ver Menú</a>
            </div>`;
        }
        return `
        <div class="carrito-card">
            ${data.items.map(htmlItem).join('')}
            <div class="carrito-resumen-totales">
                <div class="resumen-linea"><span>Subtotal:</span><span>${money(data.total)}</span></div>
                <div class="resumen-linea total-final"><span>A Pagar:</span><span>${money(data.total)}</span></div>
            </div>
            <div class="carrito-botones-accion">
                <a href="${esc(urlMenu)}" class="btn-seguir">Seguir Comprando</a>
                <button type="button" id="btn-checkout" class="btn-checkout">
                    <i class="fa-solid fa-arrow-right" style="margin-right:8px" aria-hidden="true"></i>
                    <span data-texto-boton>Ir al Checkout</span>
                </button>
            </div>
        </div>`;
    }

    function aplicarBoton(abierto) {
        const btn = document.getElementById('btn-checkout');
        if (!btn) return;
        const texto = btn.querySelector('[data-texto-boton]');
        const icono = btn.querySelector('i');
        if (texto) texto.textContent = abierto ? 'Ir al Checkout' : 'Negocio Cerrado';
        if (icono) {
            icono.className = abierto ? 'fa-solid fa-arrow-right' : 'fa-solid fa-lock';
            icono.style.marginRight = '8px';
        }
        btn.disabled = !abierto;
        btn.title = abierto ? '' : 'El negocio está cerrado en este momento';
        btn.setAttribute('aria-disabled', String(!abierto));
        btn.style.background = abierto ? '' : '#2a2a2a';
        btn.style.color = abierto ? '' : '#888';
        btn.style.borderColor = abierto ? '' : '#444';
        btn.style.cursor = abierto ? '' : 'not-allowed';
        btn.style.boxShadow = abierto ? '' : 'none';
    }

    // ---------- detectar y avisar cambios ----------
    function avisarCambios(prev, actual) {
        if (prev.abierto !== actual.abierto) {
            actual.abierto
                ? toast('¡El negocio acaba de abrir! Ya podés hacer tu pedido.', 'ok')
                : toast('El negocio acaba de cerrar. Tus productos siguen en el carrito.', 'error');
        }

        const antes = new Map(prev.items.map(i => [i.id, i]));
        const ahora = new Map(actual.items.map(i => [i.id, i]));

        // Los productos quitados por indisponibilidad se avisan con data.quitados.

        ahora.forEach((nuevo, id) => {
            const viejo = antes.get(id);
            if (!viejo) {
                toast(`Se agregó "${nuevo.nombre}" al carrito.`, 'info');
                return;
            }
            if (viejo.nombre !== nuevo.nombre) {
                toast(`"${viejo.nombre}" ahora se llama "${nuevo.nombre}".`, 'info');
            }
            if (viejo.precio_unitario !== nuevo.precio_unitario) {
                toast(`El precio de "${nuevo.nombre}" cambió: ${money(viejo.precio_unitario)} → ${money(nuevo.precio_unitario)}.`, 'warn');
            }
            if (viejo.cantidad !== nuevo.cantidad) {
                toast(`La cantidad de "${nuevo.nombre}" ahora es ${nuevo.cantidad}.`, 'info');
            }
            if (JSON.stringify(viejo.detalles) !== JSON.stringify(nuevo.detalles)) {
                toast(`Se modificaron los detalles de "${nuevo.nombre}".`, 'info');
            }
        });
    }

    function aplicar(data, silencioso) {
        if (avisoCierre) avisoCierre.style.display = data.abierto ? 'none' : 'flex';

        (data.quitados || []).forEach(n =>
            toast(`"${n}" ya no está disponible y se quitó de tu carrito.`, 'warn'));

        if (!anterior || anterior.version !== data.version) {
            if (anterior && !silencioso) avisarCambios(anterior, data);
            raiz.innerHTML = htmlCarrito(data);
        }
        aplicarBoton(data.abierto);
        anterior = data;
    }

    // ---------- sincronización (polling) ----------
    async function sincronizar() {
        if (enCurso || document.hidden) return null;
        enCurso = true;
        const secuenciaInicial = secuencia;
        try {
            const r = await fetch(ENDPOINT_ESTADO, {
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                cache: 'no-store',
                credentials: 'same-origin'
            });
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const data = await r.json();
            if (typeof data.abierto !== 'boolean' || !Array.isArray(data.items)) {
                throw new Error('Respuesta inválida');
            }
            // Si el usuario hizo una acción mientras esperábamos, esta
            // respuesta puede ser vieja: se descarta.
            if (secuenciaInicial !== secuencia) return null;
            aplicar(data);
            return data;
        } catch (e) {
            console.warn('No se pudo actualizar el carrito.', e);
            return null;
        } finally {
            enCurso = false;
        }
    }

    function detener() {
        if (temporizador !== null) { clearInterval(temporizador); temporizador = null; }
    }

    function iniciar() {
        detener();
        if (document.hidden) return;
        sincronizar();
        temporizador = setInterval(sincronizar, INTERVALO_ESTADO);
    }

    // ---------- acciones: +, -, eliminar (sin recargar) ----------
    raiz.addEventListener('click', async function (e) {
        const el = e.target.closest('[data-accion]');
        if (!el) return;
        e.preventDefault();
        if (el.dataset.busy) return;
        el.dataset.busy = '1';
        secuencia++;

        try {
            const body = new URLSearchParams({
                item_id: el.dataset.item,
                accion: el.dataset.accion
            });
            const r = await fetch(ENDPOINT_ACCION, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrf(),
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                },
                body,
                credentials: 'same-origin'
            });
            const data = await r.json();
            secuencia++;
            if (data.error) toast(data.error, 'error');
            if (Array.isArray(data.items)) aplicar(data, true);
        } catch (err) {
            toast('No se pudo actualizar el carrito. Reintentá.', 'error');
        } finally {
            delete el.dataset.busy;
        }
    });

    // ---------- checkout (delegación, porque el botón se redibuja) ----------
    raiz.addEventListener('click', async function (e) {
        const btn = e.target.closest('#btn-checkout');
        if (!btn || btn.disabled) return;

        // Verificar una última vez antes de avanzar.
        const versionPrevia = anterior ? anterior.version : null;
        const data = await sincronizar();

        if (data && !data.abierto) return;
        if (data && versionPrevia && data.version !== versionPrevia) {
            toast('Tu carrito cambió. Revisalo antes de continuar.', 'warn');
            return;
        }
        if (data && !data.items.length) return;

        window.location.href = urlCheckout;
    });

    // ---------- ciclo de vida ----------
    document.addEventListener('visibilitychange', () => document.hidden ? detener() : iniciar());
    window.addEventListener('pageshow', () => { if (!document.hidden) iniciar(); });
    window.addEventListener('pagehide', detener);
    window.addEventListener('focus', () => { if (!document.hidden) sincronizar(); });
    window.addEventListener('online', sincronizar);

    iniciar();
});