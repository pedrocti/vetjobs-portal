// Navbar scroll
window.addEventListener("scroll", function () {
  document.querySelector(".premium-navbar")
    ?.classList.toggle("scrolled", window.scrollY > 40);
});

// Auto-hide alerts
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.alert').forEach(alert => {
      alert.style.transition = 'opacity 0.6s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 600);
    });
  }, 4000);
});