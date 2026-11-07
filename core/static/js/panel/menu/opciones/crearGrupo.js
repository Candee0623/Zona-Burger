document.getElementById('btn-agregar-opcion').addEventListener('click', function () {

    const tbody = document.getElementById('filas-opciones');

    const fila = document.createElement('tr');

    fila.innerHTML = `
        <td class="grupo-new-option-cell">

            <input
                type="text"
                name="opcion_nombre[]"
                class="grupo-create-input"
                placeholder="Ej: Sprite"
            >

        </td>

        <td class="grupo-new-option-cell">

            <input
                type="number"
                step="0.01"
                name="opcion_precio[]"
                class="grupo-create-input"
                value="0"
            >

        </td>

        <td class="grupo-new-option-cell">

            <select
                name="opcion_insumo[]"
                class="grupo-create-input"
            >
                <option value="">(Sin insumo vinculado)</option>
                ${window.ZB_GRUPO_INSUMOS_OPCIONES}
            </select>

        </td>

        <td class="grupo-new-option-cell">

            <input
                type="number"
                step="0.01"
                min="0.01"
                name="opcion_cantidad_insumo[]"
                class="grupo-create-input"
                value="1.00"
            >

        </td>

        <td class="grupo-new-option-action-cell">

            <button
                type="button"
                class="grupo-remove-new-option"
                title="Quitar opción"
            >

                <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >

                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6l-1 14H6L5 6"></path>
                    <path d="M10 11v6"></path>
                    <path d="M14 11v6"></path>
                    <path d="M9 6V4h6v2"></path>

                </svg>

                Quitar

            </button>

        </td>
    `;

    tbody.appendChild(fila);

});

/*
 * Quitar una opción nueva.
 * Como todavía no fue guardada en la base de datos,
 * simplemente eliminamos la fila del formulario.
 */
document.getElementById('filas-opciones').addEventListener('click', function (event) {

    const boton = event.target.closest('.grupo-remove-new-option');

    if (!boton) {
        return;
    }

    const fila = boton.closest('tr');

    if (fila) {
        fila.remove();
    }

});
