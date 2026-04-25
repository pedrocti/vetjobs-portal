(function () {

  const hamburger = document.getElementById('vpHamburger');
  const drawer    = document.getElementById('vpDrawer');
  const overlay   = document.getElementById('vpDrawerOverlay');

  function openDrawer() {
    drawer?.classList.add('is-open');
    overlay?.classList.add('is-open');
    hamburger?.classList.add('is-open');
    document.body.classList.add('vp-drawer-open');
  }

  function closeDrawer() {
    drawer?.classList.remove('is-open');
    overlay?.classList.remove('is-open');
    hamburger?.classList.remove('is-open');
    document.body.classList.remove('vp-drawer-open');
  }

  hamburger?.addEventListener('click', openDrawer);
  overlay?.addEventListener('click', closeDrawer);
  document.getElementById('vpDrawerClose')?.addEventListener('click', closeDrawer);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
  });

  drawer?.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', closeDrawer);
  });

  document.querySelectorAll('.vp-drawer-section-toggle').forEach(toggle => {
    toggle.addEventListener('click', () => {
      const section = toggle.closest('.vp-drawer-section');
      const isOpen  = section.classList.contains('is-open');

      document.querySelectorAll('.vp-drawer-section.is-open').forEach(s => {
        s.classList.remove('is-open');
      });

      if (!isOpen) section.classList.add('is-open');
    });
  });

})();