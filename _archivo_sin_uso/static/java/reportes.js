/* =========================================================
   REPORTES - ZONA BURGER (filtros + ayudas de gráficos)
   ========================================================= */

(() => {
    const entero = new Intl.NumberFormat("es-AR");
    const moneda = new Intl.NumberFormat("es-AR", {
        style: "currency",
        currency: "ARS",
        minimumFractionDigits: 2,
    });

    const C = {
        rojo: "#dc2626",
        rojoClaro: "#f87171",
        grid: "#292929",
        texto: "#888",
        etiqueta: "#ccc",
        paleta: ["#dc2626", "#f97316", "#fbbf24", "#a3a3a3", "#f87171", "#7f1d1d"],
    };

    window.rep = {
        colores: C,
        moneda: (v) => moneda.format(Number(v || 0)),
        entero: (v) => entero.format(Number(v || 0)),
        dia: (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : ""),
        leer: (id) => JSON.parse(document.getElementById(id).textContent),

        tema() {
            Chart.defaults.color = C.texto;
            Chart.defaults.borderColor = C.grid;
            Chart.defaults.font.family = "inherit";
        },

        ejes({ horizontal = false, dinero = false } = {}) {
            const fmt = dinero ? window.rep.moneda : window.rep.entero;
            const valor = {
                beginAtZero: true,
                grid: { color: C.grid },
                ticks: { color: C.texto, callback: (v) => fmt(v) },
            };
            const categoria = {
                grid: { display: false },
                ticks: { color: horizontal ? C.etiqueta : C.texto, maxRotation: 0, autoSkip: true },
            };
            return {
                indexAxis: horizontal ? "y" : "x",
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (c) => " " + fmt(horizontal ? c.parsed.x : c.parsed.y),
                        },
                    },
                },
                scales: horizontal ? { x: valor, y: categoria } : { x: categoria, y: valor },
            };
        },

        dona(dinero = false) {
            const fmt = dinero ? window.rep.moneda : window.rep.entero;
            return {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#aaa", padding: 16, usePointStyle: true },
                    },
                    tooltip: {
                        callbacks: { label: (c) => ` ${c.label}: ${fmt(c.parsed)}` },
                    },
                },
            };
        },
    };

    /* ---------- Filtro de fechas ---------- */

    const form = document.querySelector(".rep-filters");
    if (!form) return;

    const inicio = form.querySelector('[name="fecha_inicio"]');
    const fin = form.querySelector('[name="fecha_fin"]');

    const iso = (d) =>
        `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

    const rangos = {
        hoy: () => {
            const h = new Date();
            return [h, h];
        },
        "7": () => {
            const h = new Date();
            const i = new Date();
            i.setDate(h.getDate() - 6);
            return [i, h];
        },
        "30": () => {
            const h = new Date();
            const i = new Date();
            i.setDate(h.getDate() - 29);
            return [i, h];
        },
        mes: () => {
            const h = new Date();
            return [new Date(h.getFullYear(), h.getMonth(), 1), h];
        },
        "mes-anterior": () => {
            const h = new Date();
            return [
                new Date(h.getFullYear(), h.getMonth() - 1, 1),
                new Date(h.getFullYear(), h.getMonth(), 0),
            ];
        },
    };

    form.querySelectorAll("[data-rango]").forEach((chip) => {
        const [a, b] = rangos[chip.dataset.rango]();
        if (iso(a) === inicio.value && iso(b) === fin.value) {
            chip.classList.add("rep-chip-activo");
        }

        chip.addEventListener("click", () => {
            const [desde, hasta] = rangos[chip.dataset.rango]();
            inicio.value = iso(desde);
            fin.value = iso(hasta);
            form.requestSubmit ? form.requestSubmit() : form.submit();
        });
    });

    form.addEventListener("submit", () => {
        if (inicio.value && fin.value && inicio.value > fin.value) {
            [inicio.value, fin.value] = [fin.value, inicio.value];
        }
    });
})();