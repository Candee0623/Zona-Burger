document.addEventListener('DOMContentLoaded', function () {
    const publicAlerts = document.querySelectorAll('.zb-alert-success, .zb-alert-info');
    publicAlerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-6px)';
            setTimeout(function () { alert.remove(); }, 400);
        }, 6000);
    });
});
