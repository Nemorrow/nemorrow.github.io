(() => {
  'use strict';

  function initializeSectionMotion() {
    if (!document.body.classList.contains('quiet-home-page')) return;
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (motionPreference.matches || !('IntersectionObserver' in window)) return;

    const selectors = [
      '.home-education',
      '.home-contact',
      '.page__content > p',
      '.usage-section',
      '.publications-heading',
      '.publications-group',
      '.publication-item',
      '.academic-service-heading',
      '.service-row',
      '.page__content > h2',
      '.page__content > ul'
    ];
    const targets = Array.from(document.querySelectorAll(selectors.join(', ')));
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;

    const observer = new IntersectionObserver(entries => {
      const entering = entries.filter(entry => entry.isIntersecting);
      entering.forEach((entry, index) => {
        const target = entry.target;
        target.style.setProperty('--home-scroll-delay', `${Math.min(index * 35, 70)}ms`);
        target.classList.add('home-motion-visible');
        observer.unobserve(target);
      });
    }, { rootMargin: '0px 0px 32px 0px', threshold: 0 });

    targets.forEach(target => {
      const bounds = target.getBoundingClientRect();
      if (bounds.height > 0 && bounds.top >= viewportHeight) {
        target.classList.add('home-motion-scroll');
        observer.observe(target);
      }
    });

    // Keyboard navigation reveals its destination immediately.
    document.addEventListener('focusin', event => {
      if (!(event.target instanceof Element)) return;
      const target = event.target.closest('.home-motion-scroll');
      if (!target) return;
      target.classList.remove('home-motion-scroll', 'home-motion-visible');
      target.classList.add('home-motion-static');
      observer.unobserve(target);
    });

    if (typeof motionPreference.addEventListener === 'function') {
      motionPreference.addEventListener('change', event => {
        if (event.matches) observer.disconnect();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSectionMotion, { once: true });
  } else {
    initializeSectionMotion();
  }
})();
