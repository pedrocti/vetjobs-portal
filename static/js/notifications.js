/**
 * Notifications System (GLOBAL + SAFE)
 */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initializeNotifications();
    });

    function initializeNotifications() {
        updateNotificationCounter();
        setInterval(updateNotificationCounter, 30000);
    }

    /**
     * =========================
     * COUNTER
     * =========================
     */
    function updateNotificationCounter() {
        fetch('/notifications/api/unread-count')
            .then(res => res.json())
            .then(data => {
                const desktop = document.getElementById('notification-badge');
                const mobile  = document.getElementById('notification-badge-mobile');

                const count = data.unread_count || 0;
                const display = count > 99 ? '99+' : count;

                if (desktop) {
                    desktop.textContent = display;
                    desktop.style.display = count > 0 ? 'block' : 'none';
                }

                if (mobile) {
                    mobile.textContent = display;
                    mobile.style.display = count > 0 ? 'block' : 'none';
                }
            })
            .catch(err => console.error('Notification counter error:', err));
    }

    /**
     * =========================
     * LOAD DROPDOWN (DESKTOP)
     * =========================
     */
    function loadNotifications() {
        fetch('/notifications/api/list?limit=10&include_read=false')
            .then(res => res.json())
            .then(data => {
                const list = document.getElementById('notification-list');

                if (!list) return;

                if (!data.notifications.length) {
                    list.innerHTML = emptyState();
                    return;
                }

                list.innerHTML = data.notifications.map(renderNotification).join('');
            });
    }

    /**
     * =========================
     * LOAD MOBILE
     * =========================
     */
    function loadNotificationsMobile() {
        fetch('/notifications/api/list?limit=10&include_read=false')
            .then(res => res.json())
            .then(data => {
                const list = document.getElementById('notification-list-mobile');

                if (!list) return;

                if (!data.notifications.length) {
                    list.innerHTML = emptyState();
                    return;
                }

                list.innerHTML = data.notifications.map(n => renderNotification(n, true)).join('');
            });
    }

    /**
     * =========================
     * MARK AS READ
     * =========================
     */
    function markNotificationRead(id) {
        fetch(`/notifications/mark-read/${id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(res => res.json())
        .then(d => {
            if (d.success) {
                updateNotificationCounter();
                loadNotifications();
                loadNotificationsMobile();
            }
        });
    }

    function markAllAsRead() {
        fetch('/notifications/mark-all-read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(res => res.json())
        .then(d => {
            if (d.success) {
                updateNotificationCounter();
                loadNotifications();
                loadNotificationsMobile();
            }
        });
    }

    /**
     * =========================
     * RENDER
     * =========================
     */
    function renderNotification(n, mobile = false) {
        const maxLen = mobile ? 80 : 100;

        return `
            <div class="dropdown-item-text notification-item ${n.is_read ? 'read' : 'unread'}"
                 onclick="markNotificationRead(${n.id})">
                <div class="d-flex align-items-start">
                    <div class="me-2">
                        <i class="${n.category_icon} ${n.priority_class}"></i>
                    </div>
                    <div class="flex-grow-1">
                        <div class="fw-bold">${n.title}</div>
                        <div class="text-muted small">
                            ${truncate(n.message, maxLen)}
                        </div>
                        <div class="text-muted small">${n.formatted_created_at}</div>
                    </div>
                    ${!n.is_read ? '<div class="badge bg-primary">New</div>' : ''}
                </div>
            </div>
        `;
    }

    function truncate(text, max) {
        return text.length > max ? text.slice(0, max) + '...' : text;
    }

    function emptyState() {
        return `
            <div class="text-center p-3 text-muted">
                <i class="fas fa-bell-slash fa-2x mb-2"></i>
                <div>No new notifications</div>
            </div>
        `;
    }

    /**
     * =========================
     * GLOBAL EXPORT (IMPORTANT)
     * =========================
     */
    window.updateNotificationCounter = updateNotificationCounter;
    window.loadNotifications = loadNotifications;
    window.loadNotificationsMobile = loadNotificationsMobile;
    window.markNotificationRead = markNotificationRead;
    window.markAllAsRead = markAllAsRead;

})();