/* ── Page transitions ────────────────────────────────────────────────────── */
(function () {
  const DURATION = 200; // ms — matches CSS fade-out duration

  function navigateTo(href) {
    document.body.classList.add('page-leaving');
    setTimeout(() => { window.location.href = href; }, DURATION);
  }

  // Intercept all clicks on same-origin links
  document.addEventListener('click', function (e) {
    const a = e.target.closest('a[href]');
    if (!a) return;

    // Let modified clicks (new tab etc.) pass through
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target === '_blank') return;

    const raw = a.getAttribute('href');
    if (!raw || raw.startsWith('mailto:') || raw.startsWith('tel:') || raw.startsWith('javascript:')) return;

    let url;
    try { url = new URL(raw, location.href); } catch { return; }

    // External link — let browser handle
    if (url.origin !== location.origin) return;

    // Same page with hash → allow in-page scroll
    if (url.pathname === location.pathname && url.hash) return;

    // Already on target page (no change)
    if (url.href === location.href) return;

    e.preventDefault();
    navigateTo(url.href);
  }, true);

  // bfcache restore — strip leaving class so page is visible again
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) document.body.classList.remove('page-leaving');
  });
})();

/* ── Config ──────────────────────────────────────────────────────────────── */
const API_BASE = (window.__API_BASE__ || 'https://sujas.onrender.com') + '/api/v1';

/* ── Auth helpers ────────────────────────────────────────────────────────── */
const auth = {
  getToken()        { return sessionStorage.getItem('sujas_token'); },
  setToken(t)       { sessionStorage.setItem('sujas_token', t); },
  clear()           { sessionStorage.removeItem('sujas_token'); },
  isLoggedIn()      { return !!this.getToken(); },
  headers() {
    return { 'Authorization': `Bearer ${this.getToken()}` };
  },
};

