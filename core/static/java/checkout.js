document.addEventListener('DOMContentLoaded', function () {
  const form = document.querySelector('.checkout-form');
  if (!form) return;

  const mensajes = {
    nombre: 'Ingresá tu nombre.',
    apellido: 'Ingresá tu apellido.',
    telefono_vacio: 'Ingresá tu número de teléfono.',
    telefono_invalido: 'Ingresá un teléfono válido (solo números, entre 8 y 15 dígitos).',
    calle: 'Ingresá la calle.',
    numero: 'Ingresá el número de la calle.',
    localidad: 'Ingresá tu localidad.',
    medio_pago: 'Seleccioná un método de pago.',
  };

  const patronTelefono = /^[0-9\s\-()+]{8,15}$/;

  function mostrarError(campo, mensaje) {
    const errorEl = form.querySelector(`.form-error[data-for="${campo}"]`);
    if (errorEl) {
      errorEl.textContent = mensaje;
      errorEl.style.display = 'block';
    }
    const inputEl = form.querySelector(`[name="${campo}"]`);
    if (inputEl) inputEl.classList.add('input-error');
  }

  function ocultarError(campo) {
    const errorEl = form.querySelector(`.form-error[data-for="${campo}"]`);
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.style.display = 'none';
    }
    const inputEl = form.querySelector(`[name="${campo}"]`);
    if (inputEl) inputEl.classList.remove('input-error');
  }

  form.addEventListener('submit', function (e) {
    let esValido = true;
    let primerCampoInvalido = null;

    // 1. Validar campos de texto requeridos
    const camposTexto = ['nombre', 'apellido', 'calle', 'numero', 'localidad'];
    camposTexto.forEach(function (campo) {
      const input = form.querySelector(`[name="${campo}"]`);
      if (input) {
        if (!input.value.trim()) {
          mostrarError(campo, mensajes[campo]);
          esValido = false;
          if (!primerCampoInvalido) primerCampoInvalido = input;
        } else {
          ocultarError(campo);
        }
      }
    });

    // 2. Validar teléfono
    const telefonoInput = form.querySelector('[name="telefono"]');
    if (telefonoInput) {
      const telefonoValor = telefonoInput.value.trim();
      if (!telefonoValor) {
        mostrarError('telefono', mensajes.telefono_vacio);
        esValido = false;
        if (!primerCampoInvalido) primerCampoInvalido = telefonoInput;
      } else if (!patronTelefono.test(telefonoValor)) {
        mostrarError('telefono', mensajes.telefono_invalido);
        esValido = false;
        if (!primerCampoInvalido) primerCampoInvalido = telefonoInput;
      } else {
        ocultarError('telefono');
      }
    }

    // 3. Validar medio de pago (select)
    const medioPagoSelect = form.querySelector('[name="medio_pago"]');
    if (medioPagoSelect) {
      if (!medioPagoSelect.value) {
        mostrarError('medio_pago', mensajes.medio_pago);
        esValido = false;
        if (!primerCampoInvalido) primerCampoInvalido = medioPagoSelect;
      } else {
        ocultarError('medio_pago');
      }
    }

    // Si hay algún error, frenamos el envío y mandamos el foco al primero que falló
    if (!esValido) {
      e.preventDefault();
      if (primerCampoInvalido) {
        primerCampoInvalido.focus();
      }
    }
  });

  // Limpiar errores en tiempo real mientras el usuario tipea o cambia opciones
  form.querySelectorAll('input, select, textarea').forEach(function (el) {
    el.addEventListener('input', function () {
      ocultarError(el.name);
    });
    el.addEventListener('change', function () {
      ocultarError(el.name);
    });
  });
});