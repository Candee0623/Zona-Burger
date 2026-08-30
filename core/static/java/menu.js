document.addEventListener('DOMContentLoaded', function() {
    const mobileMenu = document.getElementById('mobile-menu');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenu) {
        mobileMenu.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            mobileMenu.classList.toggle('is-active');
        });
    }

    const chips = document.querySelectorAll('.categoria-chip');
    const secciones = document.querySelectorAll('.categoria-seccion');

    chips.forEach(chip => {
        chip.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href') || `#${this.getAttribute('data-target')}`;
            const targetSection = document.querySelector(targetId);

            if (targetSection) {
                targetSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }

            chips.forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            this.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        });
    });

    const observerOptions = {
        root: null,
        rootMargin: '-20% 0px -60% 0px',
        threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                
                chips.forEach(chip => {
                    const chipTarget = chip.getAttribute('href') === `#${id}` || chip.getAttribute('data-target') === id;
                    if (chipTarget) {
                        chip.classList.add('active');
                        chip.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
                    } else {
                        chip.classList.remove('active');
                    }
                });
            }
        });
    }, observerOptions);

    secciones.forEach(section => {
        observer.observe(section);
    });
});