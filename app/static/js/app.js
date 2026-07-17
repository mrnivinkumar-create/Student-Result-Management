/* ============================================================
   APP.JS — Premium Interactions & Animations
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  /* ---- Page Load Fade ---- */
  document.querySelector(".container")?.classList.add("page-fade");

  /* ---- Flash Message Auto-Dismiss ---- */
  document.querySelectorAll(".flash").forEach((el, i) => {
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(-12px) scale(0.96)";
      el.style.transition = "all 0.45s cubic-bezier(0.4, 0, 0.2, 1)";
      setTimeout(() => el.remove(), 460);
    }, 3500 + i * 300);
  });

  /* ---- Scroll-Triggered Entrance Animations ---- */
  const animateTargets = document.querySelectorAll(
    ".card, .hero-content, .hero-card, .feature-card, .sem-card, .metric, .auth-card"
  );
  animateTargets.forEach((el) => el.classList.add("animate-in"));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
          setTimeout(() => {
            entry.target.classList.add("visible");
          }, index * 80);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
  );
  animateTargets.forEach((el) => observer.observe(el));

  /* ---- Button Ripple Effect ---- */
  document.querySelectorAll(".btn").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      const rect = this.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      this.style.setProperty("--ripple-x", x + "%");
      this.style.setProperty("--ripple-y", y + "%");
    });
  });

  /* ---- Counter Animation for Metrics ---- */
  const metricStrongs = document.querySelectorAll(".metric strong");
  const counterObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          counterObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.5 }
  );
  metricStrongs.forEach((el) => counterObserver.observe(el));

  function animateCounter(el) {
    const text = el.textContent.trim();
    const num = parseFloat(text);
    if (isNaN(num)) return;
    const suffix = text.replace(/[\d.]/g, "").trim();
    const decimals = text.includes(".") ? (text.split(".")[1] || "").replace(/[^\d]/g, "").length : 0;
    const duration = 1200;
    const start = performance.now();

    function tick(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      const current = (num * eased).toFixed(decimals);
      el.textContent = current + (suffix ? " " + suffix : "");
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ---- Floating Particle Canvas ---- */
  const canvas = document.getElementById("particle-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    let w, h;
    const particles = [];
    const PARTICLE_COUNT = 45;

    function resize() {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    class Particle {
      constructor() { this.reset(); }
      reset() {
        this.x = Math.random() * w;
        this.y = Math.random() * h;
        this.size = Math.random() * 2.2 + 0.5;
        this.speedX = (Math.random() - 0.5) * 0.3;
        this.speedY = (Math.random() - 0.5) * 0.3;
        this.opacity = Math.random() * 0.4 + 0.08;
        this.hue = Math.random() > 0.5 ? 250 : 165; // purple or teal
      }
      update() {
        this.x += this.speedX;
        this.y += this.speedY;
        if (this.x < -10 || this.x > w + 10 || this.y < -10 || this.y > h + 10) {
          this.reset();
        }
      }
      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${this.hue}, 80%, 65%, ${this.opacity})`;
        ctx.fill();
      }
    }

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push(new Particle());
    }

    function animate() {
      ctx.clearRect(0, 0, w, h);
      particles.forEach((p) => {
        p.update();
        p.draw();
      });

      // Draw lines between close particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 140) {
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.strokeStyle = `rgba(108, 99, 255, ${0.06 * (1 - dist / 140)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }

      requestAnimationFrame(animate);
    }
    animate();
  }

  /* ---- Table Row Stagger Animation ---- */
  document.querySelectorAll("tbody tr").forEach((row, i) => {
    row.style.opacity = "0";
    row.style.transform = "translateX(-15px)";
    row.style.transition = `all 0.4s cubic-bezier(0.4, 0, 0.2, 1) ${i * 0.06}s`;
    setTimeout(() => {
      row.style.opacity = "1";
      row.style.transform = "translateX(0)";
    }, 200);
  });

  /* ---- Nav Link Active Indicator ---- */
  const currentPath = window.location.pathname;
  document.querySelectorAll("nav a").forEach((link) => {
    if (link.getAttribute("href") === currentPath) {
      link.style.color = "#fff";
      link.style.background = "rgba(108, 99, 255, 0.15)";
    }
  });
});
