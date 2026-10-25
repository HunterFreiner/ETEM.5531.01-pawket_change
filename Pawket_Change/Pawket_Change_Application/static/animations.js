// Fades page content up into view as it scrolls onto the screen. Cards in the same row appear one after another.
// Content is only hidden once this script runs, so the page never looks empty without JavaScript, and nothing
// moves for visitors who have asked their device to reduce motion.
(() => {
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    const selector = [
        'main .page-title', 'main .lead', '.hero-logo', '.mission', '.dog-photo', '.price-card', '.info-panel',
        '.team-card', '.contact-panel', '.review-card', '.review-summary',
    ].join(', ');
    const STAGGER_MS = 90;
    const MAX_DELAY_MS = 450;

    const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        }
    }, {rootMargin: '0px 0px -40px 0px', threshold: 0.1});

    document.querySelectorAll(selector).forEach(element => {
        // Stagger by the element's column position within a grid row, or its position in a list of cards.
        const column = element.closest('.row > *');
        const siblings = column ? [...column.parentElement.children] : [...element.parentElement.children];
        const index = siblings.indexOf(column || element);
        element.style.setProperty('--reveal-delay', `${Math.min(index * STAGGER_MS, MAX_DELAY_MS)}ms`);
        element.classList.add('reveal');
        observer.observe(element);
    });
})();
