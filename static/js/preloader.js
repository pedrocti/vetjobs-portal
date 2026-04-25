(function () {
  function hidePreloader() {
    const el = document.getElementById('preloader');
    if (!el) return;

    el.classList.add('fade-out');
    setTimeout(() => el.style.display = 'none', 650);
  }

  window.addEventListener('load', hidePreloader);
  setTimeout(hidePreloader, 4000);
})();