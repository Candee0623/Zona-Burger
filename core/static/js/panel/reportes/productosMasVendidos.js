(() => {
    rep.tema();
    const C = rep.colores;
    const filas = rep.leer("rep-productos");
    const labels = filas.map(p => p.nombre_historico || "Sin nombre");

    const unidades = document.getElementById("rep-unidades");
    if (unidades) new Chart(unidades, {
        type: "bar",
        data: { labels, datasets: [{
            data: filas.map(p => Number(p.unidades)),
            backgroundColor: C.rojo, borderRadius: 4, maxBarThickness: 26
        }] },
        options: rep.ejes({ horizontal: true })
    });

    const ingresos = document.getElementById("rep-ingresos");
    if (ingresos) new Chart(ingresos, {
        type: "bar",
        data: { labels, datasets: [{
            data: filas.map(p => Number(p.ingresos)),
            backgroundColor: C.rojoClaro, borderRadius: 4, maxBarThickness: 26
        }] },
        options: rep.ejes({ horizontal: true, dinero: true })
    });
})();
