document.addEventListener('DOMContentLoaded', function () {
    // Auto-ocultar alertas de éxito e informativas después de 6 segundos
    const banners = document.querySelectorAll('.panel-alert-success, .panel-alert-info');
    banners.forEach(function (banner) {
        setTimeout(function () {
            banner.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            banner.style.opacity = '0';
            banner.style.transform = 'translateY(-6px)';
            setTimeout(function () {
                banner.remove();
            }, 400);
        }, 6000);
    });
});
