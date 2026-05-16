(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    updateNotificationCounter();
    setInterval(updateNotificationCounter, 30000);
  });

  function updateNotificationCounter() {
    fetch('/notifications/api/unread-count')
      .then(r => r.json())
      .then(data => {
        const count   = data.unread_count || 0;
        const display = count > 99 ? '99+' : count;
        ['notification-badge', 'notification-badge-mobile'].forEach(id => {
          const el = document.getElementById(id);
          if (!el) return;
          el.textContent = display;
          el.style.display = count > 0 ? 'block' : 'none';
        });
      })
      .catch(() => {});
  }

  function loadNotifications() {
    fetch('/notifications/api/list?limit=12&include_read=true')
      .then(r => r.json())
      .then(data => {
        const el = document.getElementById('notification-list');
        if (!el) return;
        el.innerHTML = data.notifications && data.notifications.length
          ? data.notifications.map(n => renderNotif(n)).join('')
          : emptyState();
      })
      .catch(() => {});
  }

  function loadNotificationsMobile() {
    fetch('/notifications/api/list?limit=8&include_read=true')
      .then(r => r.json())
      .then(data => {
        const el = document.getElementById('notification-list-mobile');
        if (!el) return;
        el.innerHTML = data.notifications && data.notifications.length
          ? data.notifications.map(n => renderNotif(n, true)).join('')
          : emptyState();
      })
      .catch(() => {});
  }

  function markNotificationRead(id) {
    fetch(`/notifications/mark-read/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
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
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        updateNotificationCounter();
        loadNotifications();
        loadNotificationsMobile();
      }
    });
  }

  function clearAllNotifications() {
    fetch('/notifications/clear-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        updateNotificationCounter();
        loadNotifications();
        loadNotificationsMobile();
      }
    })
    .catch(() => {});
  }

  function renderNotif(n, mobile = false) {
    const maxLen = mobile ? 70 : 90;
    const msg    = n.message && n.message.length > maxLen
      ? n.message.slice(0, maxLen) + '…'
      : (n.message || '');

    const unreadDot = !n.is_read
      ? `<div style="width:7px;height:7px;background:var(--gold);border-radius:50%;flex-shrink:0;margin-top:5px;"></div>`
      : `<div style="width:7px;flex-shrink:0;"></div>`;

    const actionUrl = n.action_url || '#';

    return `
      <div onclick="handleNotifClick(${n.id}, '${actionUrl}')"
           style="display:flex;align-items:flex-start;gap:10px;padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.04);cursor:pointer;background:${n.is_read ? 'transparent' : 'rgba(212,175,55,0.03)'};transition:background 0.15s ease;"
           onmouseover="this.style.background='rgba(255,255,255,0.04)'"
           onmouseout="this.style.background='${n.is_read ? 'transparent' : 'rgba(212,175,55,0.03)'}'">
        ${unreadDot}
        <div style="flex:1;min-width:0;">
          <div style="font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:700;color:${n.is_read ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.9)'};margin-bottom:3px;line-height:1.3;">${n.title || ''}</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.4);line-height:1.5;">${msg}</div>
          <div style="font-family:'Barlow Condensed',sans-serif;font-size:10px;color:rgba(255,255,255,0.2);margin-top:5px;letter-spacing:0.5px;">${n.formatted_created_at || ''}</div>
        </div>
        ${!n.is_read ? `<button onclick="event.stopPropagation();markNotificationRead(${n.id})" title="Mark as read"
          style="background:none;border:none;color:rgba(255,255,255,0.2);cursor:pointer;font-size:11px;padding:0;flex-shrink:0;transition:color 0.15s;"
          onmouseover="this.style.color='var(--gold)'" onmouseout="this.style.color='rgba(255,255,255,0.2)'">
          <i class="fas fa-check"></i>
        </button>` : ''}
      </div>`;
  }

  function handleNotifClick(id, url) {
    markNotificationRead(id);
    if (url && url !== '#') {
      setTimeout(() => { window.location.href = url; }, 150);
    }
  }

  function emptyState() {
    return `
      <div style="text-align:center;padding:36px 16px;">
        <i class="fas fa-bell-slash" style="font-size:24px;color:rgba(255,255,255,0.1);display:block;margin-bottom:10px;"></i>
        <div style="font-family:'Barlow Condensed',sans-serif;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,0.2);">No notifications</div>
      </div>`;
  }

  // Global exports
  window.updateNotificationCounter  = updateNotificationCounter;
  window.loadNotifications          = loadNotifications;
  window.loadNotificationsMobile    = loadNotificationsMobile;
  window.markNotificationRead       = markNotificationRead;
  window.markAllAsRead              = markAllAsRead;
  window.clearAllNotifications      = clearAllNotifications;
  window.handleNotifClick           = handleNotifClick;
})();
