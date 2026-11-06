document.addEventListener('DOMContentLoaded', function () {

    const selectTipo = document.getElementById('tipobeneficio');
    const grupoValor = document.getElementById('grupo-valor');
    const inputDescuento = document.getElementById('descuento');

    function controlarValor() {

        if (!selectTipo || !grupoValor || !inputDescuento) {
            return;
        }

        const opcionSeleccionada =
            selectTipo.options[selectTipo.selectedIndex];

        const comportamiento =
            opcionSeleccionada
                ? opcionSeleccionada.getAttribute('data-comportamiento')
                : null;

        if (comportamiento === 'SIN_VALOR') {

            grupoValor.style.display = 'none';
            inputDescuento.required = false;

        } else {

            grupoValor.style.display = 'block';
            inputDescuento.required = true;

        }
    }

    controlarValor();

    if (selectTipo) {
        selectTipo.addEventListener('change', controlarValor);
    }

});
