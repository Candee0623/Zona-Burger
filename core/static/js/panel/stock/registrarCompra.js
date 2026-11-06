document.addEventListener('DOMContentLoaded', function () {
    const cantidad = document.getElementById('cantidad');
    const precioTotal = document.getElementById('preciototal');
    const costoUnitario = document.getElementById('costo-unitario-calculado');

    function calcularCostoUnitario() {
        const cant = Number(cantidad.value) || 0;
        const total = Number(precioTotal.value) || 0;

        const costo = cant > 0 ? total / cant : 0;

        costoUnitario.textContent = costo.toLocaleString('es-AR', {
            style: 'currency',
            currency: 'ARS',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    cantidad.addEventListener('input', calcularCostoUnitario);
    precioTotal.addEventListener('input', calcularCostoUnitario);

    calcularCostoUnitario();
});
