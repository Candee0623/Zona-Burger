(() => {
    rep.tema();
    const C = rep.colores;
    const dias = rep.leer("rep-dias");
    const estados = rep.leer("rep-estados");
    const labels = dias.map(d => rep.dia(d.dia));

    const linea = document.getElementById("rep-linea");
    if (linea) new Chart(linea, {
        type: "line",
        data: { labels, datasets: [{
            data: dias.map(d => Number(d.total)),
            borderColor: C.rojo, backgroundColor: "rgba(220,38,38,.12)",
            pointBackgroundColor: C.rojo, fill: true, tension: .35, pointRadius: 3
        }] },
        options: rep.ejes({ dinero: true })
    });

    const barras = document.getElementById("rep-barras");
    if (barras) new Chart(barras, {
        type: "bar",
        data: { labels, datasets: [{
            data: dias.map(d => Number(d.pedidos)),
            backgroundColor: C.rojo, borderRadius: 4, maxBarThickness: 28
        }] },
        options: rep.ejes()
    });

    const dona = document.getElementById("rep-estados-chart");
    if (dona) new Chart(dona, {
        type: "doughnut",
        data: {
            labels: estados.map(e => e.idestadopedido__descripcion || "Sin estado"),
            datasets: [{
                data: estados.map(e => Number(e.cantidad)),
                backgroundColor: C.paleta, borderColor: "#181818", borderWidth: 3, hoverOffset: 6
            }]
        },
        options: rep.dona()
    });
})();
