
(function () {
  // Slider
  const slides = document.querySelectorAll('.hero-slider .slide');
  const dots   = document.querySelectorAll('.hero-dot');
  let current  = 0;

  function goToSlide(n) {
    slides[current].classList.remove('active');
    dots[current].classList.remove('active');
    current = (n + slides.length) % slides.length;
    slides[current].classList.add('active');
    dots[current].classList.add('active');
  }

  dots.forEach(dot => dot.addEventListener('click', () => goToSlide(+dot.dataset.slide)));
  setInterval(() => goToSlide(current + 1), 6000);

  // Rotating words
  const words  = ['Career Portal', 'Transition Portal', 'Talent Network', 'Opportunity Hub'];
  const wordEl = document.getElementById('heroRotatingWord');
  let wordIdx  = 0;

  if (wordEl) {
    setInterval(() => {
      wordEl.classList.add('fade-out');
      setTimeout(() => {
        wordIdx = (wordIdx + 1) % words.length;
        wordEl.textContent = words[wordIdx];
        wordEl.classList.remove('fade-out');
      }, 460);
    }, 3200);
  }

  // Gold particles
  const canvas = document.getElementById('heroParticles');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() {
    const s = canvas.closest('section');
    W = canvas.width  = s ? s.offsetWidth  : window.innerWidth;
    H = canvas.height = s ? s.offsetHeight : window.innerHeight;
  }

  window.addEventListener('resize', resize);
  resize();

  for (let i = 0; i < 60; i++) {
    particles.push({
      x: Math.random() * W, y: Math.random() * H,
      r: 0.4 + Math.random() * 1.4,
      dx: -0.18 + Math.random() * 0.36,
      dy: -0.35 + Math.random() * 0.27,
      alpha: 0.15 + Math.random() * 0.45,
      da: -0.003 + Math.random() * 0.006,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => {
      p.x += p.dx; p.y += p.dy; p.alpha += p.da;
      if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
      if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
      if (p.alpha <= 0.1 || p.alpha >= 0.65) p.da *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(212, 175, 55, ${p.alpha})`;
      ctx.fill();
    });
    requestAnimationFrame(draw);
  }

  draw();
})();
