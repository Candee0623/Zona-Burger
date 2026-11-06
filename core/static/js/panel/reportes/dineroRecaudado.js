(() => {
    rep.tema();
    const C = rep.colores;
    const dias = rep.leer("rep-dias");
    const semana = rep.leer("rep-semana-datos");
    const medios = rep.leer("rep-medios-datos");

    const linea = document.getElementById("rep-linea");
    if (linea) new Chart(linea, {
        type: "line",
        data: { labels: dias.map(d => rep.dia(d.fecha)), datasets: [{
            data: dias.map(d => Number(d.importe)),
            borderColor: C.rojo, backgroundColor: "rgba(220,38,38,.12)",
            pointBackgroundColor: C.rojo, fill: true, tension: .35, pointRadius: 3
        }] },
        options: rep.ejes({ dinero: true })
    });

    const dona = document.getElementById("rep-medios");
    if (dona) new Chart(dona, {
        type: "doughnut",
        data: {
            labels: medios.map(m => m.nombre),
            datasets: [{
                data: medios.map(m => Number(m.importe)),
                backgroundColor: C.paleta, borderColor: "#181818", borderWidth: 3, hoverOffset: 6
            }]
        },
        options: rep.dona(true)
    });

    const barras = document.getElementById("rep-semana");
    if (barras) new Chart(barras, {
        type: "bar",
        data: { labels: semana.map(s => s.dia), datasets: [{
            data: semana.map(s => Number(s.importe)),
            backgroundColor: C.rojo, borderRadius: 4, maxBarThickness: 34
        }] },
        options: rep.ejes({ horizontal: false, dinero: true })
    });
})();
