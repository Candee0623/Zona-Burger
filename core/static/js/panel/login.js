
const toggleBtn = document.getElementById('togglePassword');
const passwordInput = document.getElementById('password');
const toggleIcon = document.getElementById('togglePasswordIcon');

if (toggleBtn && passwordInput && toggleIcon) {
    toggleBtn.addEventListener('click', function() {
        const isPassword = passwordInput.getAttribute('type') === 'password';
        passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
        toggleIcon.classList.toggle('fa-eye', !isPassword);
        toggleIcon.classList.toggle('fa-eye-slash', isPassword);
    });
}

/* Contador de bloqueo (solo HTML/JS) */

(function () {

    // Debe coincidir con TIEMPO_BLOQUEO_SEGUNDOS de utils.py (900 = 15 min)
    const DURACION_BLOQUEO_SEG = 900;
    const CLAVE = 'zb_login_bloqueo_hasta';

    const caja = document.getElementById('login-bloqueo');
    const texto = document.getElementById('bloqueo-texto');
    const contador = document.getElementById('contador-bloqueo');
    const boton = document.getElementById('btn-ingresar');

    if (!caja || !contador) {
        return;
    }

    function leerFin() {
        try {
            return parseInt(localStorage.getItem(CLAVE), 10) || 0;
        } catch (e) {
            return 0;
        }
    }

    function guardarFin(valor) {
        try {
            localStorage.setItem(CLAVE, String(valor));
        } catch (e) {}
    }

    function borrarFin() {
        try {
            localStorage.removeItem(CLAVE);
        } catch (e) {}
    }

    let fin = leerFin();

    // Si la página trae el mensaje de bloqueo y no hay un bloqueo
    // vigente guardado, se inicia uno nuevo.
    const hayMensajeBloqueo = document.querySelector('[data-bloqueo="true"]');

    if (hayMensajeBloqueo && fin <= Date.now()) {
        fin = Date.now() + DURACION_BLOQUEO_SEG * 1000;
        guardarFin(fin);
    }

    // Sin bloqueo vigente: no se muestra nada.
    if (fin <= Date.now()) {
        borrarFin();
        return;
    }

    caja.hidden = false;

    if (boton) {
        boton.disabled = true;
    }

    function pintar(restantes) {
        const minutos = String(Math.floor(restantes / 60)).padStart(2, '0');
        const segundos = String(restantes % 60).padStart(2, '0');
        contador.textContent = minutos + ':' + segundos;
    }

    function liberar() {
        clearInterval(temporizador);
        borrarFin();

        caja.classList.add('liberado');
        texto.textContent = 'Ya podés intentar de nuevo.';
        contador.style.display = 'none';

        if (boton) {
            boton.disabled = false;
        }
    }

    function actualizar() {
        const restantes = Math.ceil((fin - Date.now()) / 1000);

        if (restantes <= 0) {
            liberar();
            return;
        }

        pintar(restantes);
    }

    const temporizador = setInterval(actualizar, 1000);
    actualizar();

})();
