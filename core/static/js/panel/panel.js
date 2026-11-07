document.addEventListener("DOMContentLoaded", function () {

    /* ELEMENTOS PRINCIPALES */

    const menuToggle = document.getElementById("menuToggle");
    const panelContainer = document.getElementById("panelContainer");
    const sidebar = document.getElementById("sidebar");

    const userButton = document.getElementById("userButton");
    const userDropdown = document.getElementById("userDropdown");

    /* CONFIGURACIÓN */

    const MOBILE_BREAKPOINT = 850;

    function isMobile() {
        return window.innerWidth <= MOBILE_BREAKPOINT;
    }

    /* ========================================
       ACTUALIZAR BOTÓN HAMBURGUESA
       
       Cerrado = ☰
       Abierto = ✕
    ======================================== */

    function actualizarBotonMenu() {

        if (!menuToggle || !panelContainer) {
            return;
        }

        const menuAbierto =
            panelContainer.classList.contains("sidebar-mobile-open");

        if (menuAbierto && isMobile()) {

            menuToggle.textContent = "✕";
            menuToggle.setAttribute(
                "aria-label",
                "Cerrar menú"
            );

        } else {

            menuToggle.textContent = "☰";
            menuToggle.setAttribute(
                "aria-label",
                "Abrir menú"
            );

        }

    }

    /* ABRIR / CERRAR MENÚ LATERAL */

    if (menuToggle && panelContainer) {

        menuToggle.addEventListener("click", function (event) {

            /*
             * Evita que el click llegue al document
             * y cierre inmediatamente el menú.
             */
            event.stopPropagation();

            if (isMobile()) {

                /* En móvil/tablet alternamos el sidebar. */
                panelContainer.classList.toggle(
                    "sidebar-mobile-open"
                );

                /* Actualizamos ☰ / ✕. */
                actualizarBotonMenu();

            } else {

                /*
                 * En escritorio usamos el sidebar
                 * contraído.
                 */
                panelContainer.classList.toggle(
                    "sidebar-collapsed"
                );

            }

        });

    }

    /* CERRAR SIDEBAR AL HACER CLICK AFUERA */

    document.addEventListener("click", function (event) {

        if (!isMobile()) {
            return;
        }

        if (!panelContainer) {
            return;
        }

        if (
            !panelContainer.classList.contains(
                "sidebar-mobile-open"
            )
        ) {
            return;
        }

        /*
         * Si el click fue dentro del sidebar
         * no hacemos nada.
         */
        if (
            sidebar &&
            sidebar.contains(event.target)
        ) {
            return;
        }

        /*
         * Si el click fue sobre el botón tampoco
         * hacemos nada porque el propio botón
         * controla la apertura/cierre.
         */
        if (
            menuToggle &&
            menuToggle.contains(event.target)
        ) {
            return;
        }

        /*
         * Click fuera del menú:
         * cerramos el sidebar.
         */
        panelContainer.classList.remove(
            "sidebar-mobile-open"
        );

        actualizarBotonMenu();

    });

    /* CERRAR AL SELECCIONAR UNA OPCIÓN */

    if (sidebar) {

        const sidebarLinks =
            sidebar.querySelectorAll("a");

        sidebarLinks.forEach(function (link) {

            link.addEventListener("click", function () {

                if (!isMobile()) {
                    return;
                }

                panelContainer.classList.remove(
                    "sidebar-mobile-open"
                );

                actualizarBotonMenu();

            });

        });

    }

    /* CAMBIO DE TAMAÑO DE PANTALLA */

    window.addEventListener("resize", function () {

        if (!panelContainer) {
            return;
        }

        /*
         * Si volvemos a escritorio,
         * quitamos el estado móvil.
         */
        if (!isMobile()) {

            panelContainer.classList.remove(
                "sidebar-mobile-open"
            );

        }

        actualizarBotonMenu();

    });

    /* MENÚ DE USUARIO */

    if (userButton && userDropdown) {

        userButton.addEventListener("click", function (event) {

            event.stopPropagation();

            userDropdown.classList.toggle("show");

        });

        /* Click fuera del menú de usuario. */
        document.addEventListener("click", function () {

            userDropdown.classList.remove("show");

        });

        /*
         * Evita que un click dentro del dropdown
         * lo cierre.
         */
        userDropdown.addEventListener("click", function (event) {

            event.stopPropagation();

        });

    }

    /* TECLA ESCAPE */

    document.addEventListener("keydown", function (event) {

        if (event.key !== "Escape") {
            return;
        }

        if (panelContainer) {

            panelContainer.classList.remove(
                "sidebar-mobile-open"
            );

        }

        actualizarBotonMenu();

        if (userDropdown) {

            userDropdown.classList.remove("show");

        }

    });

    /* ========================================
       CAMPOS NUMÉRICOS

       1) La rueda del mouse ya no cambia el valor
          (los campos pasan a ser de texto, que no
          reaccionan a la rueda).
       2) Se muestran con formato argentino:
          12.000 / 1.500,50 (miles con punto,
          decimales con coma, sin ",00" sobrante).
       3) Al enviar el formulario se manda el valor
          "crudo" (12000.5), así las vistas de Django
          reciben exactamente lo mismo que antes.
       4) `input.value` desde JavaScript también
          devuelve el valor crudo (12000.5), por lo que
          los scripts existentes siguen funcionando.
    ======================================== */

    // <numeros-helpers>
    const valorNativo = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value"
    );

    // Valor crudo "12000.5" a partir de lo que se ve en pantalla "12.000,5".
    function textoACrudo(texto) {
        let t = String(texto || "").replace(/\s/g, "").replace(/\./g, "").replace(",", ".");
        if (!/^-?\d*\.?\d*$/.test(t)) return "";
        if (t.charAt(t.length - 1) === ".") t = t.slice(0, -1);
        if (t === "" || t === "-") return "";
        t = t.replace(/^(-?)\./, "$10.");
        return t;
    }

    // Interpreta texto externo (pegado o atributo mal formateado) de forma flexible.
    function interpretarTexto(texto) {
        let t = String(texto || "").replace(/[^\d.,-]/g, "");
        if (!t) return null;

        const negativo = t.charAt(0) === "-";
        t = t.replace(/-/g, "");
        if (!t) return null;

        const tienePunto = t.indexOf(".") !== -1;
        const tieneComa = t.indexOf(",") !== -1;

        if (tienePunto && tieneComa) {
            const sepDecimal = t.lastIndexOf(",") > t.lastIndexOf(".") ? "," : ".";
            const sepMiles = sepDecimal === "," ? "." : ",";
            t = t.split(sepMiles).join("").replace(sepDecimal, ".");
        } else if (tieneComa) {
            t = t.split(",").length > 2 ? t.split(",").join("") : t.replace(",", ".");
        } else if (tienePunto) {
            const partes = t.split(".");
            const esMiles = partes.length > 2 || /^\d{1,3}\.\d{3}$/.test(t);
            if (esMiles) t = partes.join("");
        }

        if (!/^\d*\.?\d*$/.test(t) || t === "" || t === ".") return null;
        t = t.replace(/^\./, "0.").replace(/\.$/, "");
        return (negativo ? "-" : "") + t;
    }

    // "12000.5" -> "12.000,5"  |  "12000.00" -> "12.000"
    function crudoATexto(crudo, opciones) {
        if (crudo === "" || crudo === null || crudo === undefined) return "";
        const negativo = String(crudo).charAt(0) === "-";
        const partes = String(crudo).replace("-", "").split(".");

        let entero = (partes[0] || "0").replace(/^0+(?=\d)/, "");
        let decimales = (partes[1] || "").replace(/0+$/, "");

        // Importes (step 0.01): 1.500,5 se muestra como 1.500,50
        if (opciones.decimales === 2 && decimales.length === 1) decimales += "0";

        if (opciones.agrupar) entero = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

        return (negativo ? "-" : "") + entero + (decimales ? "," + decimales : "");
    }

    // Formato mientras se escribe: agrega los puntos de miles en vivo.
    function formatearMientrasEscribe(texto, opciones) {
        const negativo = opciones.permiteNegativo && texto.trim().charAt(0) === "-";
        const limpio = texto.replace(/[^\d,]/g, "");
        const indiceComa = limpio.indexOf(",");

        let entero = limpio;
        let decimales = "";
        let hayComa = false;

        if (opciones.decimales > 0 && indiceComa !== -1) {
            hayComa = true;
            entero = limpio.slice(0, indiceComa);
            decimales = limpio.slice(indiceComa + 1).replace(/,/g, "").slice(0, opciones.decimales);
        } else {
            entero = limpio.replace(/,/g, "");
        }

        entero = entero.replace(/^0+(?=\d)/, "");
        if (opciones.agrupar) entero = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");

        return (negativo ? "-" : "") + entero + (hayComa ? "," + decimales : "");
    }

    function contarSignificativos(texto) {
        return (texto.match(/[\d,-]/g) || []).length;
    }

    function posicionTrasSignificativos(texto, cantidad) {
        if (cantidad <= 0) return 0;
        let contados = 0;
        for (let i = 0; i < texto.length; i++) {
            if (/[\d,-]/.test(texto.charAt(i))) contados++;
            if (contados === cantidad) return i + 1;
        }
        return texto.length;
    }

    function decimalesDelStep(step) {
        if (step === null || step === "") return 0;
        if (step === "any") return 4;
        const m = String(step).match(/\.(\d+)$/);
        return m ? m[1].length : 0;
    }
    // </numeros-helpers>

    function prepararCampoNumerico(input) {
        if (input.dataset.numerico === "true") return;

        const decimales = decimalesDelStep(input.getAttribute("step"));
        const opciones = {
            decimales: decimales,
            // Los enteros sin step (N.º de pedido, mín./máx. selecciones)
            // no llevan puntos de miles.
            agrupar: decimales > 0 || input.hasAttribute("data-miles"),
            permiteNegativo: !input.hasAttribute("min") || parseFloat(input.getAttribute("min")) < 0
        };

        // Valor inicial: en type="number" el valor siempre viene con punto decimal.
        let inicial = valorNativo.get.call(input);
        if (inicial === "") {
            const interpretado = interpretarTexto(input.getAttribute("value"));
            inicial = interpretado === null ? "" : interpretado;
        }

        input.type = "text";
        input.setAttribute("inputmode", decimales > 0 ? "decimal" : "numeric");
        input.setAttribute("autocomplete", "off");
        input.dataset.numerico = "true";

        // Los placeholders "0.00" / "Ej. 1500.00" pasan a verse como "0" / "Ej. 1.500".
        const placeholder = input.getAttribute("placeholder");
        if (placeholder) {
            input.setAttribute(
                "placeholder",
                placeholder.replace(/\d+\.\d+|\d{4,}/g, function (n) {
                    return crudoATexto(n, opciones);
                })
            );
        }

        function leerCrudo() {
            return textoACrudo(valorNativo.get.call(input));
        }

        function mostrarCrudo(crudo) {
            valorNativo.set.call(input, crudoATexto(crudo, opciones));
        }

        // Los scripts que lean/escriban input.value siguen trabajando con el valor crudo.
        Object.defineProperty(input, "value", {
            configurable: true,
            get: function () {
                return leerCrudo();
            },
            set: function (nuevo) {
                if (nuevo === null || nuevo === undefined || nuevo === "") {
                    valorNativo.set.call(input, "");
                    return;
                }
                const interpretado = /^-?\d+(\.\d+)?$/.test(String(nuevo))
                    ? String(nuevo)
                    : interpretarTexto(nuevo);
                mostrarCrudo(interpretado === null ? "" : interpretado);
            }
        });

        function formatearTexto(numero) {
            return crudoATexto(String(numero), opciones);
        }

        function validar() {
            input.setCustomValidity("");

            const texto = valorNativo.get.call(input).trim();
            if (texto === "") return;

            const crudo = leerCrudo();
            if (crudo === "") {
                input.setCustomValidity("Ingresá un número válido.");
                return;
            }

            const numero = Number(crudo);
            const min = input.getAttribute("min");
            const max = input.getAttribute("max");

            if (min !== null && min !== "" && numero < parseFloat(min)) {
                input.setCustomValidity("El valor debe ser mayor o igual a " + formatearTexto(parseFloat(min)) + ".");
            } else if (max !== null && max !== "" && numero > parseFloat(max)) {
                input.setCustomValidity("El valor debe ser menor o igual a " + formatearTexto(parseFloat(max)) + ".");
            }
        }

        mostrarCrudo(inicial);
        validar();

        input.addEventListener("input", function () {
            const texto = valorNativo.get.call(input);
            const cursor = input.selectionStart === null ? texto.length : input.selectionStart;
            const significativos = contarSignificativos(texto.slice(0, cursor));
            const nuevo = formatearMientrasEscribe(texto, opciones);

            if (nuevo !== texto) {
                valorNativo.set.call(input, nuevo);
                const posicion = posicionTrasSignificativos(nuevo, significativos);
                input.setSelectionRange(posicion, posicion);
            }

            validar();
        });

        // En Argentina el "." del teclado numérico se usa como coma decimal.
        input.addEventListener("beforeinput", function (event) {
            if (event.inputType !== "insertText" || event.data === null || event.data.length !== 1) return;

            if (event.data === "." || event.data === ",") {
                event.preventDefault();
                if (opciones.decimales > 0) {
                    input.setRangeText(",", input.selectionStart, input.selectionEnd, "end");
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
                return;
            }

            const permitido = /\d/.test(event.data) || (event.data === "-" && opciones.permiteNegativo);
            if (!permitido) event.preventDefault();
        });

        input.addEventListener("paste", function (event) {
            const pegado = (event.clipboardData || window.clipboardData).getData("text");
            const crudo = interpretarTexto(pegado);
            if (crudo === null) return;

            event.preventDefault();
            input.setRangeText(crudo.replace(".", ","), input.selectionStart, input.selectionEnd, "end");
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });

        // Flechas arriba/abajo: suman o restan un step (la rueda del mouse NO).
        input.addEventListener("keydown", function (event) {
            if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
            event.preventDefault();

            const paso = parseFloat(input.getAttribute("step"));
            const salto = Number.isFinite(paso) && paso > 0 ? paso : 1;
            const actual = Number(leerCrudo()) || 0;

            let nuevo = actual + (event.key === "ArrowUp" ? salto : -salto);
            nuevo = Math.round(nuevo * 1e6) / 1e6;

            const min = parseFloat(input.getAttribute("min"));
            const max = parseFloat(input.getAttribute("max"));
            if (Number.isFinite(min) && nuevo < min) nuevo = min;
            if (Number.isFinite(max) && nuevo > max) nuevo = max;

            mostrarCrudo(String(nuevo));
            input.dispatchEvent(new Event("input", { bubbles: true }));
        });

        input.addEventListener("blur", function () {
            const crudo = leerCrudo();
            valorNativo.set.call(input, crudo === "" ? "" : crudoATexto(crudo, opciones));
            validar();
        });

        // form.reset() restaura el valor original sin formato: lo volvemos a formatear.
        if (input.form) {
            input.form.addEventListener("reset", function () {
                setTimeout(function () {
                    const original = interpretarTexto(input.defaultValue);
                    mostrarCrudo(original === null ? "" : original);
                    validar();
                }, 0);
            });
        }
    }

    function prepararCamposNumericos(raiz) {
        if (raiz.matches && raiz.matches('input[type="number"]')) {
            prepararCampoNumerico(raiz);
        }
        if (raiz.querySelectorAll) {
            raiz.querySelectorAll('input[type="number"]').forEach(prepararCampoNumerico);
        }
    }

    prepararCamposNumericos(document);

    // Campos agregados luego por JavaScript (ej. "Agregar opción").
    new MutationObserver(function (mutaciones) {
        mutaciones.forEach(function (mutacion) {
            mutacion.addedNodes.forEach(function (nodo) {
                if (nodo.nodeType === 1) prepararCamposNumericos(nodo);
            });
        });
    }).observe(document.body, { childList: true, subtree: true });

    // Lo que se envía al servidor (submit normal o fetch con new FormData(form))
    // es siempre el valor crudo: 12000.5 y no "12.000,5".
    document.addEventListener("formdata", function (event) {
        const form = event.target;
        if (!form || !form.elements) return;

        const nombres = {};
        Array.prototype.forEach.call(form.elements, function (el) {
            if (el.dataset && el.dataset.numerico === "true" && el.name && !el.disabled) {
                nombres[el.name] = true;
            }
        });

        Object.keys(nombres).forEach(function (nombre) {
            const campos = Array.prototype.filter.call(form.elements, function (el) {
                return el.name === nombre && !el.disabled;
            });

            // Solo reemplazamos si todos los campos con ese nombre son numéricos.
            const todosNumericos = campos.every(function (el) {
                return el.dataset && el.dataset.numerico === "true";
            });
            if (!todosNumericos) return;

            event.formData.delete(nombre);
            campos.forEach(function (el) {
                event.formData.append(nombre, el.value);
            });
        });
    });

    /* PREVENCIÓN DE DOBLE ENVÍO EN FORMULARIOS */
    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!form || form.tagName !== "FORM") return;

        if (form.dataset.enviando === "true") {
            event.preventDefault();
            event.stopPropagation();
            return false;
        }

        form.dataset.enviando = "true";

        const botonSubmit = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
        if (botonSubmit) {
            // Se deshabilita después de armar los datos del formulario;
            // si no, un botón con name/value (ej. accion=abrir) no se envía.
            setTimeout(function () {
                botonSubmit.disabled = true;
                botonSubmit.classList.add("btn-deshabilitado-enviando");
            }, 0);
        }

        // Liberar bloqueo tras 8 segundos por seguridad en caso de fallos de red
        setTimeout(function () {
            form.dataset.enviando = "false";
            if (botonSubmit) {
                botonSubmit.disabled = false;
                botonSubmit.classList.remove("btn-deshabilitado-enviando");
            }
        }, 8000);
    });

    /* ESTADO INICIAL DEL BOTÓN */

    actualizarBotonMenu();

});