/**
 * VetJobs Portal - Main JavaScript File (CLEAN VERSION)
 * Stable, modular, and conflict-free
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initializeApp();
        initializeTheme();
        initializeDashboardIfNeeded();

        console.log("App initialized");
    });

    /**
     * =========================
     * APP INITIALIZER
     * =========================
     */
    function initializeApp() {
        initializeNavigation();
        initializeCards();
        initializeForms();
        initializeTooltips();
        initializeScrollEffects();
    }

    /**
     * =========================
     * NAVIGATION
     * =========================
     */
    function initializeNavigation() {
        const currentPath = window.location.pathname;

        // Supports BOTH old Bootstrap nav AND your custom nav
        const navLinks = document.querySelectorAll(
            '.navbar-nav .nav-link, .vp-nav-link'
        );

        navLinks.forEach(link => {
            if (link.getAttribute('href') === currentPath) {
                link.classList.add('active');
            }
        });

        // Bootstrap mobile collapse (only if exists)
        const navbarCollapse = document.getElementById('navbarNav');

        if (navbarCollapse && typeof bootstrap !== 'undefined') {
            const links = navbarCollapse.querySelectorAll(
                '.nav-link:not(.dropdown-toggle), .dropdown-item'
            );

            links.forEach(link => {
                link.addEventListener('click', () => {
                    const bsCollapse = new bootstrap.Collapse(navbarCollapse, {
                        toggle: false
                    });
                    bsCollapse.hide();
                });
            });
        }
    }

    /**
     * =========================
     * CARDS
     * =========================
     */
    function initializeCards() {
        const interactiveCards = document.querySelectorAll('.card[href], .card a');

        interactiveCards.forEach(card => {
            card.addEventListener('mouseenter', function () {
                this.style.transform = 'translateY(-5px)';
                this.style.transition = 'transform 0.3s ease';
            });

            card.addEventListener('mouseleave', function () {
                this.style.transform = 'translateY(0)';
            });
        });

        const actionCards = document.querySelectorAll('.dashboard-quick-action');

        actionCards.forEach(card => {
            card.addEventListener('click', function () {
                const button = this.querySelector('.btn') || this;
                addLoadingState(button);

                setTimeout(() => {
                    removeLoadingState(button);
                }, 1000);
            });
        });
    }

    /**
     * =========================
     * FORMS
     * =========================
     */
    function initializeForms() {
        const forms = document.querySelectorAll('form');

        forms.forEach(form => {
            form.addEventListener('submit', function (e) {
                if (!validateForm(this)) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                this.classList.add('was-validated');
            });
        });

        // Password validation (single source of truth)
        const password = document.getElementById('password');
        const confirm = document.getElementById('confirm_password');

        if (password && confirm) {
            const validatePasswords = () => {
                if (confirm.value !== password.value) {
                    confirm.setCustomValidity('Passwords do not match');
                } else {
                    confirm.setCustomValidity('');
                }
            };

            confirm.addEventListener('input', validatePasswords);
            password.addEventListener('input', validatePasswords);
        }

        // Username normalization
        const username = document.getElementById('username');
        if (username) {
            username.addEventListener('input', function () {
                this.value = this.value.toLowerCase().replace(/\s/g, '');
            });
        }

        // ❌ REMOVED phone formatting (handled by phone-input.js)
    }

    /**
     * =========================
     * TOOLTIPS
     * =========================
     */
    function initializeTooltips() {
        if (typeof bootstrap === 'undefined') return;

        const triggers = document.querySelectorAll('[data-bs-toggle="tooltip"]');

        triggers.forEach(el => new bootstrap.Tooltip(el));
    }

    /**
     * =========================
     * SCROLL EFFECTS
     * =========================
     */
    function initializeScrollEffects() {
        const links = document.querySelectorAll(
            'a[href^="#"]:not([data-bs-toggle]):not([role="button"])'
        );

        links.forEach(link => {
            link.addEventListener('click', function (e) {
                const targetId = this.getAttribute('href');

                if (targetId && targetId !== '#' && targetId.length > 1) {
                    const target = document.querySelector(targetId);

                    if (target) {
                        e.preventDefault();
                        target.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        });

        const navbar = document.querySelector('.navbar');

        if (navbar && navbar.classList.contains('navbar-transparent')) {
            window.addEventListener('scroll', function () {
                navbar.classList.toggle('navbar-scrolled', window.scrollY > 50);
            });
        }
    }

    /**
     * =========================
     * UTILITIES
     * =========================
     */
    function validateForm(form) {
        let valid = true;

        form.querySelectorAll('[required]').forEach(field => {
            if (!field.value.trim()) {
                valid = false;
                field.classList.add('is-invalid');
            } else {
                field.classList.remove('is-invalid');
                field.classList.add('is-valid');
            }
        });

        return valid;
    }

    function addLoadingState(button) {
        if (!button) return;

        button.classList.add('btn-loading');
        button.disabled = true;

        button.dataset.originalText = button.textContent;
        button.textContent = 'Loading...';
    }

    function removeLoadingState(button) {
        if (!button) return;

        button.classList.remove('btn-loading');
        button.disabled = false;

        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
            delete button.dataset.originalText;
        }
    }

    function showNotification(message, type = 'info') {
        const container = document.querySelector('.container');
        if (!container) return;

        const el = document.createElement('div');
        el.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show">
                ${message}
                <button class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        container.prepend(el.firstElementChild);
    }

    function animateCounters() {
        document.querySelectorAll('.counter').forEach(counter => {
            const target = parseInt(counter.textContent);
            let current = 0;
            const step = target / 100;

            const timer = setInterval(() => {
                current += step;

                if (current >= target) {
                    counter.textContent = target;
                    clearInterval(timer);
                } else {
                    counter.textContent = Math.floor(current);
                }
            }, 20);
        });
    }

    /**
     * =========================
     * GLOBAL EXPORT
     * =========================
     */
    window.VetJobsPortal = {
        showNotification,
        addLoadingState,
        removeLoadingState,
        animateCounters
    };

})();

/**
 * =========================
 * DASHBOARD
 * =========================
 */
function initializeDashboardIfNeeded() {
    if (
        document.body.classList.contains('dashboard-page') ||
        window.location.pathname.includes('/dashboard')
    ) {
        initializeDashboard();
    }
}

function initializeDashboard() {
    setTimeout(() => {
        window.VetJobsPortal?.animateCounters();
    }, 500);

    document.querySelectorAll('.quick-action').forEach(el => {
        el.addEventListener('click', function () {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => (this.style.transform = 'scale(1)'), 100);
        });
    });

    updateProfileCompletion();
}

function updateProfileCompletion() {
    const items = document.querySelectorAll('.profile-completion-item');
    const completed = document.querySelectorAll('.profile-completion-item.completed').length;

    const percent = items.length
        ? Math.round((completed / items.length) * 100)
        : 0;

    const bar = document.querySelector('.profile-progress .progress-bar');
    const text = document.querySelector('.profile-progress-text');

    if (bar) {
        bar.style.width = percent + '%';
        bar.setAttribute('aria-valuenow', percent);
    }

    if (text) text.textContent = percent + '%';
}

/**
 * =========================
 * THEME
 * =========================
 */
function initializeTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
        document.documentElement.setAttribute('data-bs-theme', saved);
    }
}

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-bs-theme');
    const next = current === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-bs-theme', next);
    localStorage.setItem('theme', next);
}