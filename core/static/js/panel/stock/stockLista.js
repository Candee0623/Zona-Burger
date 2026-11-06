document.addEventListener('DOMContentLoaded', function () {
    const tabs = document.querySelectorAll('.stock-tab');
    const panels = document.querySelectorAll('.stock-panel');

    // Pestañas
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            tabs.forEach(function (item) {
                item.classList.remove('active');
                item.setAttribute('aria-selected', 'false');
            });

            panels.forEach(function (panel) {
                panel.hidden = true;
            });

            tab.classList.add('active');
            tab.setAttribute('aria-selected', 'true');

            const selectedPanel = document.getElementById(
                tab.dataset.panel
            );

            if (selectedPanel) {
                selectedPanel.hidden = false;
            }
        });
    });

    // Actualizar la información cada 30 segundos.
    const INTERVALO_ACTUALIZACION = 30000;
    let temporizadorActualizacion = null;

    function programarActualizacion() {
        clearTimeout(temporizadorActualizacion);

        if (document.hidden) {
            return;
        }

        temporizadorActualizacion = setTimeout(function () {
            window.location.reload();
        }, INTERVALO_ACTUALIZACION);
    }

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            clearTimeout(temporizadorActualizacion);
        } else {
            programarActualizacion();
        }
    });

    programarActualizacion();
});
