document.addEventListener('DOMContentLoaded', function() {
    // Obtenemos el precio base del elemento en el DOM
    const elementoPrecioBase = document.querySelector('.detalle-precio-base');
    const precioBase = elementoPrecioBase ? (parseFloat(elementoPrecioBase.getAttribute('data-precio-base')) || 0) : 0;
    
    const spanTotal = document.getElementById('precio-total');
    const inputsOpciones = document.querySelectorAll('#form-personalizar input[type="radio"], #form-personalizar input[type="checkbox"]');
    const inputsCantidad = document.querySelectorAll('.cantidad-extra');

    function calcularTotal() {
        let totalActual = precioBase;

        inputsOpciones.forEach(input => {
            if (input.checked) {
                const precioAdicional = parseFloat(input.getAttribute('data-precio')) || 0;
                const contenedorOpcion = input.closest('.opcion-item');
                const inputCant = contenedorOpcion ? contenedorOpcion.querySelector('.cantidad-extra') : null;
                
                // Si tiene selector de cantidad, lo multiplicamos; si no, cuenta como 1
                const cantidad = inputCant ? (parseInt(inputCant.value) || 1) : 1;

                totalActual += (precioAdicional * cantidad);
            }
        });

        if (spanTotal) {
            spanTotal.textContent = totalActual.toFixed(2);
        }
    }

    inputsOpciones.forEach(input => {
        input.addEventListener('change', calcularTotal);
    });

    inputsCantidad.forEach(input => {
        input.addEventListener('input', calcularTotal);
    });

    // Calcular al cargar por si hay elementos marcados por defecto
    calcularTotal();
});