/* ── API client ──────────────────────────────────────────────────────────── */
const api = {
  async _fetch(path, opts = {}) {
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        // FastAPI validation errors return detail as an array of objects
        if (Array.isArray(j.detail)) {
          msg = j.detail.map(e => e.msg || JSON.stringify(e)).join(', ');
        } else {
          msg = j.detail || msg;
        }
      } catch {}
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  },

  /* Summaries */
  getSummaries({ page = 1, pageSize = 12, month } = {}) {
    const q = new URLSearchParams({ page, page_size: pageSize });
    if (month) q.set('month', month);
    return this._fetch(`/sujas/?${q}`);
  },
  getSummary(id) {
    return this._fetch(`/sujas/${id}`);
  },
  getSummaryBySlug(slug) {
    /* slug = "2026/04/01" → GET /api/v1/sujas/2026/04/01 */
    return this._fetch(`/sujas/${slug}`);
  },
  createSummary(formData) {
    return this._fetch('/sujas/', {
      method: 'POST',
      headers: auth.headers(),
      body: formData,
    });
  },
  deleteSummary(id) {
    return this._fetch(`/sujas/${id}`, {
      method: 'DELETE',
      headers: auth.headers(),
    });
  },

  /* Economics */
  getChapters({ page = 1, pageSize = 100, search, all = false } = {}) {
    const q = new URLSearchParams({ page, page_size: pageSize });
    if (search) q.set('search', search);
    if (all)   q.set('status', 'all');
    return this._fetch(`/economics/?${q}`);
  },
  getChapter(id) {
    return this._fetch(`/economics/${id}`);
  },
  createChapter(data) {
    return this._fetch('/economics/', {
      method: 'POST',
      headers: { ...auth.headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },
  updateChapter(id, data) {
    return this._fetch(`/economics/${id}`, {
      method: 'PUT',
      headers: { ...auth.headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },
  deleteChapter(id) {
    return this._fetch(`/economics/${id}`, {
      method: 'DELETE',
      headers: auth.headers(),
    });
  },

  /* Blog */
  getBlogPosts({ page = 1, pageSize = 12, all = false } = {}) {
    const q = new URLSearchParams({ page, page_size: pageSize });
    if (all) q.set('all', 'true');
    return this._fetch(`/blog/?${q}`);
  },
  getBlogPost(slug) {
    return this._fetch(`/blog/${encodeURIComponent(slug)}`);
  },
  createBlogPost(data) {
    return this._fetch('/blog/', {
      method: 'POST',
      headers: { ...auth.headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },
  updateBlogPost(id, data) {
    return this._fetch(`/blog/${id}`, {
      method: 'PUT',
      headers: { ...auth.headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },
  deleteBlogPost(id) {
    return this._fetch(`/blog/${id}`, {
      method: 'DELETE',
      headers: auth.headers(),
    });
  },

  /* Auth */
  async login(username, password) {
    const data = await this._fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    auth.setToken(data.access_token);
    return data;
  },
};

/* ── DOM helpers ─────────────────────────────────────────────────────────── */
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

function showAlert(el, msg, type = 'error') {
  el.textContent = msg;
  el.className = `alert alert-${type} show`;
}

function hideAlert(el) {
  el.className = 'alert';
}

function setLoading(btn, loading) {
  btn.disabled = loading;
  btn._origText = btn._origText || btn.innerHTML;
  btn.innerHTML = loading
    ? '<span class="spinner"></span>'
    : btn._origText;
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function stripHtml(html) {
  const div = document.createElement('div');
  div.innerHTML = html;
  // Remove style/script nodes so their source text doesn't bleed into the excerpt
  div.querySelectorAll('style, script').forEach(el => el.remove());
  return (div.textContent || div.innerText || '').replace(/\s+/g, ' ').trim();
}

/* ── Ripple effect ───────────────────────────────────────────────────────── */
function createRipple(e) {
  const btn = e.currentTarget;
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 1.6;
  const x = (e.clientX - rect.left) - size / 2;
  const y = (e.clientY - rect.top)  - size / 2;
  const wave = document.createElement('span');
  wave.className = 'ripple-wave';
  wave.style.cssText = `width:${size}px;height:${size}px;left:${x}px;top:${y}px`;
  btn.appendChild(wave);
  wave.addEventListener('animationend', () => wave.remove(), { once: true });
}

function initRipples(root = document) {
  root.querySelectorAll('.btn, .nav-btn, .adm-btn, .sticky-pdf').forEach(btn => {
    if (btn.dataset.ripple) return;
    btn.dataset.ripple = '1';
    btn.addEventListener('click', createRipple);
  });
}

/* ── Scroll-reveal (IntersectionObserver) ───────────────────────────────── */
function animateOnScroll(root = document) {
  const els = root.querySelectorAll('.anim:not(.visible), .anim-scale:not(.visible), .anim-left:not(.visible)');
  if (!els.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); io.unobserve(e.target); }
    });
  }, { threshold: 0.07, rootMargin: '0px 0px -16px 0px' });
  els.forEach(el => io.observe(el));
}

/* ── Nav: active link + hamburger ───────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  /* Active link */
  const page = location.pathname.split('/').pop() || 'index.html';
  $$('.nav-link').forEach(a => {
    if (a.getAttribute('href') === page) a.classList.add('active');
  });

  /* Hamburger toggle */
  const hamburger = document.getElementById('navHamburger');
  const mobileMenu = document.getElementById('navMobile');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      const open = mobileMenu.classList.toggle('open');
      hamburger.classList.toggle('open', open);
      hamburger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });
  }

  /* Animate static elements already in DOM */
  animateOnScroll();
  initRipples();

  /* Mobile logout button mirrors desktop */
  const logoutBtnMobile = document.getElementById('logoutBtnMobile');
  if (logoutBtnMobile) {
    logoutBtnMobile.addEventListener('click', () => {
      document.getElementById('logoutBtn')?.click();
    });
  }
});
