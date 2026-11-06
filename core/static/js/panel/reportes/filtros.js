(() => {
    const inicio = document.getElementById("rep-inicio");
    const fin = document.getElementById("rep-fin");

    const iso = (d) =>
        d.getFullYear() + "-" +
        String(d.getMonth() + 1).padStart(2, "0") + "-" +
        String(d.getDate()).padStart(2, "0");

    const rangos = {
        "hoy": () => { const h = new Date(); return [h, h]; },
        "7": () => { const h = new Date(); const i = new Date(); i.setDate(h.getDate() - 6); return [i, h]; },
        "30": () => { const h = new Date(); const i = new Date(); i.setDate(h.getDate() - 29); return [i, h]; },
        "mes": () => { const h = new Date(); return [new Date(h.getFullYear(), h.getMonth(), 1), h]; },
        "mes-anterior": () => {
            const h = new Date();
            return [new Date(h.getFullYear(), h.getMonth() - 1, 1), new Date(h.getFullYear(), h.getMonth(), 0)];
        }
    };

    function filtrar(desde, hasta) {
        if (!desde || !hasta) return;
        if (desde > hasta) { const t = desde; desde = hasta; hasta = t; }
        window.location.href = window.location.pathname +
            "?fecha_inicio=" + desde + "&fecha_fin=" + hasta;
    }

    document.getElementById("rep-aplicar").addEventListener("click", () => {
        filtrar(inicio.value, fin.value);
    });

    [inicio, fin].forEach((campo) => {
        campo.addEventListener("keydown", (e) => {
            if (e.key === "Enter") filtrar(inicio.value, fin.value);
        });
    });

    document.querySelectorAll("#rep-filtros [data-preset]").forEach((chip) => {
        const r = rangos[chip.dataset.preset]();
        if (iso(r[0]) === inicio.value && iso(r[1]) === fin.value) {
            chip.classList.add("rep-chip-activo");
        }
        chip.addEventListener("click", () => {
            const rango = rangos[chip.dataset.preset]();
            filtrar(iso(rango[0]), iso(rango[1]));
        });
    });
})();
