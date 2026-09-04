document.addEventListener("DOMContentLoaded", function() {
    // Busca botones, títulos o textos que digan "Identificarse" y los cambia
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    let node;
    while (node = walker.nextNode()) {
        if (node.nodeValue.trim() === "Identificarse") {
            node.nodeValue = "Iniciar sesión";
        }
    }
});
document.addEventListener("DOMContentLoaded", function() {
    // Busca exclusivamente el botón de acciones y reemplaza su texto por completo
    const btnGo = document.querySelector('.actions button, .actions input[type="submit"]');
    
    if (btnGo) {
        if (btnGo.tagName === 'INPUT') {
            btnGo.value = 'APLICAR';
        } else {
            btnGo.innerText = 'APLICAR';
        }
    }
});